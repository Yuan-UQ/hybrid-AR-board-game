"""
Single source of truth for runtime game state.

Guide v2 rule: every layer reads from GameState; every confirmed change is
written back through the modification/ layer.  No module should maintain its
own shadow copy of the board or piece list.

`build_initial_state()` constructs a valid starting position.
`build_default_state()` is a zero-configuration helper useful for testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xiangqi_arena.core.constants import (
    PIECE_STATS,
    HUMANSIDE_LEADER_START, ORCSIDE_LEADER_START,
    HUMANSIDE_SOLDIER_STARTS, ORCSIDE_SOLDIER_STARTS,
    HUMANSIDE_DEPLOY_X, ORCSIDE_DEPLOY_X,
    FREE_DEPLOY_PIECE_TYPES,
)
from xiangqi_arena.core.enums import Faction, Phase, PieceType, VictoryState
from xiangqi_arena.flow.action import ActionContext
from xiangqi_arena.models.board import Board
from xiangqi_arena.models.event_point import EventPoint
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.models.player import Player


@dataclass
class GameState:
    """Complete runtime state of one Xiangqi Arena match."""

    # ------------------------------------------------------------------
    # Progression
    # ------------------------------------------------------------------
    round_number: int          # starts at 1; increments after OrcSide's turn
    active_faction: Faction    # whose turn it currently is
    current_phase: Phase       # where we are inside the active turn

    # ------------------------------------------------------------------
    # Board & pieces
    # ------------------------------------------------------------------
    board: Board
    pieces: dict[str, Piece]          # piece_id -> Piece (all, including dead)
    players: dict[Faction, Player]

    # ------------------------------------------------------------------
    # Event points
    # Up to 2 may exist simultaneously; spawned at the start of odd rounds.
    # ------------------------------------------------------------------
    event_points: list[EventPoint]

    # ------------------------------------------------------------------
    # Game result
    # ------------------------------------------------------------------
    victory_state: VictoryState

    # ------------------------------------------------------------------
    # Per-turn transient context  (reset at start of every new turn)
    # ------------------------------------------------------------------
    action: ActionContext

    # ------------------------------------------------------------------
    # History  (optional, useful for debugging and replay)
    # Each entry is a plain dict snapshot written by modification/ layer.
    # ------------------------------------------------------------------
    history: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def get_piece(self, piece_id: str) -> Piece:
        return self.pieces[piece_id]

    def live_pieces(self) -> list[Piece]:
        """Return all pieces that are currently alive."""
        return [p for p in self.pieces.values() if p.is_alive()]

    def pieces_of(self, faction: Faction) -> list[Piece]:
        """Return all pieces (alive and dead) belonging to *faction*."""
        return [p for p in self.pieces.values() if p.faction is faction]

    def live_pieces_of(self, faction: Faction) -> list[Piece]:
        return [p for p in self.pieces_of(faction) if p.is_alive()]

    def leader_of(self, faction: Faction) -> Piece:
        """Return the Leader / Marshal piece for *faction*."""
        for p in self.pieces_of(faction):
            if p.piece_type is PieceType.LEADER:
                return p
        raise RuntimeError(f"No Leader found for {faction}")

    def active_player(self) -> Player:
        return self.players[self.active_faction]

    def is_over(self) -> bool:
        return self.victory_state is not VictoryState.ONGOING

    def start_new_turn(self) -> None:
        """
        Reset the per-turn ActionContext.
        Called by flow/turn.py at the beginning of each new turn.
        """
        self.action.reset()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def _make_piece(
    piece_id: str,
    faction: Faction,
    piece_type: PieceType,
    pos: tuple[int, int],
) -> Piece:
    stats = PIECE_STATS[piece_type]
    return Piece(
        id=piece_id,
        faction=faction,
        piece_type=piece_type,
        pos=pos,
        hp=stats["hp"],
        max_hp=stats["hp"],
        atk=stats["atk"],
    )


def build_initial_state(
    HumanSide_free: dict[PieceType, tuple[int, int]],
    OrcSide_free: dict[PieceType, tuple[int, int]],
) -> GameState:
    """
    Build a GameState from the players' chosen deployment positions.

    Parameters
    ----------
    HumanSide_free:
        Positions chosen by HumanSide for its Archer, Lancer, and Wizard.
        Keys must be PieceType.ARCHER, PieceType.LANCER, PieceType.WIZARD.
        All positions must be on x = HUMANSIDE_DEPLOY_X (9) and non-overlapping.
    OrcSide_free:
        Same for OrcSide; positions must be on x = ORCSIDE_DEPLOY_X (0).

    Raises
    ------
    ValueError
        If any position is invalid or a required piece type is missing.
    """
    for pt in FREE_DEPLOY_PIECE_TYPES:
        if pt not in HumanSide_free:
            raise ValueError(f"Missing HumanSide deployment position for {pt}")
        if pt not in OrcSide_free:
            raise ValueError(f"Missing OrcSide deployment position for {pt}")
        rx, _ = HumanSide_free[pt]
        if rx != HUMANSIDE_DEPLOY_X:
            raise ValueError(f"HumanSide {pt} must be on x={HUMANSIDE_DEPLOY_X}, got x={rx}")
        bx, _ = OrcSide_free[pt]
        if bx != ORCSIDE_DEPLOY_X:
            raise ValueError(f"OrcSide {pt} must be on x={ORCSIDE_DEPLOY_X}, got x={bx}")

    pieces: dict[str, Piece] = {}

    def add(pid: str, faction: Faction, pt: PieceType, pos: tuple[int, int]) -> None:
        pieces[pid] = _make_piece(pid, faction, pt, pos)

    # --- fixed positions ---
    add("GeneralHuman",  Faction.HumanSide,   PieceType.LEADER, HUMANSIDE_LEADER_START)
    add("GeneralOrc", Faction.OrcSide, PieceType.LEADER, ORCSIDE_LEADER_START)

    HumanSide_soldier_names = ("Soldier1Human", "Soldier2Human", "Soldier3Human")
    OrcSide_soldier_names = ("Soldier1Orc", "Soldier2Skeleton", "Soldier3Skeleton")
    for name, pos in zip(HumanSide_soldier_names, HUMANSIDE_SOLDIER_STARTS):
        add(name, Faction.HumanSide, PieceType.SOLDIER, pos)
    for name, pos in zip(OrcSide_soldier_names, ORCSIDE_SOLDIER_STARTS):
        add(name, Faction.OrcSide, PieceType.SOLDIER, pos)

    # --- player-chosen positions ---
    HumanSide_type_to_name = {
        PieceType.ARCHER: "ArcherHuman",
        PieceType.LANCER: "LancerHuman",
        PieceType.WIZARD: "WizardHuman",
    }
    OrcSide_type_to_name = {
        PieceType.ARCHER: "ArcherSkeleton",
        PieceType.LANCER: "RiderOrc",
        PieceType.WIZARD: "Slime Orc",
    }
    for pt in FREE_DEPLOY_PIECE_TYPES:
        add(HumanSide_type_to_name[pt], Faction.HumanSide, pt, HumanSide_free[pt])
        add(OrcSide_type_to_name[pt], Faction.OrcSide, pt, OrcSide_free[pt])

    # --- build board occupancy ---
    board = Board()
    for piece in pieces.values():
        board.place_piece(piece.id, *piece.pos)

    # --- players ---
    HumanSide_ids   = [pid for pid, p in pieces.items() if p.faction is Faction.HumanSide]
    OrcSide_ids = [pid for pid, p in pieces.items() if p.faction is Faction.OrcSide]
    players = {
        Faction.HumanSide:   Player(faction=Faction.HumanSide,   piece_ids=HumanSide_ids,   is_active=True),
        Faction.OrcSide: Player(faction=Faction.OrcSide, piece_ids=OrcSide_ids, is_active=False),
    }

    return GameState(
        round_number=1,
        active_faction=Faction.HumanSide,
        current_phase=Phase.START,
        board=board,
        pieces=pieces,
        players=players,
        event_points=[],
        victory_state=VictoryState.ONGOING,
        action=ActionContext(),
        history=[],
    )


def build_default_state() -> GameState:
    """
    Convenience factory for tests and early development.

    Uses a symmetric default deployment:
      OrcSide (x=0): Archer(0,8), Lancer(0,6), Wizard(0,2)
      HumanSide   (x=9): Archer(9,0), Lancer(9,2), Wizard(9,6)
    """
    return build_initial_state(
        HumanSide_free={
            PieceType.ARCHER:   (9, 0),
            PieceType.LANCER:  (9, 2),
            PieceType.WIZARD: (9, 6),
        },
        OrcSide_free={
            PieceType.ARCHER:   (0, 8),
            PieceType.LANCER:  (0, 6),
            PieceType.WIZARD: (0, 2),
        },
    )
