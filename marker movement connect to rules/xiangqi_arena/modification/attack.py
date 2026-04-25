"""
Apply confirmed attack changes to GameState.

This module is the authoritative writer of combat outcomes.  It calls
rules/damage_rules to compute numbers and then mutates the pieces and board.

Responsibilities (Guide v2 §4.7 / Rulebook V3 §11, §12.3 Phase 5):
- Apply damage to target piece(s).
- Detect newly dead pieces and mark them (piece.mark_dead()).
- Remove dead pieces from board occupancy (dead pieces do not occupy nodes).
- Refresh victory state immediately after any kill (Rulebook V3 §15.1).
- Mark ActionContext.attack_completed = True.
- Append history entries.

Two public functions:
  apply_attack(attacker_id, target_pos, state)
      Single-target attack — used by all pieces except the Cannon.

  apply_cannon_attack(attacker_id, center_pos, state)
      Cross-shaped AOE attack — used by the Cannon only.
      All hits in the AOE are calculated first, then all deaths are processed,
      then victory is checked once.
"""

from __future__ import annotations

from xiangqi_arena.models.piece import Piece
from xiangqi_arena.rules.attack_rules import get_cannon_aoe
from xiangqi_arena.rules.damage_rules import compute_damage
from xiangqi_arena.rules.death_rules import is_piece_dead
from xiangqi_arena.rules.victory_rules import check_victory
from xiangqi_arena.state.game_state import GameState

Pos = tuple[int, int]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def apply_attack(attacker_id: str, target_pos: Pos, state: GameState) -> None:
    """
    Apply a single-target attack by *attacker_id* against the piece at
    *target_pos*.

    Preconditions (caller's responsibility):
    - target_pos is a legal attack target per rules/piece_rules.
    - The game is in ATTACK phase and no attack has been made yet this turn.
    """
    attacker: Piece = state.pieces[attacker_id]
    target_id = state.board.get_piece_id_at(*target_pos)
    if target_id is None:
        raise ValueError(f"No piece at {target_pos} to attack.")
    target: Piece = state.pieces[target_id]

    damage = compute_damage(attacker, target, state)
    target.apply_damage(damage)

    _record_attack(attacker, target, damage, state)

    if is_piece_dead(target):
        _process_death(target, state)

    _refresh_victory(state)

    state.action.attack_completed = True


def apply_cannon_attack(
    attacker_id: str,
    center_pos: Pos,
    state: GameState,
) -> None:
    """
    Apply the Cannon's cross-shaped AOE attack.

    Steps:
    1. Compute which AOE nodes contain enemy pieces.
    2. Compute and apply damage to each.
    3. Process all resulting deaths (board cleanup).
    4. Check victory once after all hits.
    """
    attacker: Piece = state.pieces[attacker_id]
    aoe_nodes = get_cannon_aoe(center_pos, state, attacker.faction)

    hit_pieces: list[tuple[Piece, int]] = []   # (piece, damage)
    for pos in aoe_nodes:
        pid = state.board.get_piece_id_at(*pos)
        if pid is None:
            continue
        target: Piece = state.pieces[pid]
        if not target.is_alive():
            continue
        damage = compute_damage(attacker, target, state)
        target.apply_damage(damage)
        hit_pieces.append((target, damage))
        _record_attack(attacker, target, damage, state)

    # Process all deaths after all hits have been applied
    for target, _ in hit_pieces:
        if is_piece_dead(target) and not target.is_dead:
            _process_death(target, state)

    _refresh_victory(state)

    state.action.attack_completed = True
    state.action.target_pos = center_pos


def apply_skip_attack(state: GameState) -> None:
    """Record that the active player chose not to attack this turn."""
    state.action.attack_skipped = True

    state.history.append({
        "type": "skip_attack",
        "round": state.round_number,
        "faction": state.active_faction.value,
    })


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _process_death(piece: Piece, state: GameState) -> None:
    """
    Formally kill *piece*:
    - Call piece.mark_dead() (sets is_dead=True, is_operable=False).
    - Remove it from board occupancy so the node is treated as empty.
    - Append a death record to history.
    """
    piece.mark_dead()
    # Dead pieces must not occupy nodes (Rulebook V3 §11.4)
    try:
        state.board.remove_piece(*piece.pos)
    except KeyError:
        pass   # already removed (e.g. double-processing guard)

    state.history.append({
        "type": "death",
        "round": state.round_number,
        "faction": piece.faction.value,
        "piece_id": piece.id,
        "pos": piece.pos,
    })


def _refresh_victory(state: GameState) -> None:
    """
    Re-evaluate victory conditions and write the result into state.
    Called immediately after every damage application (Rulebook V3 §15.1:
    game ends *immediately* when the General/Marshal reaches HP ≤ 0).
    """
    result = check_victory(state)
    if result is not state.victory_state:
        state.victory_state = result

        state.history.append({
            "type": "victory",
            "round": state.round_number,
            "result": result.value,
        })


def _record_attack(
    attacker: Piece,
    target: Piece,
    damage: int,
    state: GameState,
) -> None:
    state.history.append({
        "type": "attack",
        "round": state.round_number,
        "attacker_id": attacker.id,
        "target_id": target.id,
        "target_pos": target.pos,
        "damage": damage,
        "target_hp_after": target.hp,
    })
