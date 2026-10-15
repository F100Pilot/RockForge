# SPDX-License-Identifier: MPL-2.0
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at https://mozilla.org/MPL/2.0/.
#
# Ported from alphaTab (https://github.com/CoderLine/alphaTab), Copyright (c)
# Daniel Kuschny and Contributors, which is MPL-2.0: ``Note.finish``'s reading
# of a three-point bend. The MPL is file-level, so this file keeps it while
# the rest of RockForge is MIT (THIRD_PARTY_NOTICES.md).
"""Guitar Pro bend curves read the way alphaTab plays them."""

from __future__ import annotations

from collections.abc import Sequence

from rockforge.domain.music import BendPoint


def alphatab_bend(points: Sequence[BendPoint]) -> tuple[BendPoint, ...]:
    """A bend curve as alphaTab plays it (``Note.finish``, alphaTab 1.8).

    alphaTab keeps the middle point of a three-point bend only when it is a peak
    (a bend-and-release). Otherwise the bend becomes a straight line from its
    origin to its destination: "up to the middle of the note, then held" plays
    as a rise across the whole note, and the same for pre-bends and releases.
    Other point counts are returned unchanged.
    """
    if len(points) != 3:
        return tuple(points)
    origin, middle, destination = (p.step for p in points)
    if (destination > origin and middle > destination) or (
        destination == origin and middle > origin
    ):
        return tuple(points)
    return (points[0], points[2])
