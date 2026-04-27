"""
Creates board and initial piece placement.
"""

from core.board import Board
from core.piece import Piece
from core.game_state import GameState
from core.constants import (
    RED,
    BLACK,
    KING,
    ROOK,
    KNIGHT,
    CANNON,
    PAWN,
)


def _make_piece_id(camp: str, piece_type: str, index: int) -> str:
    return f"{camp}_{piece_type}_{index}"


def create_initial_board() -> Board:
    board = Board()

    # Black side
    board.add_piece(Piece(_make_piece_id(BLACK, ROOK, 1), ROOK, BLACK, 0, 0))
    board.add_piece(Piece(_make_piece_id(BLACK, KNIGHT, 1), KNIGHT, BLACK, 2, 0))
    board.add_piece(Piece(_make_piece_id(BLACK, KING, 1), KING, BLACK, 4, 0))
    board.add_piece(Piece(_make_piece_id(BLACK, CANNON, 1), CANNON, BLACK, 6, 0))

    board.add_piece(Piece(_make_piece_id(BLACK, PAWN, 1), PAWN, BLACK, 2, 3))
    board.add_piece(Piece(_make_piece_id(BLACK, PAWN, 2), PAWN, BLACK, 4, 3))
    board.add_piece(Piece(_make_piece_id(BLACK, PAWN, 3), PAWN, BLACK, 6, 3))

    # Red side
    board.add_piece(Piece(_make_piece_id(RED, ROOK, 1), ROOK, RED, 0, 9))
    board.add_piece(Piece(_make_piece_id(RED, KNIGHT, 1), KNIGHT, RED, 2, 9))
    board.add_piece(Piece(_make_piece_id(RED, KING, 1), KING, RED, 4, 9))
    board.add_piece(Piece(_make_piece_id(RED, CANNON, 1), CANNON, RED, 6, 9))

    board.add_piece(Piece(_make_piece_id(RED, PAWN, 1), PAWN, RED, 2, 6))
    board.add_piece(Piece(_make_piece_id(RED, PAWN, 2), PAWN, RED, 4, 6))
    board.add_piece(Piece(_make_piece_id(RED, PAWN, 3), PAWN, RED, 6, 6))

    return board


def create_initial_game_state() -> GameState:
    board = create_initial_board()
    return GameState(board)