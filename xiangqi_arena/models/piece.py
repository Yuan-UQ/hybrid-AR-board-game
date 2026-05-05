"""
Piece domain model.

All pieces — regardless of type — are represented through this single class.
Piece-specific behaviour lives in rules/piece_rules.py, not here.

Design notes (Rulebook V3 / Guide v2):
- `atk` stores the *current* effective attack value, including any permanent
  ammunition buff stacked up over the game.  There is no separate base/buff
  split because the buff is permanent once applied.
- Soldier nearby-ally bonus is NOT stored here; it is a temporary per-attack
  modifier computed on the fly in rules/damage_rules.py.
- `is_dead = True` means the piece is logically out of the game: it no longer
  occupies a board node and cannot move, attack, block, or be targeted.
  The physical piece may still be on the table — the UI marks it clearly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xiangqi_arena.core.enums import Faction, PieceType


@dataclass
class Piece:
    """A single game piece with full runtime state."""

    # --- identity (immutable during a game) ---
    id: str                   # unique marker-based ID, e.g. "ArcherHuman"
    faction: Faction
    piece_type: PieceType

    # --- spatial state ---
    pos: tuple[int, int]      # (x, y) on the 9×10 intersection grid

    # --- combat attributes ---
    hp: int
    max_hp: int
    atk: int                  # effective ATK (includes permanent ammo buffs)

    # --- lifecycle flags ---
    is_dead: bool = False
    is_operable: bool = True  # False when a piece cannot be selected this turn

    def is_alive(self) -> bool:
        return not self.is_dead

    def apply_damage(self, amount: int) -> None:
        """Lower HP by *amount* (clamped at 0). Does NOT set is_dead."""
        self.hp = max(0, self.hp - amount)

    def apply_healing(self, amount: int) -> None:
        """Raise HP by *amount* (clamped at max_hp)."""
        self.hp = min(self.max_hp, self.hp + amount)

    def apply_atk_buff(self, amount: int = 1) -> None:
        """Permanently increase ATK (ammunition event point)."""
        self.atk += amount

    def mark_dead(self) -> None:
        """Mark the piece as dead and disable all interaction."""
        self.is_dead = True
        self.is_operable = False

    def __repr__(self) -> str:
        status = "dead" if self.is_dead else f"HP={self.hp}/{self.max_hp} ATK={self.atk}"
        return f"Piece({self.id}, {self.pos}, {status})"
