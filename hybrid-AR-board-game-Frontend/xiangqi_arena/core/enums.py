"""
Project-wide enums for Xiangqi Arena.

Keeping enums centralized avoids scattered string literals and improves
consistency across state/rules/modification/ui layers.
"""

from enum import Enum, auto


class Faction(Enum):
    """Which side a piece or player belongs to."""
    HumanSide = "HumanSide"
    OrcSide = "OrcSide"

    def opponent(self) -> "Faction":
        return Faction.OrcSide if self is Faction.HumanSide else Faction.HumanSide


class PieceType(Enum):
    """All piece types used in Xiangqi Arena (both sides share the same types)."""
    LEADER = "leader"   # 将 / 帅 — confined to own palace
    ARCHER    = "archer"      # 车 (Archer) — orthogonal, up to 3 nodes
    LANCER   = "lancer"     # 马 — L-shape with blocking rule
    WIZARD  = "wizard"    # 炮 — moves up to 2, attacks at exactly 3 + cross AOE
    SOLDIER    = "soldier"      # 兵 / 卒 — forward-only before river, adds sides after


class EventPointType(Enum):
    """
    Types of temporary event points that can spawn on empty board nodes.
    Event points are digital-only; they have no physical marker.
    """
    AMMUNITION = "ammunition"  # piece gains ATK +1 (permanent, stackable)
    MEDICAL    = "medical"     # piece gains HP +1 (clamped to max HP)
    TRAP       = "trap"        # piece loses HP -1


class Phase(Enum):
    """
    The five ordered phases that make up a single turn.
    Transitions must follow the defined order; skipping phases is not allowed.
    """
    START       = 0  # display state; spawn event point on odd rounds
    MOVEMENT    = 1  # player moves one friendly piece or skips
    RECOGNITION = 2  # system scans, validates move, resolves event triggers
    ATTACK      = 3  # player selects attack target/direction or skips
    RESOLVE     = 4  # apply damage/death/victory; end turn and switch sides

    def next(self) -> "Phase":
        """Return the next phase in the fixed turn sequence."""
        members = list(Phase)
        idx = members.index(self)
        if idx + 1 < len(members):
            return members[idx + 1]
        raise ValueError("RESOLVE is the final phase; call end_turn() instead.")


class VictoryState(Enum):
    """Overall game result, updated immediately whenever a win condition is met."""
    ONGOING   = "ongoing"
    HumanSide_WIN   = "HumanSide_win"
    OrcSide_WIN = "OrcSide_win"
    DRAW      = "draw"        # mutually agreed draw
