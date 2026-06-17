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
- ``cover_art`` (if provided) is copied into the bundle and recorded in
  ``rockforge_project.json``, but is NOT yet embedded as an in-game DDS
  texture/``albumArt`` URN — that conversion (DDS encoding + manifest/SNG
  references) is not implemented.
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
from pathlib import Path

from rockforge.domain.arrangement import Arrangement
from rockforge.domain.errors import PackagingError
from rockforge.infrastructure.packaging.dlcbuilder import (
    PackagingResult,
    build_project_metadata,
)
from rockforge.infrastructure.packaging.psarc import container, manifest, sng
from rockforge.infrastructure.packaging.rs2dlc import write_rs2dlc
from rockforge.infrastructure.packaging.wwise import WwiseWemConverter
from rockforge.infrastructure.rsxml.vocals import VocalEvent, write_vocals_xml
from rockforge.infrastructure.rsxml.writer import write_arrangement_xml


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
        audio_for_psarc = audio_dest
        if self._wem_converter is not None and self._wem_converter.available():
            wem = self._wem_converter.convert(audio, out_dir / "wwise_work")
            wem_path = out_dir / "audio.wem"
            shutil.copy2(wem, wem_path)
            audio_for_psarc = wem_path

        meta = arrangements[0].metadata
        song_key = manifest.song_key_from_title(meta.artist, meta.title)
        key_lower = song_key.lower()

        files: dict[str, bytes] = manifest.build_manifest_files(
            [(arr, arr.kind.value) for arr in arrangements],
            song_key,
            include_vocals=bool(vocals),
        )

        try:
            from rockforge.infrastructure.packaging.psarc.crypto import encrypt_sng

            for arr in arrangements:
                model = sng.from_arrangement(arr)
                payload = sng.write_sng(model)
                files[f"songs/arr/{key_lower}_{arr.kind.value.lower()}.sng"] = encrypt_sng(
                    payload
                )

            # Vocals are a separate arrangement with their own SNG (real
            # Rocksmith convention), not embedded in an instrument SNG.
            if vocals:
                vocals_payload = sng.write_sng(sng.from_vocals(vocals))
                files[f"songs/arr/{key_lower}_vocals.sng"] = encrypt_sng(vocals_payload)

            files[f"audio/{key_lower}{audio_for_psarc.suffix}"] = audio_for_psarc.read_bytes()

            psarc_bytes = container.pack_entries(files, encrypt=True)
        except ImportError as exc:
            raise PackagingError(
                "native PSARC packing requires the 'psarc' extra "
                "(pip install -e \".[psarc]\")"
            ) from exc

        psarc_path = out_dir / f"{song_key}.psarc"
        psarc_path.write_bytes(psarc_bytes)

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
        project["psarc"] = psarc_path.name
        project["native_psarc_note"] = (
            "RockForge also packed this .psarc natively "
            "(infrastructure/packaging/psarc); the DLC Builder fields above "
            "remain valid for re-importing the bundle."
        )
        if cover_art_dest is not None:
            project["cover_art_note"] = (
                "cover_art was packed into the bundle but is NOT yet embedded as "
                "an in-game DDS texture in this native .psarc — the song's "
                "albumArt remains empty, same as DLC Builder without a cover set."
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
