"""
Attack legality rules.

All functions are pure: read-only access to GameState. No state mutation.

Key rule:
  Attack patterns are independent from movement patterns.  Soldiers attack
  forward and laterally only.  All other non-Wizard pieces attack in the four
  orthogonal directions, with path blocking.

Wizard remains the special AOE attacker:
  - Movement and attack are completely different patterns.
  - Attack: the center point must be exactly WIZARD_ATTACK_DIST (3) nodes away
    in one orthogonal direction AND must contain an enemy piece.
  - Effect: cross-shaped AOE centered on that point (5 nodes total).
  - The AOE is NOT blocked by intervening pieces.
  - No friendly fire.

Return types
------------
get_legal_attack_targets(piece, state) -> list[Pos]
    For non-Wizard: list of enemy positions the piece can attack.
    For Wizard: list of valid *center* positions (one per valid direction).

get_wizard_aoe(center_pos, state, attacker_faction) -> list[Pos]
    Returns the up-to-5 nodes affected by a Wizard attack centered at
    *center_pos*, filtered to nodes occupied by enemies (no friendly fire,
    out-of-board nodes excluded).
"""

from __future__ import annotations

from xiangqi_arena.core.constants import ARCHER_MAX_RANGE, WIZARD_ATTACK_DIST
from xiangqi_arena.core.enums import Faction, PieceType
from xiangqi_arena.core.utils import (
    ORTHOGONAL_DIRECTIONS as _DIRS,
    is_within_board,
    lancer_reachable,
)
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.state.game_state import GameState

Pos = tuple[int, int]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def get_legal_attack_targets(piece: Piece, state: GameState) -> list[Pos]:
    """
    Return all positions the *piece* may legally attack this turn.

    Wizard returns valid center positions (player then picks one direction).
    All other pieces return enemy-occupied positions within their attack reach.
    """
    if piece.is_dead or not piece.is_operable:
        return []
    if piece.piece_type is PieceType.WIZARD:
        return _wizard_attack_centers(piece, state)
    return _standard_attack_targets(piece, state)


def get_wizard_aoe(
    center_pos: Pos,
    state: GameState,
    attacker_faction,
) -> list[Pos]:
    """
    Return all nodes (≤ 5) affected by a Wizard attack centered on *center_pos*.

    Affected nodes: center + 4 orthogonal neighbours.
    FilteHumanSide to nodes that:
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
    For non-Wizard pieces:
    - Soldier attacks forward and sideways, never backward.
    - Leader attacks 1 node orthogonally.
    - Archer attacks up to ARCHER_MAX_RANGE orthogonally.
    - Lancer attacks in the old L-shaped pattern.
    """
    if piece.piece_type is PieceType.SOLDIER:
        reachable = _soldier_attack_nodes(piece)
    elif piece.piece_type is PieceType.LEADER:
        reachable = _orthogonal_attack_nodes(piece, state, max_range=1)
    elif piece.piece_type is PieceType.LANCER:
        reachable = lancer_reachable(*piece.pos, state.board.is_occupied)
    else:
        reachable = _orthogonal_attack_nodes(piece, state, max_range=ARCHER_MAX_RANGE)

    targets: list[Pos] = []
    for pos in reachable:
        pid = state.board.get_piece_id_at(*pos)
        if pid is None:
            continue
        occupant = state.pieces[pid]
        if occupant.faction is not piece.faction and occupant.is_alive():
            targets.append(pos)
    return targets


def _soldier_attack_nodes(piece: Piece) -> list[Pos]:
    x, y = piece.pos
    fwd_dx = -1 if piece.faction is Faction.HumanSide else 1
    candidates = [(x + fwd_dx, y), (x, y - 1), (x, y + 1)]
    return [(nx, ny) for nx, ny in candidates if is_within_board(nx, ny)]


def _orthogonal_attack_nodes(piece: Piece, state: GameState, max_range: int) -> list[Pos]:
    x, y = piece.pos
    result: list[Pos] = []
    for dx, dy in _DIRS:
        for step in range(1, max_range + 1):
            nx = x + dx * step
            ny = y + dy * step
            if not is_within_board(nx, ny):
                break
            result.append((nx, ny))
            if state.board.is_occupied(nx, ny):
                break
    return result


def _wizard_attack_centers(piece: Piece, state: GameState) -> list[Pos]:
    """
    Wizard attack: look exactly WIZARD_ATTACK_DIST (3) nodes in each of the 4
    orthogonal directions.  A direction is a valid attack option if:
      - the node exactly 3 steps away is within the board, AND
      - at least one of the 5 cross-AOE nodes (center + 4 orthogonal neighbours)
        is occupied by a live enemy piece.

    The center node itself does NOT need to contain a piece.  The Wizard fires
    at the cross pattern centered 3 steps away; any enemy caught in the cross
    takes damage regardless of whether the center is occupied.

    Example: Wizard at (9,5), center (6,5) is empty but (6,4) and (6,6) have
    enemy pieces → the Wizard may still choose this direction and will hit both.
    """
    x, y = piece.pos
    centers: list[Pos] = []
    for dx, dy in _DIRS:
        cx = x + dx * WIZARD_ATTACK_DIST
        cy = y + dy * WIZARD_ATTACK_DIST
        if not is_within_board(cx, cy):
            continue
        # Valid if at least one enemy is inside the cross AOE
        if get_wizard_aoe((cx, cy), state, piece.faction):
            centers.append((cx, cy))
    return centers


# ---------------------------------------------------------------------------
# Convenience: direction vector from attacker to a wizard center
# ---------------------------------------------------------------------------

def wizard_direction_to_center(piece: Piece, center_pos: Pos) -> Pos:
    """
    Return the unit direction vector (dx, dy) from *piece* to *center_pos*.
    Raises ValueError if the center is not exactly WIZARD_ATTACK_DIST away.
    """
    px, py = piece.pos
    cx, cy = center_pos
    dx = cx - px
    dy = cy - py
    dist = abs(dx) + abs(dy)
    if dist != WIZARD_ATTACK_DIST or (dx != 0 and dy != 0):
        raise ValueError(
            f"center_pos {center_pos} is not exactly {WIZARD_ATTACK_DIST} "
            f"orthogonal steps from piece at {piece.pos}."
        )
    return (dx // WIZARD_ATTACK_DIST, dy // WIZARD_ATTACK_DIST)
