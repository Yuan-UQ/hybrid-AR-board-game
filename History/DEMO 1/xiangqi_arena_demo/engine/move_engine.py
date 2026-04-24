"""
Handles selection, move generation, movement execution, and event triggering.
"""

from engine.validator import get_piece_move_positions, can_select_piece, can_move_selected_piece
from rules.damage_rules import apply_event_effect
from core.constants import PHASE_ATTACK


def select_piece(game_state, x: int, y: int) -> bool:
    """
    Select a piece on board if it belongs to current player.
    """
    piece = game_state.board.get_piece_at(x, y)
    if not can_select_piece(game_state, piece):
        game_state.message = "Cannot select this piece."
        return False

    game_state.set_selected_piece(piece)
    game_state.set_available_moves(get_piece_move_positions(game_state.board, piece))
    game_state.available_attacks = []
    game_state.available_cannon_centers = []
    game_state.message = f"Selected {piece.id}."
    return True


def refresh_selected_piece_moves(game_state) -> None:
    piece = game_state.selected_piece
    if piece is None:
        game_state.available_moves = []
        return

    game_state.set_available_moves(get_piece_move_positions(game_state.board, piece))


def move_selected_piece(game_state, target_x: int, target_y: int) -> bool:
    """
    Move currently selected piece if the move is legal.
    Also triggers event if landing on one.
    After move, automatically enter attack phase.
    """
    piece = game_state.selected_piece
    if piece is None:
        game_state.message = "No piece selected."
        return False

    if not can_move_selected_piece(game_state, target_x, target_y):
        game_state.message = "Invalid move."
        return False

    game_state.board.move_piece(piece, target_x, target_y)
    game_state.last_action = ("move", piece.id, target_x, target_y)

    event = game_state.get_event_at(target_x, target_y)
    if event is not None:
        result = apply_event_effect(piece, event["type"])
        game_state.remove_event_at(target_x, target_y)
        game_state.message = (
            f"{piece.id} moved to ({target_x}, {target_y}) and triggered {event['type']}."
        )
        if result["hp_change"] != 0:
            game_state.message += f" HP change: {result['hp_change']}."
        if result["atk_change"] != 0:
            game_state.message += f" ATK change: +{result['atk_change']}."
    else:
        game_state.message = f"{piece.id} moved to ({target_x}, {target_y})."

    game_state.available_moves = []
    game_state.set_phase(PHASE_ATTACK)

    return True


def clear_current_selection(game_state) -> None:
    game_state.clear_selection()