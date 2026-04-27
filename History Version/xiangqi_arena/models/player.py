"""
Player domain model.

Tracks per-player identity and game-level status.
Piece ownership is stored as a list of piece IDs; actual piece objects live
in GameState.pieces so there is a single authoritative copy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xiangqi_arena.core.enums import Faction


@dataclass
class Player:
    """Represents one of the two players."""

    faction: Faction

    # IDs of all pieces belonging to this player (including dead ones).
    # The order is fixed at game start and never changes.
    piece_ids: list[str] = field(default_factory=list)

    # True when it is currently this player's turn.
    is_active: bool = False

    # Set to True when the player voluntarily surrenders (Rulebook V3 §15.2).
    has_surrendered: bool = False

    # Set to True when the player has requested a draw this turn.
    # A draw is only confirmed when both players have this flag set at the
    # same time (handled by victory_rules).
    draw_requested: bool = False

    def __repr__(self) -> str:
        active_str = " [active]" if self.is_active else ""
        return f"Player({self.faction.value}{active_str}, pieces={self.piece_ids})"
