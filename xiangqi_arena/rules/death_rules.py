from models.piece import Piece


def refresh_death_state(piece: Piece) -> bool:
    if piece.hp > 0:
        return False
    piece.is_dead = True
    return True
