from core.utils import Position
from state.game_state import GameState


def execute_move(state: GameState, piece_id: str, destination: Position) -> None:
    piece = state.pieces[piece_id]
    old_position = piece.position
    piece.position = destination
    state.board.move_piece(old_position, destination)
    state.action.piece_id = piece_id
    state.action.has_moved = True
    state.history.append(f"{piece_id} moved {old_position} -> {destination}")
