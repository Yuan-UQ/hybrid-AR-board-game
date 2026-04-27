from core.enums import PieceType
from rules.attack_rules import cannon_attack_profiles
from rules.damage_rules import compute_damage
from rules.death_rules import refresh_death_state
from state.game_state import GameState

from modification.spatial_rule import general_damage_reduction, pawn_attack_bonus

DIR_LABELS = {
    (0, 1): "up",
    (0, -1): "down",
    (-1, 0): "left",
    (1, 0): "right",
}


def _piece_label(piece_id: str) -> str:
    return piece_id.replace("_", " ")


def queue_attack(state: GameState, piece_id: str, target: tuple[int, int] | None = None, direction: tuple[int, int] | None = None) -> None:
    state.action.piece_id = piece_id
    state.action.selected_target = target
    state.action.cannon_direction = direction


def _apply_damage(state: GameState, attacker_id: str, target_id: str) -> int:
    attacker = state.pieces[attacker_id]
    target = state.pieces[target_id]
    bonus = pawn_attack_bonus(state, attacker_id)
    reduction = general_damage_reduction(state, target_id)
    damage = compute_damage(attacker, bonus=bonus, reduction=reduction)
    target.hp -= damage
    if refresh_death_state(target):
        state.board.clear_position(target.position)
    return damage


def resolve_pending_attack(state: GameState) -> str:
    piece_id = state.action.piece_id
    if piece_id is None or state.action.selected_target is None and state.action.cannon_direction is None:
        return "No attack resolved."
    attacker = state.pieces[piece_id]
    if attacker.is_dead:
        return "Selected attacker is dead."
    if attacker.piece_type is PieceType.CANNON:
        return _resolve_cannon_attack(state, piece_id)
    target_id = state.board.get_piece_at(state.action.selected_target)
    if target_id is None:
        return "Attack target missing."
    damage = _apply_damage(state, piece_id, target_id)
    message = f"{_piece_label(piece_id)} hits {_piece_label(target_id)} for {damage}"
    state.history.append(message)
    return message


def _resolve_cannon_attack(state: GameState, piece_id: str) -> str:
    profiles = cannon_attack_profiles(state, state.pieces[piece_id])
    for profile in profiles:
        if profile.direction != state.action.cannon_direction:
            continue
        if not profile.target_ids:
            return "Cannon direction has no enemy targets."
        results: list[str] = []
        for target_id in profile.target_ids:
            damage = _apply_damage(state, piece_id, target_id)
            results.append(f"{_piece_label(target_id)}:{damage}")
        message = f"{_piece_label(piece_id)} cannon {DIR_LABELS.get(profile.direction, profile.direction)} hits {', '.join(results)}"
        state.history.append(message)
        return message
    return "Invalid cannon direction."
