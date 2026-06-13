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
from rockforge.infrastructure.packaging.wwise import WwiseWemConverter
from rockforge.infrastructure.rsxml.vocals import VocalEvent, write_vocals_xml
from rockforge.infrastructure.rsxml.writer import write_arrangement_xml


@dataclass(frozen=True)
class PackagingResult:
    bundle_dir: Path
    xml_paths: tuple[Path, ...]
    wem_path: Path | None  # produced only when a local Wwise installation is available
    psarc_path: Path | None  # None => packer unavailable; bundle is the deliverable


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
    ) -> PackagingResult:
        if not arrangements:
            raise PackagingError("no arrangements to package")
        out_dir.mkdir(parents=True, exist_ok=True)
        # DLC Builder's PhraseLevelComparer.savePhraseLevels writes a per-arrangement
        # cache file under "<project>/.phrase-levels" via File.Create, which throws
        # DirectoryNotFoundException if that folder doesn't exist yet (first build of
        # a fresh project). Pre-create it so the bundle opens/builds cleanly.
        (out_dir / ".phrase-levels").mkdir(exist_ok=True)

        xml_paths: list[Path] = []
        for arr in arrangements:
            xml_paths.append(
                write_arrangement_xml(arr, out_dir / f"arrangement_{arr.kind.value.lower()}.xml")
            )

        vocals_path: Path | None = None
        if vocals:
            vocals_path = write_vocals_xml(vocals, out_dir / "arrangement_vocals.xml")
            xml_paths.append(vocals_path)

        audio_dest = out_dir / f"audio{audio.suffix}"
        shutil.copy2(audio, audio_dest)

        wem_path: Path | None = None
        if self._wem_converter is not None and self._wem_converter.available():
            wem = self._wem_converter.convert(audio, out_dir / "wwise_work")
            wem_path = out_dir / "audio.wem"
            shutil.copy2(wem, wem_path)

        meta = arrangements[0].metadata
        project = {
            "title": meta.title,
            "artist": meta.artist,
            "album": meta.album,
            "year": meta.year,
            "audio": audio_dest.name,
            "audio_wem": wem_path.name if wem_path else None,
            "arrangements": [p.name for p in xml_paths],
            "vocals": vocals_path.name if vocals_path else None,
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
                "Import into DLC Builder (https://github.com/iminashi/Rocksmith2014.NET) "
                "to convert audio via Wwise and pack the final PSARC."
            ),
        }
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
