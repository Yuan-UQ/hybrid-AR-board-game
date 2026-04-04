"""
Event point domain model.

Event points are temporary, digital-only effects placed on empty board nodes.
They have no physical marker; they exist only in the UI layer.

Lifecycle (Rulebook V3 §10.4–10.6):
- Spawns on odd-numbered rounds, on a randomly chosen empty node.
- Triggers immediately when any piece steps onto the node.
- Once triggered, disappears at once (is_valid = False).
- If not triggered, persists until the next odd-round refresh, at which point
  the old point is replaced by a new one.
- At most one event point exists on the board at any given time.
"""

from __future__ import annotations

from dataclasses import dataclass

from xiangqi_arena.core.enums import EventPointType

Pos = tuple[int, int]


@dataclass
class EventPoint:
    """A single event point with full lifecycle state."""

    event_type: EventPointType
    pos: Pos
    spawn_round: int          # round number when this point was generated

    # Set to True the moment a piece enters the node.
    is_triggered: bool = False

    # False means the point has been consumed or replaced and should be
    # discarded.  Rules and modification layers check this before acting.
    is_valid: bool = True

    def trigger(self) -> None:
        """Mark this event point as triggered and invalidate it."""
        self.is_triggered = True
        self.is_valid = False

    def invalidate(self) -> None:
        """Invalidate without triggering (e.g. replaced by next-round spawn)."""
        self.is_valid = False

    def __repr__(self) -> str:
        state = "triggered" if self.is_triggered else ("valid" if self.is_valid else "invalid")
        return f"EventPoint({self.event_type.value}, pos={self.pos}, {state})"
