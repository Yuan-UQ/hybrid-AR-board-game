"""
Parse marker identities into arena piece IDs and bootstrap game state.

Rulebook V3 constraints:
- every physical piece must be individually distinguishable
- red/black must be distinguishable
- the three pawns must be tracked separately
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from xiangqi_arena.core.constants import PIECE_STATS
from xiangqi_arena.core.enums import Faction, Phase, PieceType, VictoryState
from xiangqi_arena.flow.action import ActionContext
from xiangqi_arena.models.board import Board
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.models.player import Player
from xiangqi_arena.state.game_state import GameState

Pos = tuple[int, int]

ARUCO_TO_VISION_NAME: dict[int, str] = {
    10: "red_general",
    11: "red_chariot",
    12: "red_horse",
    13: "red_cannon",
    14: "red_pawn_1",
    15: "red_pawn_2",
    16: "red_pawn_3",
    17: "black_general",
    18: "black_chariot",
    19: "black_horse",
    20: "black_cannon",
    21: "black_pawn_1",
    22: "black_pawn_2",
    23: "black_pawn_3",
}

VISION_NAME_TO_ARENA_ID: dict[str, str] = {
    "red_general": "red_general",
    "red_chariot": "red_rook",
    "red_horse": "red_horse",
    "red_cannon": "red_cannon",
    "red_pawn_1": "red_pawn_0",
    "red_pawn_2": "red_pawn_1",
    "red_pawn_3": "red_pawn_2",
    "black_general": "black_general",
    "black_chariot": "black_rook",
    "black_horse": "black_horse",
    "black_cannon": "black_cannon",
    "black_pawn_1": "black_pawn_0",
    "black_pawn_2": "black_pawn_1",
    "black_pawn_3": "black_pawn_2",
}

ARENA_PIECE_IDS: tuple[str, ...] = tuple(VISION_NAME_TO_ARENA_ID.values())
REQUIRED_ARUCO_IDS: tuple[int, ...] = tuple(sorted(ARUCO_TO_VISION_NAME))


@dataclass(frozen=True)
class PieceMarkerInfo:
    aruco_id: int
    vision_name: str
    piece_id: str
    faction: Faction
    piece_type: PieceType


def marker_info_from_aruco(aruco_id: int) -> PieceMarkerInfo:
    """Return normalized arena identity metadata for one ArUco marker."""
    try:
        vision_name = ARUCO_TO_VISION_NAME[aruco_id]
    except KeyError as exc:
        raise ValueError(f"Unknown piece aruco id: {aruco_id}") from exc
    piece_id = VISION_NAME_TO_ARENA_ID[vision_name]
    faction = Faction.RED if piece_id.startswith("red_") else Faction.BLACK
    piece_type = piece_type_from_piece_id(piece_id)
    return PieceMarkerInfo(
        aruco_id=aruco_id,
        vision_name=vision_name,
        piece_id=piece_id,
        faction=faction,
        piece_type=piece_type,
    )


def piece_type_from_piece_id(piece_id: str) -> PieceType:
    """Infer the arena piece type from a normalized piece id."""
    if piece_id.endswith("general"):
        return PieceType.GENERAL
    if piece_id.endswith("rook"):
        return PieceType.ROOK
    if piece_id.endswith("horse"):
        return PieceType.HORSE
    if piece_id.endswith("cannon"):
        return PieceType.CANNON
    if "_pawn_" in piece_id:
        return PieceType.PAWN
    raise ValueError(f"Unknown piece id: {piece_id}")


def normalize_piece_cells(piece_cells_by_aruco: Mapping[int, Pos]) -> dict[str, Pos]:
    """Convert `{aruco_id: (x, y)}` into `{arena_piece_id: (x, y)}`."""
    normalized: dict[str, Pos] = {}
    for aruco_id, pos in piece_cells_by_aruco.items():
        info = marker_info_from_aruco(int(aruco_id))
        normalized[info.piece_id] = (int(pos[0]), int(pos[1]))
    return normalized


def build_game_state_from_snapshot(
    piece_cells: Mapping[str, Pos],
    *,
    active_faction: Faction = Faction.RED,
    round_number: int = 1,
    current_phase: Phase = Phase.START,
) -> GameState:
    """
    Build a full `GameState` from a normalized board snapshot.

    This lets the arena align itself to the first stable physical-board snapshot
    instead of assuming the hard-coded default deployment.
    """
    board = Board()
    pieces: dict[str, Piece] = {}
    red_ids: list[str] = []
    black_ids: list[str] = []

    for piece_id, pos in sorted(piece_cells.items()):
        piece_type = piece_type_from_piece_id(piece_id)
        faction = Faction.RED if piece_id.startswith("red_") else Faction.BLACK
        stats = PIECE_STATS[piece_type]
        piece = Piece(
            id=piece_id,
            faction=faction,
            piece_type=piece_type,
            pos=(int(pos[0]), int(pos[1])),
            hp=stats["hp"],
            max_hp=stats["hp"],
            atk=stats["atk"],
        )
        pieces[piece_id] = piece
        board.place_piece(piece_id, *piece.pos)
        if faction is Faction.RED:
            red_ids.append(piece_id)
        else:
            black_ids.append(piece_id)

    players = {
        Faction.RED: Player(
            faction=Faction.RED,
            piece_ids=sorted(red_ids),
            is_active=active_faction is Faction.RED,
        ),
        Faction.BLACK: Player(
            faction=Faction.BLACK,
            piece_ids=sorted(black_ids),
            is_active=active_faction is Faction.BLACK,
        ),
    }

    return GameState(
        round_number=round_number,
        active_faction=active_faction,
        current_phase=current_phase,
        board=board,
        pieces=pieces,
        players=players,
        event_points=[],
        victory_state=VictoryState.ONGOING,
        action=ActionContext(),
        history=[],
    )

