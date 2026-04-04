"""
Attack legality rules.

All functions are pure: read-only access to GameState. No state mutation.

Key rule (Rulebook V3 §8.3):
  For all pieces EXCEPT the Cannon, a valid movement position is also a valid
  attack position.  Concretely: the piece can attack any node it could move to
  if that node were empty, provided the node is occupied by an enemy piece.

Cannon is the exception (Rulebook V3 §9.4):
  - Movement and attack are completely different patterns.
  - Attack: the center point must be exactly CANNON_ATTACK_DIST (3) nodes away
    in one orthogonal direction AND must contain an enemy piece.
  - Effect: cross-shaped AOE centred on that point (5 nodes total).
  - The AOE is NOT blocked by intervening pieces.
  - No friendly fire.

Return types
------------
get_legal_attack_targets(piece, state) -> list[Pos]
    For non-Cannon: list of enemy positions the piece can attack.
    For Cannon: list of valid *center* positions (one per valid direction).

get_cannon_aoe(center_pos, state, attacker_faction) -> list[Pos]
    Returns the up-to-5 nodes affected by a Cannon attack centred at
    *center_pos*, filtered to nodes occupied by enemies (no friendly fire,
    out-of-board nodes excluded).
"""

from __future__ import annotations

from xiangqi_arena.core.constants import CANNON_ATTACK_DIST
from xiangqi_arena.core.enums import PieceType
from xiangqi_arena.core.utils import ORTHOGONAL_DIRECTIONS as _DIRS, is_within_board
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.rules.movement_rules import reachable_nodes
from xiangqi_arena.state.game_state import GameState

Pos = tuple[int, int]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def get_legal_attack_targets(piece: Piece, state: GameState) -> list[Pos]:
    """
    Return all positions the *piece* may legally attack this turn.

    Cannon returns valid center positions (player then picks one direction).
    All other pieces return enemy-occupied positions within their movement reach.
    """
    if piece.is_dead or not piece.is_operable:
        return []
    if piece.piece_type is PieceType.CANNON:
        return _cannon_attack_centers(piece, state)
    return _standard_attack_targets(piece, state)


def get_cannon_aoe(
    center_pos: Pos,
    state: GameState,
    attacker_faction,
) -> list[Pos]:
    """
    Return all nodes (≤ 5) affected by a Cannon attack centred on *center_pos*.

    Affected nodes: center + 4 orthogonal neighbours.
    Filtered to nodes that:
      - are within the board, AND
      - are occupied by an enemy piece (no friendly fire, Rulebook V3 §9.4).
    Empty nodes or friendly-occupied nodes simply have no effect.
    """
    cx, cy = center_pos
    candidates = [(cx, cy),
                  (cx, cy + 1), (cx, cy - 1),
                  (cx - 1, cy), (cx + 1, cy)]
    result: list[Pos] = []
    for pos in candidates:
        if not is_within_board(*pos):
            continue
        pid = state.board.get_piece_id_at(*pos)
        if pid is None:
            continue
        target = state.pieces[pid]
        if target.faction is not attacker_faction and target.is_alive():
            result.append(pos)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _standard_attack_targets(piece: Piece, state: GameState) -> list[Pos]:
    """
    For General / Chariot / Horse / Pawn:
    Attack targets = nodes in movement reach that are occupied by an enemy.
    """
    reachable = reachable_nodes(piece, state)
    targets: list[Pos] = []
    for pos in reachable:
        pid = state.board.get_piece_id_at(*pos)
        if pid is None:
            continue
        occupant = state.pieces[pid]
        if occupant.faction is not piece.faction and occupant.is_alive():
            targets.append(pos)
    return targets


def _cannon_attack_centers(piece: Piece, state: GameState) -> list[Pos]:
    """
    Cannon attack: look exactly CANNON_ATTACK_DIST (3) nodes in each of the 4
    orthogonal directions.  A direction is a valid attack option if:
      - the node exactly 3 steps away is within the board, AND
      - that node is occupied by a live enemy piece.

    The nodes between the Cannon and the center do NOT need to be empty;
    Cannon attacks ignore path blocking (§9.4: "not blocked by pieces").
    """
    x, y = piece.pos
    centers: list[Pos] = []
    for dx, dy in _DIRS:
        cx = x + dx * CANNON_ATTACK_DIST
        cy = y + dy * CANNON_ATTACK_DIST
        if not is_within_board(cx, cy):
            continue
        pid = state.board.get_piece_id_at(cx, cy)
        if pid is None:
            continue
        occupant = state.pieces[pid]
        if occupant.faction is not piece.faction and occupant.is_alive():
            centers.append((cx, cy))
    return centers


# ---------------------------------------------------------------------------
# Convenience: direction vector from attacker to a cannon center
# ---------------------------------------------------------------------------

def cannon_direction_to_center(piece: Piece, center_pos: Pos) -> Pos:
    """
    Return the unit direction vector (dx, dy) from *piece* to *center_pos*.
    Raises ValueError if the center is not exactly CANNON_ATTACK_DIST away.
    """
    px, py = piece.pos
    cx, cy = center_pos
    dx = cx - px
    dy = cy - py
    dist = abs(dx) + abs(dy)
    if dist != CANNON_ATTACK_DIST or (dx != 0 and dy != 0):
        raise ValueError(
            f"center_pos {center_pos} is not exactly {CANNON_ATTACK_DIST} "
            f"orthogonal steps from piece at {piece.pos}."
        )
    return (dx // CANNON_ATTACK_DIST, dy // CANNON_ATTACK_DIST)
