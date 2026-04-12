from core.enums import PieceType
from core.utils import (
    Position,
    add_position,
    diagonal_neighbors,
    forward_step,
    has_crossed_river,
    is_in_bounds,
    is_in_palace,
    orthogonal_line,
    orthogonal_neighbors,
)
from models.piece import Piece
from state.game_state import GameState

ORTHOGONAL_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))
HORSE_JUMPS = (
    ((2, 1), (1, 0)),
    ((2, -1), (1, 0)),
    ((-2, 1), (-1, 0)),
    ((-2, -1), (-1, 0)),
    ((1, 2), (0, 1)),
    ((-1, 2), (0, 1)),
    ((1, -2), (0, -1)),
    ((-1, -2), (0, -1)),
)


def _general_moves(piece: Piece) -> list[Position]:
    return [pos for pos in orthogonal_neighbors(piece.position) + diagonal_neighbors(piece.position) if is_in_palace(pos, piece.side)]


def _chariot_moves(state: GameState, piece: Piece) -> list[Position]:
    moves: list[Position] = []
    for direction in ORTHOGONAL_DIRECTIONS:
        for position in orthogonal_line(piece.position, direction, 3):
            if state.board.is_occupied(position):
                break
            moves.append(position)
    return moves


def _horse_moves(state: GameState, piece: Piece) -> list[Position]:
    moves: list[Position] = []
    for jump, leg in HORSE_JUMPS:
        leg_position = add_position(piece.position, leg)
        destination = add_position(piece.position, jump)
        if not is_in_bounds(destination):
            continue
        if state.board.is_occupied(leg_position) or state.board.is_occupied(destination):
            continue
        moves.append(destination)
    return moves


def _cannon_moves(state: GameState, piece: Piece) -> list[Position]:
    moves: list[Position] = []
    for direction in ORTHOGONAL_DIRECTIONS:
        line = orthogonal_line(piece.position, direction, 2)
        for index, position in enumerate(line):
            if state.board.is_occupied(position):
                break
            if any(state.board.is_occupied(blocker) for blocker in line[:index]):
                break
            moves.append(position)
    return moves


def _pawn_moves(piece: Piece) -> list[Position]:
    x, y = piece.position
    moves = [(x, y + forward_step(piece.side))]
    if has_crossed_river(piece.position, piece.side):
        moves.extend(((x - 1, y), (x + 1, y)))
    return [position for position in moves if is_in_bounds(position)]


def legal_moves_for_piece(state: GameState, piece: Piece) -> list[Position]:
    if piece.is_dead or piece.side is not state.current_side:
        return []
    if piece.piece_type is PieceType.GENERAL:
        candidates = _general_moves(piece)
    elif piece.piece_type is PieceType.CHARIOT:
        candidates = _chariot_moves(state, piece)
    elif piece.piece_type is PieceType.HORSE:
        candidates = _horse_moves(state, piece)
    elif piece.piece_type is PieceType.CANNON:
        candidates = _cannon_moves(state, piece)
    else:
        candidates = _pawn_moves(piece)
    return [position for position in candidates if not state.board.is_occupied(position)]


def is_legal_move(state: GameState, piece: Piece, destination: Position) -> bool:
    return destination in legal_moves_for_piece(state, piece)
