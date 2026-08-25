"""``NativePsarcPacker``: assemble a PSARC without DLC Builder (phase 5, TODO.md).

Joins phases 1-4: per-arrangement SNG compilation (``sng.py``), runtime
manifests (``manifest.py``) and the encrypted PSARC container
(``container.py``/``crypto.py``) into a single ``.psarc`` file, behind the
same :class:`~rockforge.application.ports.Packager` Protocol as
:class:`~rockforge.infrastructure.packaging.dlcbuilder.DlcBuilderPackager`.

The SNG carries the full Sng2014 section set (``sng.py``): chord templates,
chord notes, anchors, anchor extensions, fingerprints/hand shapes, note linkage
and the real NoteMask constants. Vocals are emitted as a *separate*
``<key>_vocals.sng`` arrangement (Rocksmith convention), with their own manifest.

Honest limits that remain (CLAUDE.md):
- The ``.wem`` still requires a local Wwise install (Audiokinetic EULA); when
  unavailable, the normalized WAV is packed instead, under a path the retail
  game will not load — callers should treat a PSARC without a real ``.wem`` as
  not yet game-ready, same as DLC Builder without Wwise.
- Single difficulty level only: RockForge has no dynamic-difficulty model, so
  the song is fully playable but without the progressive note-density ramp a
  DDC-processed CDLC has. This is a feature gap, not a malformed file.
- Requires the ``[psarc]`` extra (``cryptography``) for TOC/SNG encryption;
  raises :class:`PackagingError` with a clear message if missing.
- ``cover_art`` (if provided) is copied into the bundle AND converted to the
  in-game album-art DDS textures (64/128/256) in the native ``.psarc`` via
  ``gamedata.album_art_dds`` (needs Pillow; falls back to a neutral placeholder).
- The binary layout is ported from open-source format docs (Rocksmith2014.NET,
  toolkit) and round-trip-tested, but has NOT been byte-validated against a
  retail/DLC Builder SNG — there is no reference file in CI to diff against.

The bundle still carries the DLC Builder-importable ``rockforge_project.json``
(via :func:`build_project_metadata`), so the ``GET /jobs/{id}/bundle`` zip
remains a valid fallback even in native mode — the native ``.psarc`` is
additive, never a replacement for the DLC Builder import path.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from rockforge.application.ports import PackagingResult, VocalEvent
from rockforge.domain.arrangement import Arrangement
from rockforge.domain.errors import PackagingError
from rockforge.infrastructure.normalize.loudness import calculate_volume
from rockforge.infrastructure.packaging.dlcbuilder import build_project_metadata
from rockforge.infrastructure.packaging.psarc import container, gamedata, manifest, sng, soundbank
from rockforge.infrastructure.packaging.rs2dlc import write_rs2dlc
from rockforge.infrastructure.packaging.wwise import WwiseWemConverter
from rockforge.infrastructure.rsxml.vocals import write_vocals_xml
from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

# The song-select preview is a short clip, not the whole track (reusing the full
# stream makes it play over itself). Default to a ~28 s window a bit into the song.
PREVIEW_START_S = 15.0
PREVIEW_LENGTH_S = 28.0


def _preview_window(song_length: float) -> tuple[float, float]:
    if song_length and song_length > PREVIEW_START_S + 5.0:
        start = min(PREVIEW_START_S, song_length * 0.25)
        return start, min(PREVIEW_LENGTH_S, song_length - start)
    return 0.0, min(PREVIEW_LENGTH_S, song_length) if song_length else PREVIEW_LENGTH_S


def _extract_preview_clip(audio: Path, out: Path, start_s: float, length_s: float) -> Path | None:
    """Trim a preview clip with ffmpeg (same stdin/timeout guards as the
    normalizer). Returns None if ffmpeg is missing or the trim fails."""
    cmd = [
        "ffmpeg", "-nostdin", "-y",
        "-ss", str(start_s), "-t", str(length_s),
        "-i", str(audio), "-ar", "44100", "-ac", "2", str(out),
    ]
    try:
        subprocess.run(
            cmd, check=True, capture_output=True, text=True,
            stdin=subprocess.DEVNULL, timeout=300,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return out if out.exists() and out.stat().st_size > 0 else None


logger = logging.getLogger(__name__)


class NativePsarcPacker:
    def __init__(self, wem_converter: WwiseWemConverter | None = None) -> None:
        self._wem_converter = wem_converter

    def package(
        self,
        arrangements: list[Arrangement],
        audio: Path,
        out_dir: Path,
        vocals: list[VocalEvent] | None = None,
        cover_art: Path | None = None,
        dynamic_difficulty: bool = True,
    ) -> PackagingResult:
        if not arrangements:
            raise PackagingError("no arrangements to package")
        out_dir.mkdir(parents=True, exist_ok=True)

        meta = arrangements[0].metadata
        song_key = manifest.song_key_from_title(meta.artist, meta.title)
        key_lower = song_key.lower()
        album_art_urn = f"urn:image:dds:album_{key_lower}"

        instrumental_xml: list[Path] = []
        for arr in arrangements:
            # kind.name (LEAD/ALTERNATE_LEAD/…) is a safe, unique file slug — the
            # display value ("Alternate Lead") has a space.
            slug = arr.kind.name.lower()
            instrumental_xml.append(
                write_arrangement_xml(
                    arr, out_dir / f"arrangement_{slug}.xml", album_art_urn
                )
            )
        xml_paths: list[Path] = list(instrumental_xml)

        vocals_path: Path | None = None
        if vocals:
            vocals_path = write_vocals_xml(vocals, out_dir / "arrangement_vocals.xml")
            xml_paths.append(vocals_path)

        cover_art_dest: Path | None = None
        if cover_art is not None and cover_art.exists():
            cover_art_dest = out_dir / f"cover{cover_art.suffix.lower()}"
            shutil.copy2(cover_art, cover_art_dest)

        audio_dest = out_dir / f"audio{audio.suffix}"
        shutil.copy2(audio, audio_dest)

        # The Wwise .wem is needed by the native PSARC and referenced in the
        # bundle's project metadata, but a Wwise failure must NEVER abort the
        # bundle — DLC Builder can (re)build the .wem itself on import.
        wem_path: Path | None = None
        try:
            if self._wem_converter is not None and self._wem_converter.available():
                wem = self._wem_converter.convert(audio, out_dir / "wwise_work")
                wem_path = out_dir / "audio.wem"
                shutil.copy2(wem, wem_path)
        except Exception:  # noqa: BLE001 — Wwise is best-effort; keep the bundle
            logger.warning("Wwise .wem conversion failed; bundle built without it", exc_info=True)
            wem_path = None

        # The native .psarc is fully isolated: ANY failure here (missing crypto
        # extra, Wwise/ffmpeg, a packing bug) leaves the DLC Builder bundle — the
        # trustworthy path — completely intact. The reason is recorded below.
        psarc_path: Path | None = None
        psarc_error: str | None = None
        try:
            psarc_path = self._build_psarc(
                arrangements, audio, audio_dest, out_dir, vocals, cover_art_dest,
                wem_path, song_key, key_lower, meta.song_length, dynamic_difficulty,
            )
        except Exception as exc:  # noqa: BLE001 — never let the .psarc sink the bundle
            psarc_error = f"{type(exc).__name__}: {exc}"
            logger.warning("native .psarc build failed; bundle still produced: %s", psarc_error,
                           exc_info=True)

        write_rs2dlc(
            arrangements,
            [p.name for p in instrumental_xml],
            audio_dest.name,
            song_key,
            out_dir / "rockforge.rs2dlc",
            vocals_xml_name=vocals_path.name if vocals_path else None,
            cover_art_name=cover_art_dest.name if cover_art_dest else None,
        )

        # Keep the bundle DLC Builder-importable (the GET /jobs/{id}/bundle zip)
        # and additionally record the natively-produced .psarc.
        project = build_project_metadata(
            arrangements, audio_dest, wem_path, xml_paths, vocals_path, cover_art_dest
        )
        project["song_key"] = song_key
        if psarc_path is not None:
            project["psarc"] = psarc_path.name
            project["native_psarc_note"] = (
                "RockForge also packed this .psarc natively "
                "(infrastructure/packaging/psarc); the DLC Builder fields above "
                "remain valid for re-importing the bundle."
            )
        elif psarc_error is not None:
            project["native_psarc_note"] = (
                "The native .psarc could not be built "
                f"({psarc_error}); this bundle is still valid — import it into "
                "DLC Builder and let it build the .psarc."
            )
        if cover_art_dest is not None:
            project["cover_art_note"] = (
                "cover_art was packed into the bundle and converted to the in-game "
                "album-art DDS textures (64/128/256) in the native .psarc (needs "
                "Pillow, part of the [psarc] extra; falls back to a neutral "
                "placeholder otherwise)."
            )
        (out_dir / "rockforge_project.json").write_text(
            json.dumps(project, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return PackagingResult(
            bundle_dir=out_dir,
            xml_paths=tuple(xml_paths),
            wem_path=wem_path,
            psarc_path=psarc_path,
        )

    def _build_psarc(
        self,
        arrangements: list[Arrangement],
        audio: Path,
        audio_dest: Path,
        out_dir: Path,
        vocals: list[VocalEvent] | None,
        cover_art_dest: Path | None,
        wem_path: Path | None,
        song_key: str,
        key_lower: str,
        song_length: float,
        dynamic_difficulty: bool = True,
    ) -> Path:
        """Assemble the native ``.psarc``. Raises on any failure (missing crypto,
        Wwise/ffmpeg, packing); the caller keeps the bundle regardless."""
        from rockforge.infrastructure.packaging.psarc.crypto import pack_sng

        # Build each arrangement's SNG model ONCE (up to ~21 Dynamic Difficulty
        # levels, each doing phrase-linking/anchor/chord-notes work over the
        # full note list — not cheap) and reuse it for both the manifest's
        # note/phrase counts AND the actual .sng payload below, instead of
        # compiling the same arrangement twice.
        # Section numbers continue across the song's arrangements, as a DLC
        # Builder build does — applied here, before BOTH the manifests and the
        # .sng payloads are derived from these models, so the two can never
        # disagree about what "Riff 18" is.
        sng_models = sng.renumber_sections_across([
            sng.from_arrangement(arr, dynamic_difficulty=dynamic_difficulty)
            for arr in arrangements
        ])

        # Manifests (+ appid/toolkit) and album art. Placeholder art is always
        # shipped so the AlbumArt URN resolves; a real cover is DXT1-encoded.
        files: dict[str, bytes] = manifest.build_manifest_files(
            [(arr, manifest.arrangement_asset_name(song_key, arr.kind)) for arr in arrangements],
            song_key,
            include_vocals=bool(vocals),
            has_album_art=True,
            dynamic_difficulty=dynamic_difficulty,
            models=sng_models,
        )

        # Game-enumeration assets — without these the song never lists.
        # The xblock entity name is unique per arrangement (a decoded CDLC names
        # the alternate lead's entity "..._Lead2"), unlike the manifest FullName
        # which stays "..._Lead".
        entities = [
            (manifest.persistent_id(song_key, manifest.arrangement_asset_name(song_key, arr.kind)),
             f"{song_key}_{manifest.arrangement_display_name(arr.kind)}"
             + ("2" if arr.kind.is_alternate else ""))
            for arr in arrangements
        ]
        if vocals:
            entities.append((manifest.persistent_id(song_key, "Vocals"), f"{song_key}_Vocals"))
        files[f"gamexblocks/nsongs/{key_lower}.xblock"] = gamedata.build_xblock(
            song_key, entities, has_album_art=True
        ).encode("utf-8")
        files.update(gamedata.load_flat_models())
        files[f"{key_lower}_aggregategraph.nt"] = gamedata.build_aggregategraph(
            song_key,
            [manifest.arrangement_asset_name(song_key, arr.kind) for arr in arrangements],
            include_vocals=bool(vocals),
            has_album_art=True,
        ).encode("utf-8")
        # Generate the stage-lighting track from the richest chart (most notes),
        # so every arrangement shares one lit intro/stage instead of a dark one.
        showlights_src = max(arrangements, key=lambda a: len(a.notes), default=None)
        files[f"songs/arr/{key_lower}_showlights.xml"] = gamedata.build_showlights(
            showlights_src
        ).encode("utf-8")
        cover_for_dds = cover_art_dest if cover_art_dest is not None else None
        for res in (64, 128, 256):
            files[f"gfxassets/album_art/album_{key_lower}_{res}.dds"] = gamedata.album_art_dds(
                res, cover_for_dds
            )

        for arr, model in zip(arrangements, sng_models, strict=True):
            payload = sng.write_sng(model)
            asset = manifest.arrangement_asset_name(song_key, arr.kind)
            files[f"songs/bin/generic/{asset}.sng"] = pack_sng(payload)

        # Vocals are a separate arrangement with their own SNG (real Rocksmith
        # convention), not embedded in an instrument SNG.
        if vocals:
            vocals_payload = sng.write_sng(sng.from_vocals(vocals))
            files[f"songs/bin/generic/{key_lower}_vocals.sng"] = pack_sng(vocals_payload)

        if wem_path is not None:
            # Real Rocksmith audio: a Wwise SoundBank (Play_<key> event + audio
            # prefetch) plus the full stream as <fileID>.wem beside it. Without
            # the .bnk the game has no event to fire and plays silence.
            wem_bytes = wem_path.read_bytes()
            # "Calculate Volumes": measure the audio's loudness and set the Wwise
            # bus volume so the song sits at a consistent level (the .bnk shipped
            # a neutral 0). Falls back to 0 dB when ffmpeg can't measure.
            song_volume = calculate_volume(audio)
            bnk_bytes, wem_file_id = soundbank.generate_soundbank(
                song_key, wem_bytes, volume=song_volume
            )
            files[f"audio/windows/song_{key_lower}.bnk"] = bnk_bytes
            files[f"audio/windows/{wem_file_id}.wem"] = wem_bytes

            # A real ~28 s preview clip (its own .wem), not the full stream, and
            # marked single-instance so it never plays over itself. Its own
            # volume is measured on the clip so it matches the song's level.
            preview_wem_bytes = wem_bytes
            preview_volume = song_volume
            start_s, length_s = _preview_window(song_length)
            clip = _extract_preview_clip(audio, out_dir / "preview.wav", start_s, length_s)
            if clip is not None and self._wem_converter is not None:
                preview_wem = self._wem_converter.convert(clip, out_dir / "wwise_preview")
                preview_wem_bytes = preview_wem.read_bytes()
                # Match the volume to the clip that's actually shipped.
                preview_volume = calculate_volume(clip)
            preview_bnk, preview_id = soundbank.generate_soundbank(
                f"{song_key}_preview", preview_wem_bytes, volume=preview_volume, preview=True
            )
            files[f"audio/windows/song_{key_lower}_preview.bnk"] = preview_bnk
            files[f"audio/windows/{preview_id}.wem"] = preview_wem_bytes
        else:
            # No Wwise: pack the WAV under a path the retail game will not load —
            # the bundle stays the trustworthy audio path.
            files[f"audio/{key_lower}{audio_dest.suffix}"] = audio_dest.read_bytes()

        psarc_bytes = container.pack_entries(files, encrypt=True)
        # Rocksmith 2014 on PC only loads CDLC whose filename ends in "_p.psarc"
        # (the "_p" platform tag) — without it the game ignores the file.
        psarc_path = out_dir / f"{song_key}_p.psarc"
        psarc_path.write_bytes(psarc_bytes)
        return psarc_path
