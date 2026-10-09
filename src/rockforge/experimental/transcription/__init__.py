"""Audio → guitar notes, EXPERIMENTAL — phase 0: measure before building.

RockForge once transcribed recordings with Basic Pitch and removed it: on a
distorted electric guitar mix it was never trustworthy. Before any new attempt
reaches the app, this bench measures candidate transcribers on the user's OWN
songs, against the charts they already built and synced (the Guitar Pro notes,
with every sync correction applied, are the right answer to within a few
milliseconds):

    python -m rockforge.experimental.transcription list
    python -m rockforge.experimental.transcription run --models gaps,yourmt3
    python -m rockforge.experimental.transcription score FILE.mid --project ID

It only READS the database, the built XMLs and the recordings; it writes into
its own output folder. Nothing in the app calls it.
"""
