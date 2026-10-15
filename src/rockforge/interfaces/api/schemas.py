"""The API's request and response models.

Kept apart from app.py (and from the endpoint groups in routers/) because the
API tests reload app.py: a model defined there is created again on every
reload, and a model of another module that names it in a field would then
refuse the new class's instances. A module nothing reloads has one of each."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

PIPELINE_STAGES = [
    "ingest", "normalize", "parse_gp", "build_arrangements", "lyrics", "package",
]


# Every float a CLIENT can send goes through this, never a bare ``float``.
# JSON carries the literals ``NaN`` and ``Infinity``, Pydantic accepts them in a
# float by default, and ``NaN <= 0`` is False — so the ``tempo_scale <= 0`` guard
# waved NaN straight through, the job forked, the value was persisted into the
# JSON params column, and the build only failed much later with an error that
# pointed nowhere. ``_build_time_warp`` propagates a NaN silently across the
# whole timeline. Rejecting it at the boundary is the project's own convention:
# surface the error where the bad value entered, never default silently.
Finite = Annotated[float, Field(allow_inf_nan=False)]


# A string's open-string pitch. The length check stays an explicit 422 (it needs
# a message naming the six strings), but the RANGE belongs here: an absurd pitch
# used to reach the SNG writer, where the semitone offset is packed as an int16
# and died as a `struct.error` pointing at nothing.
MidiPitch = Annotated[int, Field(ge=0, le=127)]


# How far the recording sits from A440, in cents. Past ±50 it is closer to the
# next semitone, which is a TUNING (Editar info), not a deviation; the detector
# itself answers inside ±50 (librosa's estimate_tuning is in ±0.5 bins).
MAX_CENT_OFFSET = 50.0


CentOffset = Annotated[
    float, Field(ge=-MAX_CENT_OFFSET, le=MAX_CENT_OFFSET, allow_inf_nan=False)
]


class JobOut(BaseModel):
    id: str
    status: str
    stage: str | None
    stages: list[str] = PIPELINE_STAGES
    title: str
    artist: str
    album: str
    year: int | None
    created_at: str
    warnings: list[str]
    note_counts: dict[str, int]
    psarc_available: bool
    bundle_available: bool
    source_type: str
    offset_s: float
    lead_in_s: float = 0.0
    tempo_scale: float
    import_mutes: bool
    dynamic_difficulty: bool = True
    error: str | None
    lyrics_status: str = "none"
    tone_detection_status: str = "none"
    cover_art: bool = False
    # Completeness signals for the "Estado do PSARC" checklist. has_tones: the
    # user defined at least one custom tone (else DLC Builder flags "tone
    # missing"). sync_edited: at least one sync adjustment was made (offset moved
    # off 0, tempo scaled, or a drift anchor placed) — drives the soft
    # "confirmaste a sincronização?" reminder. Both GP-only.
    has_tones: bool = False
    sync_edited: bool = False
    # The user said "it is in sync" (`PATCH /jobs/{id}/sync-confirmed`). A song
    # that needed no adjustment — synced in Guitar Pro 8, its embedded audio, or
    # simply right from the start — has nothing for `sync_edited` to see, so
    # without this the reminder could never be cleared.
    sync_confirmed: bool = False
    # The chart whose sync corrections the viewer carries onto the others
    # ("Pista principal"); None = each chart on its own.
    sync_main: str | None = None
    # Why the chart counts as in sync, for the badge on the project card and the
    # score: "confirmed" (the user said so), "gp" (synced in Guitar Pro 8 — the
    # file carries its own sync points), "songsterr" (human-marked bar times),
    # "adjusted" (corrected here, not yet confirmed) or None.
    sync_source: str | None = None
    # The charts the user marked as in sync, one by one (their tabs turn green).
    synced_arrangements: list[str] = []
    # The recording is the audio the Guitar Pro file carries (its own copy, the
    # one its sync points describe), not a separate upload.
    recording_from_gp: bool = False
    # True if the bundle carries lyrics from ANY source — edited/GP-embedded
    # events, an LRC/UltraStar file, or completed WhisperX detection — not just
    # `lyrics_status == "ready"` (which only covers detection).
    has_lyrics: bool = False
    # The job this one was forked from (rebuild / reload-gp / import-sync). Lets the
    # UI offer "previous version" so an iterative sync can be walked back — the older
    # job (and its bundle) is never deleted on a rebuild.
    rebuilt_from: str | None = None
    # Is this song in the game's dlc folder ("Instalar no jogo")? "this" = this
    # version's PSARC, "older" = a copy installed from an earlier version (a
    # rebuild inherits the record), None = not installed or since deleted.
    in_game: str | None = None
    in_game_path: str | None = None


class OtherSyncIn(BaseModel):
    tempo_scale: Finite | None = None
    sync_anchors: list[tuple[Finite, Finite]] = []


class RebuildIn(BaseModel):
    """Human-review overrides for a rebuild (sync, tuning, tones, lyrics, note edits)."""

    # How far the recording is from A440, for every chart (one recording); None
    # leaves the stored value. The strings' own tuning is per chart, in
    # tuning_overrides below ("Editar info").
    cent_offset: CentOffset | None = None
    offset_s: Finite | None = None  # GP sync: second in the recording where the song starts
    lead_in_s: Finite | None = None  # GP: extra intro silence prepended (pushes the song later)
    tempo_scale: Finite | None = None  # GP sync: stretch/compress the whole chart timeline
    # Manual drift-correction points: (chart_time_s, corrected_time_s) pairs, in the
    # chart's already-shifted timeline (as shown in the tab viewer).
    sync_anchors: list[tuple[Finite, Finite]] | None = None
    # When set (ArrangementKind value, e.g. "Lead"/"Rhythm"/"Combined"), tempo_scale
    # and sync_anchors are scoped to that arrangement alone instead of all of them.
    arrangement: str | None = None
    # When True (with arrangement set), tempo_scale and sync_anchors are applied
    # to every arrangement that has notes, not just the specified one.
    apply_to_all: bool = False
    # The OTHER charts' pending sync, committed in the same rebuild (keyed like
    # arrangement). Before it only the chart on screen was sent, so another
    # tab's pending corrections — and what the "Pista principal" carries onto
    # the others — were lost. Ignored with apply_to_all.
    other_sync: dict[str, OtherSyncIn] | None = None
    # GP: when False, palm mute / slap / pop / tap are stripped (plain notes).
    import_mutes: bool | None = None
    # When False, the native PSARC's SNG is a single full-chart level (no DD).
    dynamic_difficulty: bool | None = None
    # GP: re-assign which GP track feeds which arrangement, post-creation. Keys are
    # "lead"/"rhythm"/"combo"/"alt_lead"/"alt_rhythm"; a value is the track index,
    # or null to clear that slot. When set (even to {}), it REPLACES the whole
    # track assignment. None leaves it unchanged.
    tracks: dict[str, int | None] | None = None
    # GP: per-arrangement tuning override, keyed by ArrangementKind value
    # ("Lead"/"Rhythm"/…) → the six MIDI pitches (low to high). When set (even to
    # {}), replaces params["tuning_overrides"]; None leaves it untouched.
    tuning_overrides: dict[str, list[MidiPitch]] | None = None
    # Edited per-word lyrics from the in-app lyrics editor. When set (even to an
    # empty list), replaces params["lyrics_events"] and clears lyrics_status so
    # the next build uses the edited lyrics. None leaves existing lyrics alone.
    lyrics_events: list[LyricEventOut] | None = None
    # Whether the lyric rows move with the chart's sync corrections (lyrics timed
    # on the score) or stay put (timed to the recording). None leaves it alone.
    lyrics_follow_chart: bool | None = None
    # Tone editor overrides (GP jobs). When set (even to an empty list), each
    # replaces the corresponding params entry; None leaves it untouched.
    # ``tones`` are full gear definitions (see gear_catalogue.tone_from_dict);
    # ``tone_base``/``tone_names`` reference them by key; ``tone_changes`` are the
    # timed switches placed on the partitura.
    tone_base: str | None = None
    tone_names: list[str] | None = None
    tones: list[dict[str, Any]] | None = None
    tone_changes: list[ToneChangeIn] | None = None
    # Each track's own tone setup, keyed by ArrangementKind.value (the tones
    # themselves stay song-level in ``tones``). When set, REPLACES
    # params["arrangement_tones"] — {} brings every track back to the song-level
    # tone_base/tone_names/tone_changes above; None leaves it untouched.
    arrangement_tones: dict[str, ArrangementTonesIn] | None = None
    # In-app section-editor overrides (bundle-clock times, placed on the tab
    # viewer, same convention as tone_changes). When set (even to an empty
    # list), replaces the GP-parsed sections for every arrangement; None
    # leaves each arrangement's own GP-authored sections untouched.
    section_overrides: list[SectionOverrideIn] | None = None
    # In-app note-editor edits (GP jobs), keyed by ArrangementKind.value —
    # genuinely per-arrangement, unlike tone_changes/section_overrides. Each
    # entry upserts a note at (time, string), or removes it when
    # ``deleted``. When set (even to {}), REPLACES params["note_overrides"]
    # wholesale; None leaves it untouched.
    note_overrides: dict[str, list[NoteOverrideIn]] | None = None


class ArrangementTonesIn(BaseModel):
    """One track's own tone setup (see ``gp_pipeline.ArrangementTones``)."""

    tone_base: str | None = None
    tone_names: list[str] = Field(default=[], max_length=4)
    tone_changes: list[ToneChangeIn] = []


class ToneChangeIn(BaseModel):
    """A timed tone switch placed on the score. Was a free ``dict[str, Any]``,
    so its time bypassed validation entirely — same shape as the section and
    note overrides, so it gets the same treatment."""

    time: Finite
    name: str


class SectionOverrideIn(BaseModel):
    time: Finite
    name: str


class SectionOut(BaseModel):
    time: float
    name: str
    number: int


class NoteOverrideIn(BaseModel):
    time: Finite
    string: int = Field(ge=0, le=5)
    fret: int = Field(default=0, ge=0, le=24)
    sustain: Finite = 0.0
    techniques: list[str] = []
    bend_semitones: Finite = 0.0
    slide_to_fret: int | None = Field(default=None, ge=0, le=24)
    deleted: bool = False


class ArrangementNoteOut(BaseModel):
    time: float
    string: int
    fret: int
    sustain: float
    chord: bool
    techniques: list[str]
    bend_semitones: int = 0  # bend magnitude (1=half, 2=full, 3=1½…); 0 if no bend
    chord_name: str | None = None  # derived name for the chord this note belongs to
    # The fret a slide ends on (pitched, else unpitched slide-out), -1 if none —
    # the 3D highway draws the trail running to it.
    slide_to: int = -1
    # The note runs on into the next note on its string without a new pick
    # (Rocksmith's linkNext: a legato slide, a note held on).
    link_next: bool = False


class ArpeggioOut(BaseModel):
    """A run of single notes the game draws as one chord shape (an "-arp"
    hand shape), bundle-clock, with the chord it spells ("" if unnamed)."""

    start: float
    end: float
    name: str = ""


class BarOut(BaseModel):
    measure: int  # 1-based bar number
    time: float   # bundle-time position of the bar's downbeat


class ArrangementOut(BaseModel):
    kind: str
    tuning_offsets: list[int]
    # The strings the chart is drawn with: 6, or 4 for a bass (whose offsets are
    # measured from E1 A1 D2 G2, the game's own convention).
    string_count: int = 6
    cent_offset: float
    average_bpm: float
    tempo_scale: float  # this arrangement's own tempo scale (GP sync), 1.0 if none
    note_count: int
    chord_count: int
    notes: list[ArrangementNoteOut]
    bars: list[BarOut] = []  # measure downbeats for the viewer's bar numbering
    beats: list[float] = []  # ALL ebeat times (downbeats + off-beats) — the drag snap grid
    # Named song-structure markers (GP-authored, or the in-app editor's
    # overrides), bundle-clock time — the writer's synthetic trailing
    # "noguitar" end sentinel is never included here.
    sections: list[SectionOut] = []
    # The note-editor edits ALREADY COMMITTED for this arrangement (from
    # params["note_overrides"]). The viewer seeds its pending list from these, so
    # the always-send round-trip is lossless: it used to reset to {} on every job
    # open and a rebuild for any unrelated reason (a tuning change, say) then
    # sent {} and silently erased every note edit the user had applied.
    note_overrides: list[NoteOverrideIn] = []
    # The user marked THIS chart as in sync with the recording (each track is
    # synchronised on its own; its tab turns green).
    sync_confirmed: bool = False
    # How Rocksmith names this chart in game ("LEAD 1", "LEAD 2", "RHYTHM",
    # "COMBO") — numbered only when the song has two on the same path.
    game_name: str = ""
    # Bars (as ``bars`` numbers them) whose rhythm PDF-to-GP5 estimated from the
    # note spacing when it converted this track: the ones to check first.
    estimated_bars: list[int] = []
    arpeggios: list[ArpeggioOut] = []


class TempoCorrectionIn(BaseModel):
    measure: int = Field(ge=1)
    bpm: float = Field(gt=10.0, lt=400.0)


class ExportGpIn(BaseModel):
    corrections: list[TempoCorrectionIn]


class AppliedCorrectionOut(BaseModel):
    measure: int
    requested_bpm: float
    written_bpm: float
    rounded: bool


class ExportGpOut(BaseModel):
    """Report of a corrected Guitar Pro export — the file is fetched separately."""

    filename: str
    format: str
    size_bytes: int
    applied: list[AppliedCorrectionOut]
    warnings: list[str]


class ExportArrangementGpOut(BaseModel):
    """Report of a generated Guitar Pro file — the file is fetched separately."""

    filename: str
    arrangement: str
    measures: int
    notes_written: int
    notes_dropped: int
    quantized: int
    max_shift_ms: float
    warnings: list[str]


class DetectTempoIn(BaseModel):
    from_s: Finite = 0.0  # recording time to start measuring the local tempo from
    # The chart's tempo AS CURRENTLY DISPLAYED at that point (the viewer's live
    # BPM readout: authored spacing × tempo_scale × pending anchors). Optional —
    # falls back to the GP file's header tempo, which is only right for a song
    # with no tempo changes and no corrections applied yet.
    chart_bpm: Finite | None = None


class DetectTempoOut(BaseModel):
    """Local tempo measured from a point — for the per-point 're-tempo from here' tool."""

    gp_bpm: float  # the GP file's header tempo (informational)
    reference_bpm: float  # what the factor is measured against (chart_bpm, else gp_bpm)
    detected_bpm: float
    suggested_factor: float  # multiply note spacing after the point by this
    used_drum_stem: bool = False  # tempo measured on the isolated drum stem?


class DetectTuningOut(BaseModel):
    """Proposed fine-tuning correction (not applied; the user reviews then
    rebuilds). String/drop tuning is NOT detected — see librosa_adapter."""

    suggested_cent_offset: float


# Doubles as an INPUT model (RebuildIn.lyrics_events carries the in-app lyric
# editor's rows), hence the finite times.
class LyricEventOut(BaseModel):
    time: Finite
    length: Finite
    lyric: str


class DetectTonesOut(BaseModel):
    """Proposed lead + rhythm tone presets based on spectral analysis of the
    guitar stem. Not auto-applied; the user reviews in the tone editor."""

    # "none"|"detecting"|"separating"|"analyzing"|"ready"|"unavailable"
    status: str
    category: str = ""  # "clean"|"crunch"|"high_gain"
    lead: dict[str, Any] = {}
    rhythm: dict[str, Any] = {}
    # Full ranked libraries (closest first, each carrying a 0-100 "match") so the
    # user can browse several "similar tones" rather than only the top guess.
    lead_candidates: list[dict[str, Any]] = []
    rhythm_candidates: list[dict[str, Any]] = []
    profile: dict[str, Any] = {}  # detected spectral profile (gain/brightness/…)
    log: list[str] = []
    # The detection measured the tone over time too, so /tone-suggestions can
    # propose a tone per part of each track.
    has_timeline: bool = False


class ToneReasonOut(BaseModel):
    code: str  # chords, palm_mute, lead, high, ring, gain, no_audio
    value: float = 0.0


class ToneSegmentOut(BaseModel):
    name: str
    start: float  # bundle clock, as the score draws it
    end: float
    role: str  # clean / rhythm / lead / silent
    tone_key: str | None = None
    tone_name: str | None = None
    match: int = 0
    confidence: str = "low"  # high / medium / low
    reasons: list[ToneReasonOut] = []
    gain: float = 0.0
    brightness: float = 0.0
    low_end: float = 0.0


class TrackTonePlanOut(BaseModel):
    kind: str
    segments: list[ToneSegmentOut]
    base: str | None = None
    names: list[str] = []  # slots A-D, base first — what tone_names takes
    changes: list[ToneChangeIn] = []
    tones: list[dict[str, Any]] = []


class ToneSwapIn(BaseModel):
    """The user's stand-in for one suggested tone: the whole tone, where it came
    from ("project" / "library" / "collection") and, for a PSARC tone, the song
    it came from."""

    tone: dict[str, Any]
    source: Literal["project", "library", "collection"]
    label: str | None = Field(default=None, max_length=300)


class ToneSuggestionsOut(BaseModel):
    tracks: list[TrackTonePlanOut]
    # The stand-ins the user chose for suggested tones, by suggested key — kept
    # with the project (PATCH /jobs/{id}/tone-swaps) so they survive leaving it.
    swaps: dict[str, ToneSwapIn] = {}
    # The tone over time moved onto the bundle clock, [t, gain, active], for the
    # little gain curve drawn above the suggested parts.
    timeline: list[list[float]] = []


class StemsOut(BaseModel):
    """State of per-instrument stem separation. ``stems`` lists the available
    stem names (guitar/bass/drums/vocals/other/piano); each is served via
    GET /jobs/{id}/stem/{name} so the viewer can solo one while fine-tuning sync."""

    # "none"|"detecting"|"normalizing"|"separating"|"ready"|"unavailable"
    status: str
    stems: list[str] = []
    log: list[str] = []


class SettingsOut(BaseModel):
    """App settings editable from the UI (persisted in work_dir/settings.json).
    `banquet` carries per-path readiness so the UI can show ✓/✗."""

    stem_separator: str = "demucs"  # "demucs" | "banquet"
    banquet_repo: str = ""
    banquet_ckpt: str = ""
    banquet_queries: str = ""
    banquet: dict[str, Any] = {}  # repo_ok/ckpt_ok/queries_ok/query_names/ready
    # Loudness/volume target (LUFS): louder = higher (closer to 0). The audio is
    # normalized to this AND the Wwise bus volume is calibrated to it.
    loudness_target: float = -12.0
    # True when the GPU-broken marker is set (a CUDA crash tripped the whole-ML
    # -stack CPU fallback). The UI shows this + a "reactivate GPU" button so the
    # user doesn't have to hunt for the hidden marker file.
    gpu_broken: bool = False
    # ctranslate2 compute type for WhisperX ("" = pick by device). May be a
    # manual choice or auto-persisted by the GPU escalation ladder when a
    # non-default type is found to work — editable here so the user isn't stuck
    # setting/clearing the ROCKFORGE_WHISPERX_COMPUTE_TYPE env var by hand.
    whisperx_compute_type: str = ""
    # The Python the heavy ML stages (Demucs / WhisperX / librosa) are run
    # with. Empty = this very process, which is right for a Python install and
    # impossible for the frozen .exe, whose own interpreter IS the executable.
    # `ml_python` carries per-extra readiness, probed in a subprocess so this
    # process never imports torch.
    ml_python: str = ""
    ml_python_info: dict[str, Any] = {}
    # The Rocksmith 2014 folder the user set ("" = found by looking in the Steam
    # libraries, which is `rocksmith_dir_detected`). The CDLC patch is looked for
    # there and the tone collection suggests its dlc folder.
    rocksmith_dir: str = ""
    rocksmith_dir_detected: str = ""
    # Ask GitHub once a day for a newer version (infrastructure/update_check.py).
    check_updates: bool = True
    # The Wwise folder the user set ("" = ROCKFORGE_WWISE_ROOT/WWISEROOT, else
    # found where the Audiokinetic Launcher installs it: `wwise_root_detected`).
    wwise_root: str = ""
    wwise_root_detected: str = ""


class SettingsIn(BaseModel):
    stem_separator: str | None = None
    banquet_repo: str | None = None
    banquet_ckpt: str | None = None
    banquet_queries: str | None = None
    loudness_target: Finite | None = None
    # "" clears the override (falls back to ROCKFORGE_WHISPERX_COMPUTE_TYPE / by
    # device); None leaves it untouched.
    whisperx_compute_type: str | None = None
    # "" clears the override (falls back to ROCKFORGE_ML_PYTHON / this process).
    ml_python: str | None = None
    # "" clears it (back to looking in the Steam libraries).
    rocksmith_dir: str | None = None
    check_updates: bool | None = None
    # "" clears it (back to the environment / the Launcher's folder).
    wwise_root: str | None = None


class UpdateCheckOut(BaseModel):
    """A newer RockForge on GitHub. `kind` is how this copy was installed:
    "exe", "source" (a folder start.bat cannot update) or "git" (start.bat
    updates it, so the UI says nothing)."""

    enabled: bool = True
    current: str
    latest: str = ""
    newer: bool = False
    url: str = ""
    kind: str = "exe"


class ComponentsOut(BaseModel):
    """The `.exe`'s extra components (infrastructure/components.py): a private
    Python 3.11 with the ML, lyrics, YouTube and PDF packages, and Deno."""

    supported: bool = False  # only the Windows .exe installs them itself
    status: str = "idle"  # idle | running | done | error
    step: str = ""
    log: list[str] = []
    error: str = ""
    installed: dict[str, bool] = {}
    complete: bool = False
    gpu: bool = False
    home: str = ""
    declined: bool = False
    auto_install: bool = False


class LyricsOut(BaseModel):
    # "none"|"detecting"|"normalizing"|"separating"|"transcribing"|"aligning"|
    # "ready"|"empty"|"unavailable"
    status: str
    events: list[LyricEventOut]
    log: list[str] = []
    # The rows move with the chart's sync corrections (timed on the score) —
    # see _lyrics_follow_chart.
    follow_chart: bool = False


class MetadataIn(BaseModel):
    """Editable song identity for an existing job (title/artist/album/year)."""

    title: str
    artist: str
    album: str = ""
    year: int | None = None


class GpTrackOut(BaseModel):
    index: int
    name: str
    is_percussion: bool
    string_count: int
    tuning_midi: list[int]


class GpInspectOut(BaseModel):
    gp_token: str
    title: str
    artist: str
    album: str
    tempo: int
    has_lyrics: bool
    tracks: list[GpTrackOut]
    # Where bar 1 falls in the audio Guitar Pro 8 was synced to (its audio-track
    # sync points), or None. When the recording is that same file this IS the
    # offset, so the wizard pre-fills it instead of asking for a guess.
    sync_start_s: float | None = None
    # The recording a GP8 file carries inside it (its audio track), as
    # {"name", "size_bytes"}, or None. When present it is the audio the sync
    # points describe, so the wizard offers it instead of asking for an upload.
    embedded_audio: dict[str, Any] | None = None
    # When the audio GP8 was synced to is NOT inside the file, where it is: a
    # YouTube video (the wizard fetches its audio) or a file on the user's disk.
    backing_youtube_url: str | None = None
    backing_external_path: str | None = None
    # The audio track is switched off in Guitar Pro (its audio is used anyway).
    backing_disabled: bool = False
    # Set when the file was built from a Songsterr tab (/songsterr/import): the
    # link, so the wizard can fetch that song's bar times too, and what the
    # conversion could not carry over.
    songsterr_song: str | None = None
    import_warnings: list[str] = []
    # Set when the file was converted from a PDF or a picture of the tab
    # (/pdf/import, PDF-to-GP5's converter): the names of those files.
    pdf_files: list[str] = []
    # …and, per track index, the bars whose rhythm the converter estimated from
    # the note spacing, numbered as the chart plays them. The wizard hands them
    # back to /jobs/gp so the viewer can offer them for review.
    estimated_bars: dict[int, list[int]] = {}


class SongsterrVideoOut(BaseModel):
    video_id: str
    url: str
    #: None = Songsterr's default video; else "alternative"/"backing"/"solo"/…
    feature: str | None
    #: Where each measure starts in THAT video, in seconds — sent back as
    #: /jobs/gp's ``bar_times`` when the user picks this video.
    points: list[float]


class SongsterrOut(BaseModel):
    song_id: int
    revision_id: int
    title: str
    artist: str
    videos: list[SongsterrVideoOut]


class YouTubeAudioIn(BaseModel):
    video_id: str = Field(max_length=20)
    #: A browser on this machine whose YouTube login yt-dlp may reuse, for when
    #: YouTube refuses an anonymous download.
    cookies_browser: str | None = Field(default=None, max_length=20)


class YouTubeAudioOut(BaseModel):
    audio_token: str
    name: str
    size_bytes: int


class SongsterrImportIn(BaseModel):
    song: str = Field(max_length=500)


class AlbumCandidateOut(BaseModel):
    source: str
    album: str
    artist: str
    year: int | None
    cover_url: str | None
    thumb_url: str | None
    track: str
    kind: str


class AlbumLookupOut(BaseModel):
    candidates: list[AlbumCandidateOut]
    #: What was actually searched (the main artist, the title without a
    #: featuring credit), so "nothing found" can say for what.
    searched_title: str = ""
    searched_artist: str = ""
    #: A service that could not be asked — its silence is not "not there".
    failures: list[str] = []


class SyncStateOut(BaseModel):
    version: int
    song: str
    sync: dict[str, object]


class SyncStateIn(BaseModel):
    version: int | None = None
    sync: dict[str, object]


class AlignLineIn(BaseModel):
    #: Where the line is believed to start (un-padded recording clock); None
    #: for plain lyrics with no timing at all.
    time: Finite | None = Field(default=None, ge=0)
    text: str = Field(max_length=500)


class DetectLyricsIn(BaseModel):
    """Optional: KNOWN lyrics to place on the recording instead of transcribing."""

    align_lines: list[AlignLineIn] = Field(default_factory=list, max_length=2000)
    #: WhisperX alignment-model language; guessed from the words when omitted.
    language: str | None = Field(default=None, pattern=r"^[a-z]{2,3}$")


class LyricsCandidateOut(BaseModel):
    id: int
    track: str
    artist: str
    album: str
    duration: float | None
    synced: str | None
    plain: str | None
    instrumental: bool


class LyricsLookupOut(BaseModel):
    candidates: list[LyricsCandidateOut]
    searched_title: str = ""
    searched_artist: str = ""


class LyricsParseIn(BaseModel):
    text: str = Field(max_length=200_000)
    offset_s: Finite = 0.0


class LyricsParseOut(BaseModel):
    events: list[LyricEventOut]


class VocalNoteOut(BaseModel):
    time: float
    length: float
    midi: int | None = None


class VocalLineOut(BaseModel):
    notes: list[VocalNoteOut]
    gp_has_lyrics: bool = False


class ToneSwapsIn(BaseModel):
    swaps: dict[str, ToneSwapIn] = {}


class UiLanguageIn(BaseModel):
    lang: str


class ToneCollectionScanIn(BaseModel):
    folder: str | None = None


class SyncConfirmedIn(BaseModel):
    confirmed: bool
    # One chart ("Lead", "Alternate Rhythm"…): each track is synchronised on its
    # own. None = the whole song (the checklist's button), i.e. every chart.
    arrangement: str | None = None


class SyncMainIn(BaseModel):
    arrangement: str | None = None  # None = no main chart


class PsarcProblemOut(BaseModel):
    code: str
    text: str
    arrangement: str
    count: int
    level: int | None = None  # where it first happens
    time: float | None = None
    detail: str = ""


class PsarcCheckOut(BaseModel):
    ok: bool
    charts: list[str]
    problems: list[PsarcProblemOut]


class GameDlcOut(BaseModel):
    dlc_dir: str | None
    folder: str  # the sub-folder RockForge installs into
    target: str | None  # dlc_dir/folder, written by the server's own path rules


class InstallOut(BaseModel):
    path: str
    removed: str | None
    duplicates: list[str]
    job: JobOut


class CoverFromUrlIn(BaseModel):
    url: str = Field(max_length=2000)


class RequirementOut(BaseModel):
    """One external dependency and what its absence actually costs."""

    key: str
    name: str
    #: True = present, False = absent, None = NOT CHECKABLE from this process —
    #: a different answer from "absent", and the honest one for the CDLC loader
    #: patch (we do not know where the game is) and for a CUDA build of torch
    #: (only importing it would tell, which the API process must never do).
    found: bool | None
    detail: str
    required: bool
    unlocks: str
    without_it: str
    install: str
    extras: list[str] = []


class SystemCheckOut(BaseModel):
    requirements: list[RequirementOut]
    #: Keys of the required dependencies that are missing — the app cannot
    #: produce anything at all while this is non-empty.
    missing_required: list[str]
