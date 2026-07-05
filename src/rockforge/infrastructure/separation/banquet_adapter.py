"""EXPERIMENTAL / IN TESTING — finer stem separation via Banquet (query-bandit).

Banquet (Watcharasupat & Lerch, arXiv 2406.18747, MIT) is a query-based source
separator trained on MoisesDB, which labels **electric**, **acoustic**, **clean**
and **distorted** guitars as distinct classes. It beats htdemucs_6s on the guitar
stem and, being query-based, can isolate a *narrow class* by example: you give it
a short reference clip of the target sound (``--query_path``) and it extracts that
class from the mixture.

This adapter is a drop-in `StemSeparator` for `POST /jobs/{id}/separate-stems`,
selected with ``ROCKFORGE_STEM_SEPARATOR=banquet``. It shells out to the repo's
native ``train.py inference_byoq`` (same subprocess discipline as the Demucs
adapter) once per reference clip found in ``banquet_queries``, producing one stem
per clip (named after the clip's filename).

Honest limit (unchanged from Demucs): separation is by instrument **class**, not
by track/role. Two guitars of the *same* class playing at once (Lead + Rhythm,
both distorted) still cannot be split — there is no spectral cue to tell them
apart. Banquet only helps when the guitars differ in class (e.g. one acoustic,
one distorted electric).

Setup (see TESTING.md §Banquet): clone the repo, download ``ev-pre-aug.ckpt``
from Zenodo, and drop one ``<class>.wav`` reference clip per stem you want into
the queries dir. Requires PyTorch; a CUDA GPU is strongly recommended.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rockforge.domain.errors import SeparationError

BANQUET_TIMEOUT_S = 3600  # per-query inference; longer than Demucs (bigger model, per-class passes)


class BanquetSeparator:
    """Implements rockforge.application.ports.StemSeparator via the query-bandit CLI."""

    def __init__(
        self,
        repo: Path | None,
        ckpt: Path | None,
        queries_dir: Path | None,
        device: str = "cpu",
        batch_size: int = 4,
    ) -> None:
        self._repo = repo
        self._ckpt = ckpt
        self._queries_dir = queries_dir
        self._device = device
        self._batch_size = batch_size

    def _require_setup(self) -> tuple[Path, Path, Path]:
        if not self._repo or not (self._repo / "train.py").exists():
            raise SeparationError(
                "Banquet repo not configured — set ROCKFORGE_BANQUET_REPO to a cloned "
                "kwatcharasupat/query-bandit (see TESTING.md §Banquet)"
            )
        if not self._ckpt or not self._ckpt.exists():
            raise SeparationError(
                "Banquet checkpoint not found — set ROCKFORGE_BANQUET_CKPT (e.g. ev-pre-aug.ckpt)"
            )
        if not self._queries_dir or not self._queries_dir.is_dir():
            raise SeparationError(
                "Banquet query clips not found — set ROCKFORGE_BANQUET_QUERIES to a dir of "
                "<class>.wav reference clips"
            )
        return self._repo, self._ckpt, self._queries_dir

    def _run_query(self, audio: Path, query: Path, target: Path) -> None:
        repo, ckpt, _ = self._repo, self._ckpt, self._queries_dir
        assert repo is not None and ckpt is not None  # _require_setup ran
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable, "train.py", "inference_byoq",
            f"--ckpt_path={ckpt}",
            f"--input_path={audio}",
            f"--output_path={target}",
            f"--query_path={query}",
            f"--batch_size={self._batch_size}",
            f"--use_cuda={'true' if self._device == 'cuda' else 'false'}",
        ]
        try:
            # stdin=DEVNULL: never inherit the worker console's stdin (mirrors the
            # Demucs adapter — an inherited stdin can block a CLI subprocess).
            subprocess.run(
                cmd, check=True, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=BANQUET_TIMEOUT_S, cwd=repo,
            )
        except FileNotFoundError as exc:
            raise SeparationError(
                "python/query-bandit not runnable — check the Banquet install (PyTorch)"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise SeparationError(
                f"Banquet timed out after {BANQUET_TIMEOUT_S}s on {query.stem}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise SeparationError(f"Banquet failed on {query.stem}: {exc.stderr[-2000:]}") from exc

    def separate_stems(self, audio: Path, workdir: Path) -> dict[str, Path]:
        """Extract one stem per reference clip in the queries dir — ``{clip stem:
        path}`` (e.g. ``{'electric_guitar': …, 'acoustic_guitar': …, 'bass': …}``).
        One query-bandit pass per clip; the stem is named after the clip file."""
        _, _, queries_dir = self._require_setup()
        queries = sorted(queries_dir.glob("*.wav"))
        if not queries:
            raise SeparationError(f"no Banquet query clips (*.wav) in {queries_dir}")
        out_dir = workdir / "banquet"
        stems: dict[str, Path] = {}
        for query in queries:
            target = out_dir / f"{query.stem}.wav"
            self._run_query(audio, query, target)
            if target.exists():
                stems[query.stem] = target
        if not stems:
            raise SeparationError("Banquet produced no stems — check the queries and checkpoint")
        return stems

    def separate_guitar(self, audio: Path, workdir: Path) -> Path:
        """Aggregated guitar stem (StemSeparator port): runs the first query whose
        name looks like a guitar (``*guitar*`` / ``*electric*``)."""
        _, _, queries_dir = self._require_setup()
        guitar_q = next(
            (q for q in sorted(queries_dir.glob("*.wav"))
             if "guitar" in q.stem.lower() or "electric" in q.stem.lower()),
            None,
        )
        if guitar_q is None:
            raise SeparationError(
                f"no guitar query clip (*guitar*.wav / *electric*.wav) in {queries_dir}"
            )
        target = workdir / "banquet" / "guitar.wav"
        self._run_query(audio, guitar_q, target)
        if not target.exists():
            raise SeparationError(f"expected Banquet guitar stem not produced at {target}")
        return target
