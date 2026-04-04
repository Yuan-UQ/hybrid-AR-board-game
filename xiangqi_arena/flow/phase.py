"""
Phase progression within a turn.

Rulebook V3 §12.3 — five ordered phases per turn:
  START → MOVEMENT → RECOGNITION → ATTACK → RESOLVE

Transitions must follow that fixed order.  The only legal way to leave
RESOLVE is via `flow.turn.end_turn()`, which resets the state for the next
player's START phase.

This module controls *when* phase transitions happen.  It does not judge
whether an action inside a phase is legal (that belongs to rules/).
"""

from __future__ import annotations

from xiangqi_arena.core.enums import Phase
from xiangqi_arena.state.game_state import GameState

# ---------------------------------------------------------------------------
# Allowed actions per phase
# Used by input_control and main loop to gate what inputs are accepted.
# ---------------------------------------------------------------------------

ALLOWED_ACTIONS: dict[Phase, frozenset[str]] = {
    Phase.START: frozenset({
        "confirm",          # press Enter to proceed to MOVEMENT
    }),
    Phase.MOVEMENT: frozenset({
        "select_piece",     # choose which friendly piece to operate
        "move_piece",       # physically move the selected piece
        "skip_movement",    # press Enter without moving
    }),
    Phase.RECOGNITION: frozenset({
        "confirm",          # press Enter after system scan completes
        "retry_scan",       # request another scan (illegal-move correction)
    }),
    Phase.ATTACK: frozenset({
        "select_target",    # click / keyboard-select an attack target
        "set_cannon_dir",   # arrow-key direction for Cannon
        "confirm_attack",   # confirm the chosen attack
        "skip_attack",      # press Enter without attacking
    }),
    Phase.RESOLVE: frozenset({
        "confirm",          # press Enter to end the turn
    }),
}


def is_action_allowed(action: str, phase: Phase) -> bool:
    """Return True if *action* is permitted during *phase*."""
    return action in ALLOWED_ACTIONS.get(phase, frozenset())


# ---------------------------------------------------------------------------
# Phase transition
# ---------------------------------------------------------------------------

def advance_phase(state: GameState) -> None:
    """
    Move *state* forward by one phase in the fixed sequence.

    Raises
    ------
    ValueError
        If called while the current phase is RESOLVE — that transition is
        owned by `flow.turn.end_turn()`, not this function.
    """
    if state.current_phase is Phase.RESOLVE:
        raise ValueError(
            "Cannot advance past RESOLVE with advance_phase(). "
            "Call flow.turn.end_turn() to finish the turn instead."
        )
    state.current_phase = state.current_phase.next()


def assert_in_phase(state: GameState, expected: Phase) -> None:
    """
    Raise a RuntimeError if the state is not in *expected* phase.
    Useful as a guard at the top of phase-specific handlers.
    """
    if state.current_phase is not expected:
        raise RuntimeError(
            f"Expected phase {expected.name}, "
            f"but current phase is {state.current_phase.name}."
        )
