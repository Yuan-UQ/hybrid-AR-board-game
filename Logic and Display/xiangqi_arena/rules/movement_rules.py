"""
Movement legality rules.

All functions are pure: they read GameState / Piece / Board but MUST NOT
mutate any of them.

Architecture note
-----------------
Each helper returns the full set of nodes a piece can *reach* according to
its movement pattern, IGNORING what is sitting at the destination (i.e. it
may include occupied nodes).  `get_legal_moves()` then filters that set to
empty nodes only.  `attack_rules` imports the same helpers and filters to
enemy-occupied nodes instead — this avoids duplicating movement logic.

Piece-by-piece movement rules (Rulebook V3 §9)
-----------------------------------------------
Leader / Marshal  : 1 step orthogonal OR diagonal, within own palace.
Archer (车)          : orthogonal, ≤ 3 nodes, path-blocked.
Lancer              : L-shape with leg-blocking (standard Xiangqi lancer rule).
Wizard             : orthogonal, ≤ 2 nodes, path-blocked, target must be empty.
Soldier               : forward-only before river; forward+lateral after river.
"""

from __future__ import annotations

from xiangqi_arena.core.constants import (
    ARCHER_MAX_RANGE,
    WIZARD_MOVE_MAX,
    PALACE_BOUNDS,
)
from xiangqi_arena.core.enums import Faction, PieceType
from xiangqi_arena.core.utils import (
    ORTHOGONAL_DIRECTIONS,
    has_crossed_river,
    lancer_reachable,
    is_within_board,
)
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.state.game_state import GameState

Pos = tuple[int, int]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_legal_moves(piece: Piece, state: GameState) -> list[Pos]:
    """
    Return every board node the *piece* may legally move to this turn.

    Conditions shared by all pieces:
    - Destination must be within the board.
    - Destination must be EMPTY (Rulebook V3 §8.1).
    - Path may not cross through other pieces (§8.2), per-piece rules apply.
    """
    if piece.is_dead or not piece.is_operable:
        return []
    reachable = _reachable_nodes(piece, state)
    return [pos for pos in reachable if state.board.is_empty(*pos)]


# ---------------------------------------------------------------------------
# Shared reachable-nodes helper (also used by attack_rules)
# ---------------------------------------------------------------------------

def reachable_nodes(piece: Piece, state: GameState) -> list[Pos]:
    """
    Return all nodes the piece can potentially reach by its movement pattern,
    including enemy-occupied nodes (but still applying path-blocking and
    range limits).

    The Wizard is the only piece that has DIFFERENT movement and attack
    patterns; this function returns its *movement* reachable set only.
    Wizard attack logic lives entirely in attack_rules.
    """
    return _reachable_nodes(piece, state)


def _reachable_nodes(piece: Piece, state: GameState) -> list[Pos]:
    dispatch = {
        PieceType.LEADER: _leader_reachable,
        PieceType.ARCHER:    _archer_reachable,
        PieceType.LANCER:   _lancer_reachable,
        PieceType.WIZARD:  _wizard_reachable,
        PieceType.SOLDIER:    _soldier_reachable,
    }
    return dispatch[piece.piece_type](piece, state)


# ---------------------------------------------------------------------------
# Per-piece helpers
# ---------------------------------------------------------------------------

def _leader_reachable(piece: Piece, state: GameState) -> list[Pos]:
    """
    Leader / Marshal: 1 step orthogonal OR diagonal, restricted to palace.
    Rulebook V3 §9.1.
    """
    x, y = piece.pos
    bounds = PALACE_BOUNDS[piece.faction]
    px_min, px_max = bounds["x"]
    py_min, py_max = bounds["y"]

    result: list[Pos] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if px_min <= nx <= px_max and py_min <= ny <= py_max:
                result.append((nx, ny))
    return result


def _archer_reachable(piece: Piece, state: GameState) -> list[Pos]:
    """
    Archer (车): orthogonal up to ARCHER_MAX_RANGE (3), path-blocked.
    Stops at (and includes) the first node that has any piece.
    Rulebook V3 §9.2.
    """
    x, y = piece.pos
    result: list[Pos] = []
    for dx, dy in ORTHOGONAL_DIRECTIONS:
        steps = 0
        cx, cy = x + dx, y + dy
        while is_within_board(cx, cy) and steps < ARCHER_MAX_RANGE:
            result.append((cx, cy))
            if state.board.is_occupied(cx, cy):
                break   # path blocked; the blocking node is included for attacks
            cx += dx
            cy += dy
            steps += 1
    return result


def _lancer_reachable(piece: Piece, state: GameState) -> list[Pos]:
    """
    Lancer: standard Xiangqi L-shape with leg-blocking.
    Rulebook V3 §9.3.
    """
    x, y = piece.pos
    return lancer_reachable(x, y, state.board.is_occupied)


def _wizard_reachable(piece: Piece, state: GameState) -> list[Pos]:
    """
    Wizard MOVEMENT: orthogonal, ≤ WIZARD_MOVE_MAX (2) nodes, path-blocked.
    The Wizard cannot land on an occupied node, and the path is blocked by
    any piece it encounters (§8.2 applies).
    NOTE: Wizard ATTACK is handled entirely in attack_rules — it is a
    completely different pattern (exactly 3 away, cross AOE).
    Rulebook V3 §9.4.
    """
    x, y = piece.pos
    result: list[Pos] = []
    for dx, dy in ORTHOGONAL_DIRECTIONS:
        steps = 0
        cx, cy = x + dx, y + dy
        while is_within_board(cx, cy) and steps < WIZARD_MOVE_MAX:
            if state.board.is_occupied(cx, cy):
                break   # path blocked; occupied node NOT included (Wizard must land on empty)
            result.append((cx, cy))
            cx += dx
            cy += dy
            steps += 1
    return result


def _soldier_reachable(piece: Piece, state: GameState) -> list[Pos]:
    """
    Soldier: forward-only before river; forward + lateral after crossing.
    Diagonal movement is never allowed (Rulebook V3 §9.5).
    """
    x, y = piece.pos
    faction = piece.faction

    # Forward direction: HumanSide advances left; OrcSide advances right.
    fwd_dx = -1 if faction is Faction.HumanSide else 1
    crossed = has_crossed_river(x, y, faction)

    candidates: list[Pos] = [(x + fwd_dx, y)]          # forward always
    if crossed:
        candidates += [(x, y - 1), (x, y + 1)]         # lateral after river

    return [(nx, ny) for nx, ny in candidates if is_within_board(nx, ny)]
