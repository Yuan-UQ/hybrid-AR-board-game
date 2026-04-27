from models.piece import Piece


def compute_damage(attacker: Piece, bonus: int = 0, reduction: int = 0) -> int:
    return max(0, attacker.atk + bonus - reduction)


def capped_heal(piece: Piece, amount: int) -> int:
    piece.hp = min(piece.max_hp, piece.hp + amount)
    return piece.hp
