"""
Controls phase transitions and player switching.
"""

from core.constants import PHASE_MOVE, PHASE_ATTACK
from engine.move_engine import clear_current_selection
from engine.event_engine import refresh_events
from engine.attack_engine import start_attack_phase


def advance_phase(game_state) -> str:
    """
    move -> attack
    attack -> directly end turn / switch player
    """
    if game_state.game_over:
        game_state.message = "Game already ended."
        return game_state.phase

    current_phase = game_state.phase

    if current_phase == PHASE_MOVE:
        game_state.set_phase(PHASE_ATTACK)
        start_attack_phase(game_state)
        return game_state.phase

    if current_phase == PHASE_ATTACK:
        end_current_turn(game_state)
        return game_state.phase

    return game_state.phase


def end_current_turn(game_state) -> None:
    """
    End current player's turn, switch player, and start next player's move phase.
    """
    if game_state.game_over:
        return

    previous_player = game_state.current_player

    clear_current_selection(game_state)

    if hasattr(game_state, "clear_attack_ready_pieces"):
        game_state.clear_attack_ready_pieces()

    game_state.switch_player()
    game_state.next_round_if_needed(previous_player)

    if previous_player == "black" and game_state.current_player == "red":
        refresh_events(game_state)

    game_state.set_phase(PHASE_MOVE)
    game_state.message = (
        f"Now it is {game_state.current_player}'s turn. "
        f"Round {game_state.round_number}, move phase."
    )