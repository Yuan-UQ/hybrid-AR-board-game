"""
Event point rules: spawn timing, position validity, and trigger detection.

Pure read-only logic only.  Actual state mutations (applying ATK/HP changes,
removing the event point) live in modification/event.py.

Rulebook V3 §10 (revised for 2-point gameplay):
  §10.3 Spawn rules:
    - Event points can only spawn on empty nodes.
    - They may spawn inside palaces.
    - Position is completely random.
  §10.4 Refresh timing:
    - Up to 2 event points spawn on odd-numbered rounds (1, 3, 5, …).
    - At most 2 event points on the board at any time.
    - Previous un-triggered points are replaced (invalidated first).
  §10.5 Trigger:
    - A piece triggers an event point by entering its node.
    - The point disappears immediately after triggering.
"""

from __future__ import annotations

import random

from xiangqi_arena.core.enums import EventPointType
from xiangqi_arena.models.event_point import EventPoint
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.state.game_state import GameState

Pos = tuple[int, int]


# ---------------------------------------------------------------------------
# Spawn timing
# ---------------------------------------------------------------------------

def should_spawn_this_round(state: GameState) -> bool:
    """
    Return True if event points should be generated at the start of the
    current round (odd rounds only, Rulebook V3 §10.4).
    """
    return state.round_number % 2 == 1


# ---------------------------------------------------------------------------
# Spawn position selection
# ---------------------------------------------------------------------------

def choose_spawn_position(state: GameState) -> Pos | None:
    """
    Select a random empty board node for a new event point.

    Excludes nodes already occupied by existing active event points so that
    both new points land on different nodes.
    """
    empty_nodes = state.board.all_empty_nodes()

    # Exclude positions already claimed by active event points
    occupied_by_events = {ep.pos for ep in state.event_points if ep.is_valid}
    empty_nodes = [n for n in empty_nodes if n not in occupied_by_events]

    if not empty_nodes:
        return None
    return random.choice(empty_nodes)


def choose_event_type() -> EventPointType:
    """
    Select the event point type for the new spawn.
    Equal-probability random choice between the three types.
    """
    return random.choice(list(EventPointType))


def make_event_point(state: GameState) -> EventPoint | None:
    """
    Build a new EventPoint for the current round, choosing a random empty
    position and a random type.  Returns None if no valid position exists.
    """
    pos = choose_spawn_position(state)
    if pos is None:
        return None
    return EventPoint(
        event_type=choose_event_type(),
        pos=pos,
        spawn_round=state.round_number,
    )


# ---------------------------------------------------------------------------
# Trigger detection  (primary API)
# ---------------------------------------------------------------------------

def get_all_triggers(state: GameState) -> list[tuple[str, EventPoint]]:
    """
    Return a list of (piece_id, event_point) pairs for every active event
    point that currently has a live piece standing on it.

    Called during the RECOGNITION phase after piece positions are updated.
    Multiple triggers can occur in one recognition pass if two event points
    happen to be occupied simultaneously (e.g. a piece moved earlier in the
    turn, and another piece was already sitting on a different event node).
    In practice only the moving piece can trigger; this API is intentionally
    general to stay correct in edge-cases.
    """
    triggers: list[tuple[str, EventPoint]] = []
    for ep in list(state.event_points):   # copy so mutation inside is safe
        if not ep.is_valid or ep.is_triggered:
            continue
        pid = state.board.get_piece_id_at(*ep.pos)
        if pid is None:
            continue
        piece = state.pieces[pid]
        if piece.is_alive():
            triggers.append((pid, ep))
    return triggers


# ---------------------------------------------------------------------------
# Legacy single-trigger helpers  (kept for backward compat / simulate.py)
# ---------------------------------------------------------------------------

def piece_triggers_event(piece: Piece, state: GameState) -> bool:
    """
    Return True if *piece* is currently standing on any active event point.
    """
    for ep in state.event_points:
        if ep.is_valid and not ep.is_triggered:
            if piece.pos == ep.pos and piece.is_alive():
                return True
    return False


def get_triggered_piece(state: GameState) -> Piece | None:
    """
    Return the first live piece standing on an active event point, or None.

    Deprecated in favour of get_all_triggers(); kept for backward compat.
    """
    triggers = get_all_triggers(state)
    if not triggers:
        return None
    pid, _ = triggers[0]
    return state.pieces[pid]
