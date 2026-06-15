"""Native PSARC packing (no DLC Builder dependency).

Phase 1: the PSARC container format (header, zlib block compression, TOC).
Encryption (real Rocksmith PSARCs encrypt the TOC and SNG payloads) is added
in a later phase — see TODO.md for the full plan.
"""
