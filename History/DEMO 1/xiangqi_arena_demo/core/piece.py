"""
Each piece is an object with type, camp, position, hp, atk, and status flags.
"""

from core.constants import PIECE_BASE_STATS


class Piece:
    def __init__(self, piece_id: str, piece_type: str, camp: str, x: int, y: int):
        if piece_type not in PIECE_BASE_STATS:
            raise ValueError(f"Unknown piece type: {piece_type}")

        stats = PIECE_BASE_STATS[piece_type]

        self.id = piece_id
        self.piece_type = piece_type
        self.camp = camp

        self.x = x
        self.y = y

        self.hp = stats["initial_hp"]
        self.max_hp = stats["max_hp"]
        self.atk = stats["atk"]

        self.alive = True
        self.pending_removal = False

    def get_position(self) -> tuple[int, int]:
        return self.x, self.y

    def set_position(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def take_damage(self, damage: int) -> None:
        """
        Reduce hp by damage.
        Damage lower than 0 is treated as 0.
        """
        real_damage = max(0, damage)
        self.hp -= real_damage
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            self.pending_removal = True

    def heal(self, amount: int) -> None:
        """
        Recover hp, but not above max_hp.
        """
        if not self.alive:
            return
        self.hp = min(self.max_hp, self.hp + max(0, amount))

    def increase_atk(self, amount: int) -> None:
        """
        Permanent ATK increase.
        """
        if not self.alive:
            return
        self.atk += max(0, amount)

    def mark_removed(self) -> None:
        self.pending_removal = True
        self.alive = False

    def is_alive(self) -> bool:
        return self.alive

    def copy(self) -> "Piece":
        """
        Useful later for testing or simulation.
        """
        new_piece = Piece(self.id, self.piece_type, self.camp, self.x, self.y)
        new_piece.hp = self.hp
        new_piece.max_hp = self.max_hp
        new_piece.atk = self.atk
        new_piece.alive = self.alive
        new_piece.pending_removal = self.pending_removal
        return new_piece

    def __repr__(self) -> str:
        return (
            f"Piece(id={self.id!r}, type={self.piece_type!r}, camp={self.camp!r}, "
            f"pos=({self.x}, {self.y}), hp={self.hp}/{self.max_hp}, atk={self.atk}, "
            f"alive={self.alive})"
        )