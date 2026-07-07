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
import shutil
import subprocess
from pathlib import Path

from rockforge.domain.arrangement import Arrangement
from rockforge.domain.errors import PackagingError
from rockforge.infrastructure.packaging.dlcbuilder import (
    PackagingResult,
    build_project_metadata,
)
from rockforge.infrastructure.packaging.psarc import container, gamedata, manifest, sng, soundbank
from rockforge.infrastructure.packaging.rs2dlc import write_rs2dlc
from rockforge.infrastructure.packaging.wwise import WwiseWemConverter
from rockforge.infrastructure.rsxml.vocals import VocalEvent, write_vocals_xml
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
    ) -> PackagingResult:
        if not arrangements:
            raise PackagingError("no arrangements to package")
        out_dir.mkdir(parents=True, exist_ok=True)

        instrumental_xml: list[Path] = []
        for arr in arrangements:
            instrumental_xml.append(
                write_arrangement_xml(arr, out_dir / f"arrangement_{arr.kind.value.lower()}.xml")
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

        wem_path: Path | None = None
        if self._wem_converter is not None and self._wem_converter.available():
            wem = self._wem_converter.convert(audio, out_dir / "wwise_work")
            wem_path = out_dir / "audio.wem"
            shutil.copy2(wem, wem_path)

        meta = arrangements[0].metadata
        song_key = manifest.song_key_from_title(meta.artist, meta.title)
        key_lower = song_key.lower()

        # Always ship (placeholder) album art so the song list's AlbumArt URN
        # resolves; DLC Builder generates real DDS textures from the cover.
        files: dict[str, bytes] = manifest.build_manifest_files(
            [(arr, manifest.arrangement_asset_name(song_key, arr.kind)) for arr in arrangements],
            song_key,
            include_vocals=bool(vocals),
            has_album_art=True,
        )

        # Game-enumeration assets — without these the song never lists.
        entities = [
            (manifest.persistent_id(song_key, manifest.arrangement_asset_name(song_key, arr.kind)),
             f"{song_key}_{manifest.arrangement_display_name(arr.kind)}")
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
        files[f"songs/arr/{key_lower}_showlights.xml"] = gamedata.build_showlights().encode("utf-8")
        # Real cover → DXT1 DDS when a cover was uploaded (and Pillow is present);
        # otherwise a neutral placeholder so the AlbumArt URN still resolves.
        cover_for_dds = cover_art_dest if cover_art_dest is not None else None
        for res in (64, 128, 256):
            files[f"gfxassets/album_art/album_{key_lower}_{res}.dds"] = gamedata.album_art_dds(
                res, cover_for_dds
            )

        psarc_path: Path | None = None
        try:
            from rockforge.infrastructure.packaging.psarc.crypto import encrypt_sng

            for arr in arrangements:
                model = sng.from_arrangement(arr)
                payload = sng.write_sng(model)
                asset = manifest.arrangement_asset_name(song_key, arr.kind)
                files[f"songs/bin/generic/{asset}.sng"] = encrypt_sng(payload)

            # Vocals are a separate arrangement with their own SNG (real
            # Rocksmith convention), not embedded in an instrument SNG.
            if vocals:
                vocals_payload = sng.write_sng(sng.from_vocals(vocals))
                files[f"songs/bin/generic/{key_lower}_vocals.sng"] = encrypt_sng(vocals_payload)

            if wem_path is not None:
                # Real Rocksmith audio: a Wwise SoundBank (Play_<key> event +
                # audio prefetch) plus the full stream as <fileID>.wem beside it.
                # Without the .bnk the game has no event to fire and plays silence.
                # A matching preview bank is required by the manifest/xblock.
                wem_bytes = wem_path.read_bytes()
                bnk_bytes, wem_file_id = soundbank.generate_soundbank(song_key, wem_bytes)
                files[f"audio/windows/song_{key_lower}.bnk"] = bnk_bytes
                files[f"audio/windows/{wem_file_id}.wem"] = wem_bytes

                # A real ~28 s preview clip (its own .wem), not the full stream.
                assert self._wem_converter is not None
                preview_wem_bytes = wem_bytes
                start_s, length_s = _preview_window(meta.song_length)
                clip = _extract_preview_clip(
                    audio, out_dir / "preview.wav", start_s, length_s
                )
                if clip is not None:
                    preview_wem = self._wem_converter.convert(clip, out_dir / "wwise_preview")
                    preview_wem_bytes = preview_wem.read_bytes()
                preview_bnk, preview_id = soundbank.generate_soundbank(
                    f"{song_key}_preview", preview_wem_bytes
                )
                files[f"audio/windows/song_{key_lower}_preview.bnk"] = preview_bnk
                files[f"audio/windows/{preview_id}.wem"] = preview_wem_bytes
            else:
                # No Wwise available: pack the WAV under a path the retail game
                # will not load — the bundle stays the trustworthy audio path.
                files[f"audio/{key_lower}{audio_dest.suffix}"] = audio_dest.read_bytes()

            psarc_bytes = container.pack_entries(files, encrypt=True)
            # Rocksmith 2014 on PC only loads CDLC whose filename ends in
            # "_p.psarc" (the "_p" platform tag) — without it the game ignores
            # the file and the song never appears in the song list.
            psarc_path = out_dir / f"{song_key}_p.psarc"
            psarc_path.write_bytes(psarc_bytes)
        except ImportError:
            pass

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
