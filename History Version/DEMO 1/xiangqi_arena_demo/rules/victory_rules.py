"""
Victory rules for Xiangqi Arena. A side loses when its king dies.
"""

from core.constants import RED, BLACK, KING


def find_kings(board) -> dict:
    kings = {}

    for piece in board.get_all_pieces():
        if piece.piece_type == KING and piece.alive:
            kings[piece.camp] = piece

    return kings


def get_winner_if_any(board):
    """
    Return winner camp if one side's king is gone.
    Otherwise return None.
    """
    kings = find_kings(board)

    red_has_king = RED in kings
    black_has_king = BLACK in kings

    if red_has_king and black_has_king:
        return None

    if red_has_king and not black_has_king:
        return RED

    if black_has_king and not red_has_king:
        return BLACK

    # extremely rare edge case: both kings gone
    return "draw"


def check_game_over(board) -> tuple[bool, str | None]:
    """
    Return (game_over, winner)
    """
    winner = get_winner_if_any(board)
    if winner is None:
        return False, None
    return True, winner


def update_game_over_state(game_state) -> tuple[bool, str | None]:
    """
    Check board and update game_state if game ends.
    """
    game_over, winner = check_game_over(game_state.board)
    if game_over:
        game_state.set_game_over(winner)
    return game_over, winner