"""
Recognition system interfaces and normalized data contracts.

This layer turns camera / marker recognition output into stable, game-facing
objects. It intentionally stops short of evaluating gameplay legality.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

Pos = tuple[int, int]


@dataclass(frozen=True)
class ScannerMoveEvent:
    """One stable, debounced movement detected by the vision system."""

    aruco_id: int
    vision_name: str
    piece_id: str
    from_pos: Pos
    to_pos: Pos
    timestamp: float


@dataclass(frozen=True)
class ScannerSelectionEvent:
    """One piece marker stayed missing long enough to count as selected."""

    aruco_id: int
    vision_name: str
    piece_id: str
    origin_pos: Pos
    timestamp: float


@dataclass(frozen=True)
class ScannerAttackEvent:
    """One completed physical attack gesture detected by the vision system."""

    aruco_id: int
    vision_name: str
    piece_id: str
    origin_pos: Pos
    contact_pos: Pos
    covered_aruco_id: int | None
    covered_piece_id: str | None
    timestamp: float


@dataclass(frozen=True)
class ScannerSnapshot:
    """Latest stable board snapshot produced by the recognition backend."""

    timestamp: float
    board_visible: bool
    complete: bool
    aruco_cells: dict[int, Pos] = field(default_factory=dict)
    piece_cells: dict[str, Pos] = field(default_factory=dict)
    missing_aruco_ids: tuple[int, ...] = ()
    diagnostics: tuple[str, ...] = ()


class VisionScanner(ABC):
    """Polling interface used by the arena main loop."""

    @abstractmethod
    def poll_snapshot(self) -> ScannerSnapshot | None:
        """Return the latest stable snapshot, or None if no frame is available."""

    @abstractmethod
    def poll_move_events(self) -> list[ScannerMoveEvent]:
        """Return and clear all newly detected movement events."""

    @abstractmethod
    def poll_selection_events(self) -> list[ScannerSelectionEvent]:
        """Return and clear all newly detected missing-marker selection events."""

    @abstractmethod
    def poll_attack_events(self) -> list[ScannerAttackEvent]:
        """Return and clear all newly detected physical attack gestures."""

    @abstractmethod
    def arm_selection_tracking(self, piece_ids: list[str]) -> None:
        """Watch the given piece ids and emit selection when one stays missing."""

    @abstractmethod
    def clear_selection_tracking(self) -> None:
        """Clear any active selection tracking state."""

    @abstractmethod
    def arm_attack_tracking(self, piece_id: str, origin_pos: Pos) -> None:
        """Track physical attack gestures for the currently selected piece only."""

    @abstractmethod
    def clear_attack_tracking(self) -> None:
        """Clear any active physical attack tracking state."""

    @abstractmethod
    def close(self) -> None:
        """Release external resources such as cameras or detector handles."""

