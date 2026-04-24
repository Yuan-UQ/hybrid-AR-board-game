from core.constants import (
    KING,
    AMMO,
    HEAL,
    TRAP,
    AMMO_ATK_BONUS,
    HEAL_HP_RECOVER,
    TRAP_HP_DAMAGE,
    KING_PALACE_DAMAGE_REDUCTION,
)
from rules.common_rules import is_in_own_palace


def calculate_final_damage(attacker, defender, base_damage: int | None = None) -> int:
    """
    Calculate final damage dealt from attacker to defender.

    Rules:
    - default damage uses attacker's current ATK
    - if defender is king and stays in own palace, damage -1
    - final damage cannot be negative
    """
    if attacker is None or defender is None:
        return 0

    damage = attacker.atk if base_damage is None else base_damage

    if defender.piece_type == KING and is_in_own_palace(defender, defender.x, defender.y):
        damage -= KING_PALACE_DAMAGE_REDUCTION

    return max(0, damage)


def apply_damage(attacker, defender, base_damage: int | None = None) -> int:
    """
    Apply damage and return the actual damage dealt.
    """
    if attacker is None or defender is None:
        return 0

    damage = calculate_final_damage(attacker, defender, base_damage)
    defender.take_damage(damage)
    return damage


def apply_heal_effect(piece) -> int:
    """
    Heal piece by fixed amount.
    Returns actual recovered HP.
    """
    if piece is None or not piece.alive:
        return 0

    old_hp = piece.hp
    piece.heal(HEAL_HP_RECOVER)
    return piece.hp - old_hp


def apply_ammo_effect(piece) -> int:
    """
    Permanently increase piece ATK.
    Returns actual ATK increase.
    """
    if piece is None or not piece.alive:
        return 0

    old_atk = piece.atk
    piece.increase_atk(AMMO_ATK_BONUS)
    return piece.atk - old_atk


def apply_trap_effect(piece) -> int:
    """
    Trap deals fixed HP damage.
    Returns actual trap damage.
    """
    if piece is None or not piece.alive:
        return 0

    old_hp = piece.hp
    piece.take_damage(TRAP_HP_DAMAGE)
    return max(0, old_hp - piece.hp)


def apply_event_effect(piece, event_type: str) -> dict:
    """
    Apply event effect to a piece and return a result summary.
    """
    result = {
        "event_type": event_type,
        "hp_change": 0,
        "atk_change": 0,
        "piece_alive": piece.alive if piece is not None else False,
    }

    if piece is None or not piece.alive:
        return result

    if event_type == HEAL:
        healed = apply_heal_effect(piece)
        result["hp_change"] = healed
    elif event_type == AMMO:
        increased = apply_ammo_effect(piece)
        result["atk_change"] = increased
    elif event_type == TRAP:
        trapped = apply_trap_effect(piece)
        result["hp_change"] = -trapped

    result["piece_alive"] = piece.alive
    return result