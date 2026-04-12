"""
Turn-level progression control.

A turn belongs to one player (Red or Black).  At most one friendly piece may
be operated per turn, and at most one attack may be made (Rulebook V3 §12.1).

Turn lifecycle
--------------
1. `start_turn(state)`   — called once at the very beginning of a turn.
                            Resets ActionContext, sets current phase to START.
2.  … phases run …
3. `end_turn(state)`     — called when the player confirms at RESOLVE.
                            If Black just finished, increments the round first.
                            Then switches sides and calls start_turn() for the
                            next player.

This module modifies GameState directly because flow/ is allowed to update
progression state (round, faction, phase).  It must NOT implement detailed
piece or combat logic.
"""

from __future__ import annotations

from xiangqi_arena.core.enums import Faction, Phase
from xiangqi_arena.state.game_state import GameState


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_turn(state: GameState) -> None:
    """
    Initialise the state for a fresh turn belonging to `state.active_faction`.

    - Resets the per-turn ActionContext.
    - Sets phase to START.
    - Marks the active player's flag and clears the other player's flag.
    """
    state.start_new_turn()                         # clears ActionContext
    state.current_phase = Phase.START
    _sync_active_player_flags(state)


def end_turn(state: GameState) -> None:
    """
    Conclude the current turn and hand control to the other player.

    Order of operations:
    1. If Black just finished, increment the round counter (Red + Black = 1
       round, Rulebook V3 §10.4).
    2. Switch active_faction.
    3. Call start_turn() for the newly active player.
    """
    if state.current_phase is not Phase.RESOLVE:
        raise RuntimeError(
            "end_turn() must only be called during the RESOLVE phase, "
            f"but current phase is {state.current_phase.name}."
        )

    # Round increments after Black completes a turn (imported lazily to avoid
    # a potential circular reference at module load time).
    if state.active_faction is Faction.BLACK:
        from xiangqi_arena.flow.round import increment_round  # noqa: PLC0415
        increment_round(state)

    _switch_active_side(state)
    start_turn(state)


def can_select_piece(state: GameState, piece_id: str) -> bool:
    """
    Return True if the player is allowed to select *piece_id* this turn.

    Rules:
    - Must be in MOVEMENT phase.
    - No piece has been selected yet (one piece per turn).
    - The piece must belong to the active faction and be alive and operable.
    """
    if state.current_phase is not Phase.MOVEMENT:
        return False
    if state.action.selected_piece_id is not None:
        return False
    piece = state.pieces.get(piece_id)
    if piece is None:
        return False
    return (
        piece.faction is state.active_faction
        and piece.is_alive()
        and piece.is_operable
    )


def can_attack(state: GameState) -> bool:
    """
    Return True if an attack is still possible this turn.

    Conditions:
    - Must be in ATTACK phase.
    - Attack has not yet been completed or skipped.
    """
    return (
        state.current_phase is Phase.ATTACK
        and not state.action.attack_decided()
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _switch_active_side(state: GameState) -> None:
    state.active_faction = state.active_faction.opponent()


def _sync_active_player_flags(state: GameState) -> None:
    """Keep Player.is_active in sync with GameState.active_faction."""
    for faction, player in state.players.items():
        player.is_active = (faction is state.active_faction)
