def is_piece_dead(piece) -> bool:
    if piece is None:
        return False
    return piece.hp <= 0 or (not piece.alive)


def mark_piece_dead(piece) -> None:
    """
    Force a piece into dead / pending removal state.
    """
    if piece is None:
        return

    piece.hp = 0
    piece.alive = False
    piece.pending_removal = True


def handle_piece_death(piece) -> bool:
    """
    If piece should die, mark it dead.
    Return True if piece is dead after handling.
    """
    if piece is None:
        return False

    if piece.hp <= 0:
        mark_piece_dead(piece)
        return True

    return not piece.alive


def remove_dead_pieces_from_board(board) -> list:
    """
    Remove all dead / pending-removal pieces from the board.
    Return removed pieces.
    """
    removed = []

    for piece in board.get_all_pieces():
        if is_piece_dead(piece) or piece.pending_removal:
            removed.append(piece)

    for piece in removed:
        board.remove_piece(piece)

    return removed


def cleanup_dead_pieces(board) -> list:
    """
    Alias helper for later engine usage.
    """
    return remove_dead_pieces_from_board(board)