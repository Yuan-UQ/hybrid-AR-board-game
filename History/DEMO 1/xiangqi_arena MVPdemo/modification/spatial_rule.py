from core.enums import PieceType
from core.utils import is_in_palace, local_neighbors
from state.game_state import GameState


def general_damage_reduction(state: GameState, piece_id: str) -> int:
    piece = state.pieces[piece_id]
    if piece.piece_type is PieceType.GENERAL and is_in_palace(piece.position, piece.side):
        return 1
    return 0


def pawn_attack_bonus(state: GameState, piece_id: str) -> int:
    piece = state.pieces[piece_id]
    if piece.piece_type is not PieceType.PAWN:
        return 0
    for position in local_neighbors(piece.position):
        neighbor_id = state.board.get_piece_at(position)
        if neighbor_id and neighbor_id != piece_id and state.pieces[neighbor_id].side is piece.side:
            return 1
    return 0
