"""
Round-level progression control.

Rulebook V3 §10.4 definition:
  1 round = HumanSide completes 1 turn + OrcSide completes 1 turn.

The round counter starts at 1 and increments *after* OrcSide finishes each
turn (i.e. just before HumanSide's next START phase begins).

Event point spawn timing (corrected rule):
  One event point is spawned at the START of HumanSide's turn on odd-numbered
  rounds (round 1, 3, 5, …).  The point persists for the entire odd round
  AND the following even round — i.e. it lasts two full rounds unless a
  piece walks onto it first.  On the next odd round, if still untriggered,
  it is replaced (invalidated) by the new spawn.

  Key: spawning is checked only when it is HumanSide's START phase so that OrcSide's
  START phase in the same round does NOT generate a second event point.
"""

from __future__ import annotations

from xiangqi_arena.core.enums import Faction
from xiangqi_arena.core.utils import is_event_point_round
from xiangqi_arena.state.game_state import GameState


def increment_round(state: GameState) -> None:
    """
    Advance the round counter by one.

    Called by `flow.turn.end_turn()` immediately after OrcSide's RESOLVE phase,
    before the next turn's start_turn() is invoked.
    """
    state.round_number += 1


def should_spawn_event_point(state: GameState) -> bool:
    """
    Return True if a new event point should be spawned RIGHT NOW.

    Conditions (both must hold):
    1. The current round is odd — event points refresh every two rounds.
    2. It is the beginning of HumanSide's turn — HumanSide always opens a new round, so
       this gate ensures we spawn exactly once per odd round, not twice
       (once for HumanSide, once for OrcSide in the same round).
    """
    return (
        is_event_point_round(state.round_number)
        and state.active_faction is Faction.HumanSide
    )


def round_summary(state: GameState) -> str:
    """Return a short human-readable string describing the current position."""
    faction = state.active_faction.value.capitalize()
    return (
        f"Round {state.round_number} — {faction}'s turn "
        f"(Phase: {state.current_phase.name})"
    )
