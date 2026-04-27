"""
Per-turn temporary action context.

This dataclass holds everything that is specific to the current turn in
progress.  It is reset to a clean state at the start of every new turn.

It is NOT long-term game state — it lives inside GameState purely as a
convenience container, and GameState.start_new_turn() wipes it.

Fields (Rulebook V3 §12):
- A player operates at most ONE friendly piece per turn.
- At most ONE attack may be made per turn.
- Movement and/or attack may each be skipped independently.
- Cannon attack requires a direction selection before confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Pos = tuple[int, int]


@dataclass
class ActionContext:
    """Transient per-turn state cleared at the start of each new turn."""

    # The piece the current player chose to operate this turn.
    selected_piece_id: str | None = None

    # Movement sub-state
    move_completed: bool = False   # piece has been physically moved & confirmed
    move_skipped: bool = False     # player pressed Enter to skip movement

    # Attack sub-state
    attack_completed: bool = False
    attack_skipped: bool = False

    # Cannon-specific: direction chosen via arrow keys (dx, dy unit vector).
    cannon_direction: Pos | None = None

    # The logical target position for the current attack (set during Attack phase).
    target_pos: Pos | None = None

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    def movement_decided(self) -> bool:
        """True once movement has either been completed or explicitly skipped."""
        return self.move_completed or self.move_skipped

    def attack_decided(self) -> bool:
        """True once attack has either been completed or explicitly skipped."""
        return self.attack_completed or self.attack_skipped

    def reset(self) -> None:
        """Clear all fields back to defaults (called at the start of a new turn)."""
        self.selected_piece_id = None
        self.move_completed = False
        self.move_skipped = False
        self.attack_completed = False
        self.attack_skipped = False
        self.cannon_direction = None
        self.target_pos = None

    def __repr__(self) -> str:
        parts = []
        if self.selected_piece_id:
            parts.append(f"piece={self.selected_piece_id}")
        if self.move_completed:
            parts.append("moved")
        elif self.move_skipped:
            parts.append("move-skipped")
        if self.attack_completed:
            parts.append("attacked")
        elif self.attack_skipped:
            parts.append("attack-skipped")
        return f"ActionContext({', '.join(parts) or 'empty'})"
