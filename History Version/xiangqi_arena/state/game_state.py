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
    RED_GENERAL_START, BLACK_GENERAL_START,
    RED_PAWN_STARTS, BLACK_PAWN_STARTS,
    RED_DEPLOY_ROW, BLACK_DEPLOY_ROW,
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
    round_number: int          # starts at 1; increments after Black's turn
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

    def general_of(self, faction: Faction) -> Piece:
        """Return the General / Marshal piece for *faction*."""
        for p in self.pieces_of(faction):
            if p.piece_type is PieceType.GENERAL:
                return p
        raise RuntimeError(f"No General found for {faction}")

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
    red_free: dict[PieceType, tuple[int, int]],
    black_free: dict[PieceType, tuple[int, int]],
) -> GameState:
    """
    Build a GameState from the players' chosen deployment positions.

    Parameters
    ----------
    red_free:
        Positions chosen by Red for its Chariot, Horse, and Cannon.
        Keys must be PieceType.ROOK, PieceType.HORSE, PieceType.CANNON.
        All positions must be on y = RED_DEPLOY_ROW (0) and non-overlapping.
    black_free:
        Same for Black; positions must be on y = BLACK_DEPLOY_ROW (9).

    Raises
    ------
    ValueError
        If any position is invalid or a required piece type is missing.
    """
    for pt in FREE_DEPLOY_PIECE_TYPES:
        if pt not in red_free:
            raise ValueError(f"Missing Red deployment position for {pt}")
        if pt not in black_free:
            raise ValueError(f"Missing Black deployment position for {pt}")
        rx, ry = red_free[pt]
        if ry != RED_DEPLOY_ROW:
            raise ValueError(f"Red {pt} must be on row {RED_DEPLOY_ROW}, got y={ry}")
        bx, by = black_free[pt]
        if by != BLACK_DEPLOY_ROW:
            raise ValueError(f"Black {pt} must be on row {BLACK_DEPLOY_ROW}, got y={by}")

    pieces: dict[str, Piece] = {}

    def add(pid: str, faction: Faction, pt: PieceType, pos: tuple[int, int]) -> None:
        pieces[pid] = _make_piece(pid, faction, pt, pos)

    # --- fixed positions ---
    add("red_general",  Faction.RED,   PieceType.GENERAL, RED_GENERAL_START)
    add("black_general", Faction.BLACK, PieceType.GENERAL, BLACK_GENERAL_START)

    for i, pos in enumerate(RED_PAWN_STARTS):
        add(f"red_pawn_{i}", Faction.RED, PieceType.PAWN, pos)
    for i, pos in enumerate(BLACK_PAWN_STARTS):
        add(f"black_pawn_{i}", Faction.BLACK, PieceType.PAWN, pos)

    # --- player-chosen positions ---
    type_to_name = {
        PieceType.ROOK:   "rook",
        PieceType.HORSE:  "horse",
        PieceType.CANNON: "cannon",
    }
    for pt in FREE_DEPLOY_PIECE_TYPES:
        name = type_to_name[pt]
        add(f"red_{name}",   Faction.RED,   pt, red_free[pt])
        add(f"black_{name}", Faction.BLACK, pt, black_free[pt])

    # --- build board occupancy ---
    board = Board()
    for piece in pieces.values():
        board.place_piece(piece.id, *piece.pos)

    # --- players ---
    red_ids   = [pid for pid, p in pieces.items() if p.faction is Faction.RED]
    black_ids = [pid for pid, p in pieces.items() if p.faction is Faction.BLACK]
    players = {
        Faction.RED:   Player(faction=Faction.RED,   piece_ids=red_ids,   is_active=True),
        Faction.BLACK: Player(faction=Faction.BLACK, piece_ids=black_ids, is_active=False),
    }

    return GameState(
        round_number=1,
        active_faction=Faction.RED,
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
      Red   (y=0): Rook(0,0), Horse(2,0), Cannon(6,0)
      Black (y=9): Rook(0,9), Horse(2,9), Cannon(6,9)
    """
    # Red mirrors Black: Rook ↔ Rook, Horse ↔ Horse, Cannon ↔ Cannon
    # Black: Rook(0,9) Horse(2,9) Cannon(6,9)
    # Red:   Rook(8,0) Horse(6,0) Cannon(2,0)  ← x mirrored on center (x=4)
    return build_initial_state(
        red_free={
            PieceType.ROOK:   (8, 0),
            PieceType.HORSE:  (6, 0),
            PieceType.CANNON: (2, 0),
        },
        black_free={
            PieceType.ROOK:   (0, 9),
            PieceType.HORSE:  (2, 9),
            PieceType.CANNON: (6, 9),
        },
    )


def build_from_scanned_deployment(
    scanned: dict[str, tuple[int, int]],
) -> GameState:
    """
    Build a GameState from piece positions reported by the vision/recognition
    system after scanning the physical board at game start.

    General and Pawn positions are fixed by the rulebook (Rulebook V3 §7.1–7.2)
    and are ignored even if present in ``scanned``.  Only ROOK, HORSE, and
    CANNON positions are extracted from the scan.

    This function is the intended integration point between the recognition
    pipeline and the game-logic layer.  The recognition system should call it
    once, immediately after the initial board scan, before the first turn.

    Parameters
    ----------
    scanned:
        Mapping of piece name → (col, row) as returned by the scanner.
        Required keys for free-deploy pieces::

            "red_rook",   "red_horse",   "red_cannon"
            "black_rook", "black_horse", "black_cannon"

        Additional keys (e.g. "red_general", "red_pawn_0") are silently ignored.

    Returns
    -------
    GameState
        A fully-initialised game state ready for ``flow.turn.start_turn()``.

    Raises
    ------
    ValueError
        Propagated from ``build_initial_state`` if any required piece position
        is missing from ``scanned`` or is on the wrong deployment row.

    Examples
    --------
    Typical call from the recognition integration layer::

        from xiangqi_arena.state.game_state import build_from_scanned_deployment
        from xiangqi_arena.flow.turn import start_turn

        scanned = {
            "red_rook":    (0, 0),
            "red_horse":   (2, 0),
            "red_cannon":  (6, 0),
            "black_rook":  (8, 9),
            "black_horse": (6, 9),
            "black_cannon":(2, 9),
        }
        state = build_from_scanned_deployment(scanned)
        start_turn(state)
    """
    _name_to_type: dict[str, PieceType] = {
        "rook":   PieceType.ROOK,
        "horse":  PieceType.HORSE,
        "cannon": PieceType.CANNON,
    }
    red_free:   dict[PieceType, tuple[int, int]] = {}
    black_free: dict[PieceType, tuple[int, int]] = {}

    for piece_name, pos in scanned.items():
        # Expected format: "<faction>_<type>"  e.g. "red_rook", "black_cannon"
        parts = piece_name.split("_", 1)
        if len(parts) != 2:
            continue
        faction_str, type_str = parts
        pt = _name_to_type.get(type_str)
        if pt is None:
            continue  # general / pawns have fixed positions, skip silently
        if faction_str == "red":
            red_free[pt] = pos
        elif faction_str == "black":
            black_free[pt] = pos

    return build_initial_state(red_free, black_free)
