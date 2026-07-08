"""Packaging stage: always emits a DLC Builder-ready bundle; PSARC only if tooling exists.

Honest constraint (docs/research/03-rocksmith-cdlc.md §6): creating the .wem
audio inside a playable PSARC REQUIRES Audiokinetic Wwise (2019–2023), which
cannot be redistributed and is typically absent in headless/server environments.
Therefore the guaranteed output is a bundle (arrangement XMLs + normalized OGG
+ project metadata) importable into DLC Builder (MIT, actively maintained),
which performs Wwise conversion, SNG compilation, DD and PSARC packing.
If an external packer command is configured AND available, it is invoked to
produce the final PSARC; otherwise packaging stops at the bundle, explicitly.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rockforge.domain.arrangement import Arrangement
from rockforge.domain.errors import PackagingError
from rockforge.infrastructure.packaging.psarc.manifest import song_key_from_title
from rockforge.infrastructure.packaging.rs2dlc import write_rs2dlc
from rockforge.infrastructure.packaging.wwise import WwiseWemConverter
from rockforge.infrastructure.rsxml.vocals import VocalEvent, write_vocals_xml
from rockforge.infrastructure.rsxml.writer import write_arrangement_xml


@dataclass(frozen=True)
class PackagingResult:
    bundle_dir: Path
    xml_paths: tuple[Path, ...]
    wem_path: Path | None  # produced only when a local Wwise installation is available
    psarc_path: Path | None  # None => packer unavailable; bundle is the deliverable


def build_project_metadata(
    arrangements: list[Arrangement],
    audio_dest: Path,
    wem_path: Path | None,
    xml_paths: list[Path],
    vocals_path: Path | None,
    cover_art_path: Path | None = None,
) -> dict[str, object]:
    """The DLC Builder-importable project descriptor (``rockforge_project.json``).

    Shared by :class:`DlcBuilderPackager` and the native PSARC packer so the
    bundle stays importable into DLC Builder regardless of ``psarc_mode`` — the
    native path produces a ``.psarc`` *and* keeps this fallback file.
    """
    meta = arrangements[0].metadata
    return {
        "title": meta.title,
        "artist": meta.artist,
        "album": meta.album,
        "year": meta.year,
        "audio": audio_dest.name,
        "audio_wem": wem_path.name if wem_path else None,
        "arrangements": [p.name for p in xml_paths],
        "vocals": vocals_path.name if vocals_path else None,
        "cover_art": cover_art_path.name if cover_art_path else None,
        "tones": {
            arr.kind.value: {"base": arr.tone_base, "slots": arr.tone_names}
            for arr in arrangements
            if arr.tone_base or arr.tone_names
        },
        "stage_confidence": {
            arr.kind.value: {k: v.value for k, v in arr.stage_confidence.items()}
            for arr in arrangements
        },
        "note": (
            "Open rockforge.rs2dlc in DLC Builder "
            "(https://github.com/iminashi/Rocksmith2014.NET) to load every "
            "arrangement, vocals, audio and cover at once, then convert audio "
            "via Wwise and pack the final PSARC. Assign tones in DLC Builder "
            "(RockForge does not author tone gear); its 'Calculate Volumes' and "
            "'Create Preview Audio' fill the neutral audio defaults."
        ),
    }


class DlcBuilderPackager:
    def __init__(
        self,
        psarc_packer_cmd: str | None = None,
        wem_converter: WwiseWemConverter | None = None,
    ) -> None:
        """psarc_packer_cmd: template like 'dlc-builder-cli pack {project}' (operator-provided)."""
        self._packer_cmd = psarc_packer_cmd
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
        # dynamic_difficulty is a native-SNG concern; the DLC Builder bundle runs
        # its own DDC on import, so the flag is accepted but not used here.
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

        meta = arrangements[0].metadata
        write_rs2dlc(
            arrangements,
            [p.name for p in instrumental_xml],
            audio_dest.name,
            song_key_from_title(meta.artist, meta.title),
            out_dir / "rockforge.rs2dlc",
            vocals_xml_name=vocals_path.name if vocals_path else None,
            cover_art_name=cover_art_dest.name if cover_art_dest else None,
        )

        wem_path: Path | None = None
        if self._wem_converter is not None and self._wem_converter.available():
            wem = self._wem_converter.convert(audio, out_dir / "wwise_work")
            wem_path = out_dir / "audio.wem"
            shutil.copy2(wem, wem_path)

        project = build_project_metadata(
            arrangements, audio_dest, wem_path, xml_paths, vocals_path, cover_art_dest
        )
        (out_dir / "rockforge_project.json").write_text(
            json.dumps(project, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        psarc: Path | None = None
        if self._packer_cmd:
            cmd = self._packer_cmd.format(project=str(out_dir))
            try:
                subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                raise PackagingError(f"external PSARC packer failed: {exc.stderr[-2000:]}") from exc
            candidates = sorted(out_dir.glob("*.psarc"))
            if not candidates:
                raise PackagingError("packer command ran but produced no .psarc")
            psarc = candidates[0]

        return PackagingResult(
            bundle_dir=out_dir, xml_paths=tuple(xml_paths), wem_path=wem_path, psarc_path=psarc
        )
