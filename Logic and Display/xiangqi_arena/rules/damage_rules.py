"""
Combat numerical calculations.

All functions return computed values only. No state mutation happens here.

Damage resolution order (Rulebook V3 §11):
  1. Base damage = attacker.atk  (includes permanent ammo buffs already)
  2. Soldier nearby-ally bonus: if attacker is Soldier and a friendly piece is
     within its 3×3 neighbourhood, add +1 for this attack only (§9.5).
  3. Palace damage reduction: if the TARGET is a Leader/Marshal inside its
     own palace, subtract 1 (minimum 0) (§11.2).

HP change rules:
  - Healing (medical event point): HP + 1, clamped to max_hp (§6.2, §10.2).
  - Trap (event point): HP − 1, clamped to 0.
  - Any damage result < 0 is treated as 0 (§6.2).
"""

from __future__ import annotations

from xiangqi_arena.rules.buff_rules import get_attack_bonus, get_defence_bonus
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.state.game_state import GameState


def compute_damage(
    attacker: Piece,
    target: Piece,
    state: GameState,
) -> int:
    """
    Return the final damage the *target* will receive from *attacker*.

    The result is already clamped to ≥ 0 and accounts for:
    - Soldier nearby-ally bonus (+1 if applicable).
    - Leader/Marshal palace damage reduction (−1 if applicable).
    """
    dmg = attacker.atk
    dmg += get_attack_bonus(attacker, state)
    dmg -= get_defence_bonus(target)

    return max(0, dmg)


def compute_healing() -> int:
    """
    Return the HP gained from a Medical event point (+1, Rulebook V3 §10.2).
    Callers must clamp the result against the piece's max_hp.
    """
    return 1


def compute_trap_damage() -> int:
    """
    Return the HP lost from a Trap event point (1, Rulebook V3 §10.2).
    Callers must clamp to ≥ 0.
    """
    return 1


def clamp_hp(new_hp: int, max_hp: int) -> int:
    """Clamp HP into [0, max_hp]."""
    return max(0, min(new_hp, max_hp))

