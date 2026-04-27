"""
Apply confirmed event point effects to GameState.

Called during the RECOGNITION phase after rules/event_rules detects that a
piece has stepped onto an active event point node.

Responsibilities (Rulebook V3 §10.2, §10.5):
  Ammunition : piece.atk += 2  (permanent, stackable; +2 makes it strategically
               significant with only 2 event points on the board)
  Medical    : piece.hp  += 1  (clamped to max_hp)
  Trap       : piece.hp  -= 1  (clamped to 0; triggers death check)

Lifecycle:
  - After applying the effect call event_point.trigger() to mark it consumed
    and remove it from state.event_points.
  - Append a history entry.

Spawn (revised):
  spawn_event_point(state) is called at Phase.START on odd-numbered rounds.
  Up to 2 event points are spawned simultaneously.
  Any leftover un-triggered points from the previous cycle are invalidated
  first (replaced by the new spawn).
"""

from __future__ import annotations

from xiangqi_arena.core.enums import EventPointType
from xiangqi_arena.models.event_point import EventPoint
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.rules.damage_rules import clamp_hp, compute_trap_damage, compute_healing
from xiangqi_arena.rules.death_rules import is_piece_dead
from xiangqi_arena.rules.event_rules import make_event_point
from xiangqi_arena.rules.victory_rules import check_victory
from xiangqi_arena.state.game_state import GameState

# Ammunition buff per trigger (raised from 1 to 2 to make it a meaningful pick)
_AMMO_BUFF = 2


# ---------------------------------------------------------------------------
# Trigger
# ---------------------------------------------------------------------------

def apply_event_trigger(
    piece_id: str,
    ep: EventPoint,
    state: GameState,
    *,
    spawn_heal_effect: bool = True,
) -> None:
    """
    Apply *ep*'s effect to *piece_id* and consume the event point.

    Parameters
    ----------
    piece_id:
        The piece that stepped onto the event point.
    ep:
        The specific EventPoint object being triggered.  The caller is
        responsible for confirming that this point is valid and that the
        piece is standing on its node.
    state:
        Current game state (mutated in-place).
    """
    if not ep.is_valid:
        return

    piece: Piece = state.pieces[piece_id]
    effect = ep.event_type

    if effect is EventPointType.AMMUNITION:
        piece.apply_atk_buff(_AMMO_BUFF)

    elif effect is EventPointType.MEDICAL:
        piece.apply_healing(compute_healing())

    elif effect is EventPointType.TRAP:
        piece.apply_damage(compute_trap_damage())
        if is_piece_dead(piece) and not piece.is_dead:
            _process_death(piece, state)
            _refresh_victory(state)

    # Consume the event point
    ep.trigger()
    try:
        state.event_points.remove(ep)
    except ValueError:
        pass  # already removed (shouldn't happen, but safe)

    history_entry = {
        "type": "event_trigger",
        "round": state.round_number,
        "piece_id": piece_id,
        "event_type": effect.value,
        "pos": ep.pos,
    }
    if effect is EventPointType.MEDICAL:
        history_entry["spawn_heal_effect"] = spawn_heal_effect
    state.history.append(history_entry)


# ---------------------------------------------------------------------------
# Spawn
# ---------------------------------------------------------------------------

def spawn_event_point(state: GameState) -> None:
    """
    Spawn up to 2 new event points for the current odd round.

    Previous un-triggered event points are invalidated and cleared first
    (the new spawn replaces them entirely).
    """
    # Invalidate and clear any leftover event points
    for ep in state.event_points:
        if ep.is_valid:
            ep.invalidate()
    state.event_points.clear()

    # Spawn up to 2 new points (second spawn respects first spawn's position)
    for _ in range(2):
        new_ep = make_event_point(state)
        if new_ep is not None:
            state.event_points.append(new_ep)
            state.history.append({
                "type": "event_spawn",
                "round": state.round_number,
                "event_type": new_ep.event_type.value,
                "pos": new_ep.pos,
            })


# ---------------------------------------------------------------------------
# Internal helpers (shared with modification/attack)
# ---------------------------------------------------------------------------

def _process_death(piece: Piece, state: GameState) -> None:
    piece.mark_dead()
    try:
        state.board.remove_piece(*piece.pos)
    except KeyError:
        pass
    state.history.append({
        "type": "death",
        "round": state.round_number,
        "faction": piece.faction.value,
        "piece_id": piece.id,
        "pos": piece.pos,
        "cause": "trap",
    })


def _refresh_victory(state: GameState) -> None:
    result = check_victory(state)
    if result is not state.victory_state:
        state.victory_state = result
        state.history.append({
            "type": "victory",
            "round": state.round_number,
            "result": result.value,
        })
