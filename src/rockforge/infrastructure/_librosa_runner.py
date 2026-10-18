"""The librosa measurements, as functions AND as a standalone script.

librosa is the one ML stage RockForge did NOT already run out-of-process:
Demucs, WhisperX and Banquet are all subprocesses, but tone analysis, the
per-point tempo ("Corrigir daqui") and the tuning proposal imported librosa
directly. That is what kept them out of the standalone `.exe`, which has its
own Python and can never import the user's packages.

So this module is written to be usable **both ways**, with one implementation
of each measurement:

- imported and called directly, when the running process has librosa
  (``start.bat``) — no subprocess cost on a per-click tool;
- executed as a script by another interpreter (``ml_python.run_json``), when it
  does not (the `.exe`).

It therefore imports NOTHING from ``rockforge`` — same rule as
``_whisperx_runner.py`` and ``_demucs_patcher.py``, and the reason it can be
run by an interpreter that has librosa but has never heard of RockForge.

Each function returns plain floats (a JSON-able dict for the tone features), so
the two transports cannot disagree about anything but the transport.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def tempo_from(audio: str, start_s: float, expected_bpm: float | None = None) -> float:
    """Estimate the recording's tempo (BPM) from ``start_s`` to the end.

    ``expected_bpm`` is passed to librosa as ``start_bpm``. This matters a lot:
    librosa's estimator weights the autocorrelation peaks by a log-normal prior
    centred on ``start_bpm``, which defaults to **120**. Left at that default the
    prior systematically pulls the answer toward 120 — a song at 70 reads as 140,
    the "always a higher tempo, never a lower one" bias — and the re-tempo then
    compresses the tail and the chart runs fast. The caller already knows what
    the chart plays at the clicked point, so centring the prior there asks the
    narrow question ("is the recording faster or slower than this?") instead of
    the open one librosa answers badly.
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(audio, sr=None, mono=True, offset=max(0.0, start_s))
    if len(y) == 0:
        raise ValueError("no audio after the requested start point")
    kwargs = {"start_bpm": float(expected_bpm)} if expected_bpm and expected_bpm > 0 else {}
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, **kwargs)
    return float(np.atleast_1d(tempo)[0])


def tuning_cents(audio: str) -> float:
    """The recording's reference-pitch deviation from A440, in cents."""
    import librosa

    y, sr = librosa.load(audio, sr=None, mono=True)
    return float(librosa.estimate_tuning(y=y, sr=sr)) * 100.0


# Per-window analysis ("tone over time"): long enough to hold a few notes, so
# a window's crest factor still sees attacks and decay; one-second steps, fine
# enough to find where a section changes character.
WINDOW_S = 4.0
HOP_S = 1.0
# A window counts as "the guitar is playing" when this share of its frames is
# above the song's activity threshold (30% of the peak RMS, as for the song).
WINDOW_ACTIVE_SHARE = 0.4


def _frame_features(y: Any, sr: int) -> tuple[dict[str, Any], Any, int]:
    """Frame-level features of a peak-normalized signal, frame counts aligned."""
    import librosa
    import numpy as np

    peak = float(np.max(np.abs(y)))
    if peak > 0:
        y = y / peak
    rms = librosa.feature.rms(y=y)[0]
    zcr = librosa.feature.zero_crossing_rate(y=y)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
    flatness = librosa.feature.spectral_flatness(y=y)[0]
    n = min(len(rms), len(zcr), len(centroid), len(rolloff), len(flatness), contrast.shape[1])
    frames = {
        "rms": rms[:n], "zcr": zcr[:n], "centroid": centroid[:n],
        "contrast": contrast[:, :n].mean(axis=0), "rolloff": rolloff[:n],
        "flatness": flatness[:n],
    }
    peak_rms = float(np.max(frames["rms"])) if n else 0.0
    # Frames where the guitar is actually playing — above 30% of the peak RMS —
    # so silence, count-ins and clean breaks don't pull the estimate toward clean.
    active = frames["rms"] >= 0.3 * peak_rms if peak_rms > 0 else np.ones(n, dtype=bool)
    return frames, active, n


def _summarize(frames: dict[str, Any], mask: Any) -> dict[str, float]:
    """The feature means over the frames in ``mask`` (the ToneProfile inputs)."""
    import numpy as np

    act_rms = frames["rms"][mask]
    mean_rms = float(np.mean(act_rms))
    return {
        "zcr": float(np.mean(frames["zcr"][mask])),
        "centroid": float(np.mean(frames["centroid"][mask])),
        "contrast": float(np.mean(frames["contrast"][mask])),
        "rolloff": float(np.mean(frames["rolloff"][mask])),
        "flatness": float(np.mean(frames["flatness"][mask])),
        # Crest factor over the active region: clean, transient picking keeps
        # peaks well above the average (~3-6); heavy distortion sustains and
        # compresses it toward ~1.5-2.5. Low crest ⇒ compressed ⇒ distorted.
        "crest": float(np.max(act_rms)) / (mean_rms + 1e-8),
        "rms_std_ratio": float(np.std(act_rms)) / (mean_rms + 1e-8),
    }


def tone_features(audio: str) -> dict[str, float]:
    """The spectral features a guitar tone is classified from (whole song).

    Only the MEASUREMENT lives here; mapping these to a ``ToneProfile`` is pure
    and stays in ``tone_analysis/analyzer.py`` where CI can test it without an
    ML stack.
    """
    return tone_report(audio)["features"]  # type: ignore[return-value]


def tone_report(audio: str) -> dict[str, object]:
    """The whole-song features AND the same features window by window, from one
    read of the audio: ``{"features": {...}, "windows": [{"t", "active", ...}]}``.
    ``t`` is the window's centre in seconds of this file."""
    import librosa
    import numpy as np

    y, sr = librosa.load(audio, sr=None, mono=True)
    if len(y) == 0:
        raise ValueError("empty audio file")
    frames, active, n = _frame_features(y, sr)
    if not bool(active.any()):
        active = np.ones(n, dtype=bool)
    features = _summarize(frames, active)

    times = librosa.frames_to_time(np.arange(n), sr=sr)
    duration = float(len(y)) / sr
    windows: list[dict[str, float]] = []
    start = 0.0
    while start < duration:
        in_win = (times >= start) & (times < start + WINDOW_S)
        if bool(in_win.any()):
            win_active = in_win & active
            share = float(win_active.sum()) / float(in_win.sum())
            mask = win_active if bool(win_active.any()) else in_win
            windows.append({
                "t": round(min(start + WINDOW_S / 2, duration), 3),
                "active": 1.0 if share >= WINDOW_ACTIVE_SHARE else 0.0,
                **{k: round(v, 5) for k, v in _summarize(frames, mask).items()},
            })
        start += HOP_S
    return {"features": features, "windows": windows}


# ── Variable-tempo alignment (EXPERIMENTAL) ─────────────────────────────────
# The chart already knows what the recording is supposed to play: how many
# beats, where each note falls inside its beat. What it does not know is WHEN,
# once the recording's tempo wanders away from the written one. So instead of
# asking "where are the beats?" (the open question the removed whole-song
# estimators answered badly — wrong metrical level, corrections everywhere),
# this asks the narrow one: keeping the chart's own beats in order, how must
# each one move so that the notes land on attacks heard in the recording,
# with a tempo that changes slowly? The number of beats can never change, so
# the metrical level cannot be misread. A beam search over the beats, in plain
# Python (no numpy), so CI can test it without the ML stack.
ALIGN_HOP_S = 0.01           # the onset envelope's frame, in seconds
ALIGN_RATIO = (0.80, 1.25)   # a beat may last this much less/more than shown now
ALIGN_SMOOTH = 0.03          # a 3 % tempo change from one beat to the next costs
                             # as much as one note landing on a full attack
ALIGN_BEAM = 48              # states kept per beat
ALIGN_START_S = 0.25         # the first beat is searched this far around where it shows
ALIGN_GAP_BEATS = 4          # beats without a note before one that is flagged to check
ALIGN_BEAT_WEIGHT = 0.35     # an attack on a beat with no note of the chart still counts a little


def _normalized(env: list[float]) -> list[float]:
    """The envelope scaled by its 95th percentile (one loud hit cannot flatten
    the rest), capped, then widened by one frame each side so an attack a frame
    off still counts."""
    if not env:
        return []
    ranked = sorted(env)
    ref = ranked[int(0.95 * (len(ranked) - 1))] or max(ranked) or 1.0
    e = [min(v / ref, 1.5) for v in env]
    return [max(e[max(0, i - 1):i + 2]) for i in range(len(e))]


def align_beats(
    env: list[float],
    hop: float,
    beats: list[float],
    notes: list[float],
    *,
    beam: int = ALIGN_BEAM,
    start_window: float = ALIGN_START_S,
) -> dict[str, object]:
    """Move each chart beat (``beats``, seconds of the recording as the chart
    shows them now, ascending) to where the recording plays it, given the
    recording's onset envelope ``env`` (one value per ``hop`` seconds) and the
    chart's note onsets ``notes`` (same clock). Returns the new beat times,
    each beat's ``support`` (how strongly the notes after it land on attacks,
    0..1.5, None for a beat with no note) and the mean note evidence before
    and after, so the caller can say when nothing improved."""
    import bisect
    import math

    n = len(beats)
    if n < 2:
        raise ValueError("need at least two beats to align")
    e = _normalized(env)

    def ev(t: float) -> float:
        i = int(round(t / hop))
        return e[i] if 0 <= i < len(e) else 0.0

    # Each note as (beat, fraction of the way to the next beat); one on a beat
    # counts for that beat.
    seg: list[list[float]] = [[] for _ in range(n - 1)]
    on_beat = [0] * n
    for t in notes:
        k = bisect.bisect_right(beats, t) - 1
        if k < 0 or k >= n - 1:
            if k == n - 1 and abs(t - beats[-1]) < 0.02:
                on_beat[-1] += 1
            continue
        frac = (t - beats[k]) / (beats[k + 1] - beats[k])
        if frac < 0.02:
            on_beat[k] += 1
        elif frac > 0.98:
            on_beat[k + 1] += 1
        else:
            seg[k].append(frac)

    def beat_gain(i: int, t: float) -> float:
        return ev(t) * (on_beat[i] + ALIGN_BEAT_WEIGHT)

    # A state: (score, time of this beat, stretch of the segment that led here,
    # index of the parent state in the previous beat's list).
    frames0 = range(
        max(0, math.ceil((beats[0] - start_window) / hop)),
        math.floor((beats[0] + start_window) / hop) + 1,
    )
    states = [
        (beat_gain(0, f * hop) - ((f * hop - beats[0]) / start_window) ** 2, f * hop, 1.0, -1)
        for f in frames0
    ] or [(0.0, beats[0], 1.0, -1)]
    states.sort(key=lambda s: -s[0])
    states = states[:beam]
    history = [states]
    lo_r, hi_r = ALIGN_RATIO
    for i in range(n - 1):
        d = beats[i + 1] - beats[i]
        fracs = seg[i]
        best: dict[tuple[int, int], tuple[float, float, float, int]] = {}
        for p, (score, t, s, _) in enumerate(states):
            f_lo = math.ceil((t + d * lo_r) / hop)
            f_hi = math.floor((t + d * hi_r) / hop)
            for f in range(f_lo, f_hi + 1):
                t2 = f * hop
                r = (t2 - t) / d
                sc = score + beat_gain(i + 1, t2) - (math.log(r / s) / ALIGN_SMOOTH) ** 2
                for frac in fracs:
                    sc += ev(t + frac * (t2 - t))
                key = (f, round(math.log(r) / 0.01))
                old = best.get(key)
                if old is None or sc > old[0]:
                    best[key] = (sc, t2, r, p)
        states = sorted(best.values(), key=lambda s: -s[0])[:beam]
        history.append(states)

    times = [0.0] * n
    k = 0
    for i in range(n - 1, -1, -1):
        st = history[i][k]
        times[i] = st[1]
        k = st[3]

    def note_times(bt: list[float]) -> list[tuple[int, float]]:
        out = [(i, bt[i]) for i in range(n) for _ in range(on_beat[i])]
        for i, fr in enumerate(seg):
            out += [(i, bt[i] + x * (bt[i + 1] - bt[i])) for x in fr]
        return out

    after = note_times(times)
    support: list[float | None] = [None] * n
    per: list[list[float]] = [[] for _ in range(n)]
    for i, t in after:
        per[i].append(ev(t))
    for i, vals in enumerate(per):
        if vals:
            support[i] = round(sum(vals) / len(vals), 3)
    # Where the recording was silent for the chart (a bar of rests or more),
    # nothing held the tempo, and the first beat with notes again can lock a
    # whole subdivision off while looking perfectly supported — the one
    # failure the measurements could not rule out. Those beats are named for
    # the user to check by ear.
    after_gap = []
    last = -1
    for i in range(n):
        if per[i]:
            if last >= 0 and i - last >= ALIGN_GAP_BEATS:
                after_gap.append(i)
            last = i
    before = note_times(list(beats))
    ratios = [(times[i + 1] - times[i]) / (beats[i + 1] - beats[i]) for i in range(n - 1)]
    return {
        "times": [round(t, 4) for t in times],
        "support": support,
        "after_gap": after_gap,
        "evidence_before": round(sum(ev(t) for _, t in before) / max(1, len(before)), 3),
        "evidence_after": round(sum(ev(t) for _, t in after) / max(1, len(after)), 3),
        "ratio_min": round(min(ratios), 3),
        "ratio_max": round(max(ratios), 3),
    }


def onset_envelope(
    audio: str, hop: float = ALIGN_HOP_S, floor_db: float | None = None
) -> tuple[list[float], float]:
    """The recording's onset strength, one value per ``hop`` seconds. With
    ``floor_db``, every mel band is read no lower than that many dB under the
    file's loudest (librosa's own floor is 80 dB)."""
    import librosa
    import numpy as np

    y, rate = librosa.load(audio, sr=22050, mono=True)
    if len(y) == 0:
        raise ValueError("empty audio file")
    sr = int(rate)
    hop_len = max(1, int(round(hop * sr)))
    if floor_db:
        mel = librosa.feature.melspectrogram(y=y, sr=sr, hop_length=hop_len)
        db = librosa.power_to_db(mel, ref=np.max, top_db=floor_db)
        env = librosa.onset.onset_strength(S=db, sr=sr, hop_length=hop_len)
    else:
        env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_len)
    return [float(v) for v in np.asarray(env)], hop_len / sr


# Picking the attacks out of the onset envelope, for the score's "Ataques da
# gravação" lane. The envelope is librosa's spectral flux (energy that is NEW in
# a 10 ms frame), not the waveform's amplitude: a distorted guitar is compressed
# so hard that its level barely dips between strums, while each pick still
# brings a burst of new spectrum. A frame is an attack when it is the highest
# within ATTACK_MIN_GAP_S, stands ATTACK_RATIO times above the envelope's
# MEDIAN around it (ATTACK_LOCAL_S each side — the median, not the mean, so a
# dense riff's own hits do not raise the floor they are measured against, and
# steady noise, whose peaks sit close to its median, gives none), and reaches
# ATTACK_MIN of the envelope's 95th percentile. The first ATTACK_EDGE_S are
# skipped: librosa pads the start with silence, so the noise floor of a
# recording that does not open on digital silence reads as an attack there.
ATTACK_MIN_GAP_S = 0.05
ATTACK_LOCAL_S = 0.25
ATTACK_RATIO = 2.0
ATTACK_MIN = 0.3
ATTACK_EDGE_S = 0.1
# A separated instrument still carries a little of the others (Demucs leaves
# some behind), and in decibels a hi-hat 30 dB down in bands the bass never
# reaches is as much NEW energy as the bass itself — librosa averages the flux
# over every mel band, and the residue fills many more of them. Reading the
# bands no lower than this under the stem's loudest drops that residue. On
# synthesized songs (drums, bass, distorted guitar, voice; a stem = the
# instrument plus 3 % of the rest), strong attacks with no note per note of an
# in-sync chart: bass 0.87 → 0.01, guitar 0.39 → 0.01, no real attack lost.
# Not used on the mix: what is quiet there is music, not residue.
ATTACK_STEM_FLOOR_DB = 40.0


def pick_attacks(env: list[float], hop: float) -> list[list[float]]:
    """``[[time, strength], …]`` — each attack's instant (seconds) and its
    strength relative to the envelope's 95th percentile, capped at 1."""
    if not env:
        return []
    ranked = sorted(env)
    ref = ranked[int(0.95 * (len(ranked) - 1))] or max(ranked) or 1.0
    e = [v / ref for v in env]
    n = len(e)
    gap = max(1, int(round(ATTACK_MIN_GAP_S / hop)))
    local = max(1, int(round(ATTACK_LOCAL_S / hop)))
    edge = int(round(ATTACK_EDGE_S / hop))
    out: list[list[float]] = []
    for i, v in enumerate(e):
        if v < ATTACK_MIN or i < edge:
            continue
        lo, hi = max(0, i - gap), min(n, i + gap + 1)
        if v < max(e[lo:hi]) or any(e[j] == v for j in range(lo, i)):
            continue  # not the peak (the first of equal peaks wins)
        around = sorted(e[max(0, i - local):min(n, i + local + 1)])
        if v < around[len(around) // 2] * ATTACK_RATIO:
            continue
        out.append([round(i * hop, 3), round(min(1.0, v), 3)])
    return out


def attacks(audio: str, separated: bool = False) -> dict[str, object]:
    """The recording's attacks (``pick_attacks``) and its length. ``separated``:
    ``audio`` is one instrument out of a separation (``ATTACK_STEM_FLOOR_DB``)."""
    env, hop = onset_envelope(audio, floor_db=ATTACK_STEM_FLOOR_DB if separated else None)
    return {"attacks": pick_attacks(env, hop), "duration": round(len(env) * hop, 3)}


# The score's "Barras de áudio" in their "Ataques" mode: the same envelope the
# attacks are picked from, every frame kept, so a strike stands up as a narrow
# bar even in a distorted guitar whose LEVEL barely dips between strums. Scaled
# to the envelope's 99th percentile (an onset envelope is spiky: its loudest
# frames are single strikes, the 99th still leaves the soft ones visible) and
# sent as whole percents — a song's 24 000 frames as a small answer.
LEVEL_REF_PCT = 0.99


def level_values(env: list[float], hop: float) -> list[int]:
    """Each frame of ``env`` as 0-100, 100 = the envelope's 99th percentile or
    more; the first ``ATTACK_EDGE_S`` are 0 (librosa's padded start, as in
    ``pick_attacks``)."""
    if not env:
        return []
    edge = min(len(env), int(round(ATTACK_EDGE_S / hop)))
    env = [0.0] * edge + list(env[edge:])
    ranked = sorted(env)
    ref = ranked[int(LEVEL_REF_PCT * (len(ranked) - 1))] or ranked[-1] or 1.0
    return [max(0, min(100, int(round(100 * v / ref)))) for v in env]


def onset_levels(audio: str, separated: bool = False) -> dict[str, object]:
    """``level_values`` of ``audio``'s onset envelope, its frame length and the
    file's length. ``separated`` as in ``attacks``."""
    env, hop = onset_envelope(audio, floor_db=ATTACK_STEM_FLOOR_DB if separated else None)
    return {"values": level_values(env, hop), "hop": hop, "duration": round(len(env) * hop, 3)}


def beat_align(audio: str, spec_path: str) -> dict[str, object]:
    """``align_beats`` on ``audio``, with the beats and notes read from a JSON
    file (``{"beats": [...], "notes": [...]}``) — too long for a command line."""
    with open(spec_path, encoding="utf-8") as fh:
        spec = json.load(fh)
    env, hop = onset_envelope(audio)
    result = align_beats(env, hop, [float(x) for x in spec["beats"]],
                         [float(x) for x in spec.get("notes", [])])
    result["duration"] = round(len(env) * hop, 3)
    return result


def main(argv: list[str] | None = None) -> int:
    """Print ONE line of JSON on stdout. ``ml_python.run_json`` reads the last
    line, so librosa's own warnings on stderr (or a chatty backend on stdout)
    cannot corrupt the answer."""
    parser = argparse.ArgumentParser(description="librosa measurements for RockForge")
    parser.add_argument(
        "command", choices=("tempo", "tuning", "tone", "beatalign", "attacks", "levels")
    )
    parser.add_argument("--audio", required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--expected-bpm", type=float, default=0.0)
    parser.add_argument("--spec", default="")
    parser.add_argument("--separated", type=float, default=0.0)  # 1 = a separated instrument
    args = parser.parse_args(argv)

    if args.command == "tempo":
        result: dict[str, object] = {
            "bpm": tempo_from(args.audio, args.start, args.expected_bpm or None)
        }
    elif args.command == "beatalign":
        result = beat_align(args.audio, args.spec)
    elif args.command == "attacks":
        result = attacks(args.audio, separated=bool(args.separated))
    elif args.command == "levels":
        result = onset_levels(args.audio, separated=bool(args.separated))
    elif args.command == "tuning":
        result = {"cents": tuning_cents(args.audio)}
    else:
        result = tone_report(args.audio)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    # Run as a script, this file's folder is sys.path[0], and it holds
    # RockForge's own ``packaging`` package — which then stands in for the pip
    # ``packaging`` librosa imports (``No module named 'packaging.version'``).
    # Nothing here is imported from that folder.
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != here]
    sys.exit(main())
