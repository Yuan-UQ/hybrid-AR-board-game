"""
after move, any current-player piece with available attack can be chosen
if no one can attack, end turn directly
"""

from core.constants import CANNON, PHASE_MOVE, PAWN
from engine.validator import get_piece_attack_positions, can_attack_with_selected_piece
from rules.cannon_rules import get_cannon_attack_targets
from rules.damage_rules import apply_damage
from rules.death_rules import cleanup_dead_pieces
from rules.victory_rules import update_game_over_state
from rules.pawn_rules import pawn_has_local_support


def get_attack_ready_pieces(game_state) -> list:
    """
    Return all current-player pieces that currently have at least one valid attack.
    """
    ready = []
    for piece in game_state.board.get_all_pieces():
        if not piece.alive:
            continue
        if piece.camp != game_state.current_player:
            continue

        attacks = get_piece_attack_positions(game_state.board, piece)
        if attacks:
            ready.append(piece)

    return ready


def start_attack_phase(game_state) -> None:
    """
    After movement, prepare attack phase.
    """
    ready_pieces = get_attack_ready_pieces(game_state)
    game_state.set_attack_ready_pieces(ready_pieces)
    game_state.available_attacks = []
    game_state.available_cannon_centers = []
    game_state.selected_piece = None

    if not ready_pieces:
        game_state.message = "No available attacks. Turn ended automatically."
        _end_turn_after_attack(game_state)
        return

    game_state.message = "Select one of the highlighted pieces to attack."


def select_attack_piece(game_state, piece) -> bool:
    """
    In attack phase, player selects one of the pieces that can attack.
    """
    if piece is None:
        return False

    if piece not in game_state.attack_ready_pieces:
        game_state.message = "This piece has no valid attack."
        return False

    game_state.set_selected_piece(piece)
    positions = get_piece_attack_positions(game_state.board, piece)

    if piece.piece_type == CANNON:
        game_state.set_available_cannon_centers(positions)
        game_state.available_attacks = []
        game_state.message = "Select a cannon attack center."
    else:
        game_state.set_available_attacks(positions)
        game_state.available_cannon_centers = []
        game_state.message = "Select an enemy target to attack."

    return True


def attack_with_selected_piece(game_state, target_x: int, target_y: int) -> bool:
    """
    For cannon, target is center point.
    For others, target is enemy coordinate.
    """
    piece = game_state.selected_piece
    if piece is None:
        game_state.message = "No attack piece selected."
        return False

    if not can_attack_with_selected_piece(game_state, target_x, target_y):
        game_state.message = "Invalid attack."
        return False

    if piece.piece_type == CANNON:
        success = _attack_with_cannon(game_state, piece, target_x, target_y)
    else:
        success = _attack_with_normal_piece(game_state, piece, target_x, target_y)

    if success and not game_state.game_over:
        _end_turn_after_attack(game_state)

    return success


def _attack_with_normal_piece(game_state, attacker, target_x: int, target_y: int) -> bool:
    defender = game_state.board.get_piece_at(target_x, target_y)
    if defender is None or not defender.alive:
        game_state.message = "No valid target."
        return False

    damage_value = attacker.atk
    if attacker.piece_type == PAWN and pawn_has_local_support(game_state.board, attacker):
        damage_value += 1

    damage = apply_damage(attacker, defender, damage_value)
    removed = cleanup_dead_pieces(game_state.board)
    game_over, winner = update_game_over_state(game_state)

    game_state.last_action = ("attack", attacker.id, defender.id, damage)
    game_state.message = f"{attacker.id} attacked {defender.id} for {damage} damage."

    if attacker.piece_type == PAWN and damage_value > attacker.atk:
        game_state.message += " Pawn support bonus applied."

    if removed:
        removed_ids = ", ".join(piece.id for piece in removed)
        game_state.message += f" Removed: {removed_ids}."

    game_state.available_attacks = []
    game_state.available_cannon_centers = []
    if game_over:
        game_state.message += f" Game Over! Winner: {winner}."
    return True


def _attack_with_cannon(game_state, attacker, center_x: int, center_y: int) -> bool:
    targets = get_cannon_attack_targets(game_state.board, attacker, center_x, center_y)
    if not targets:
        game_state.message = "No cannon targets hit."
        return False

    hit_records = []
    for defender in targets:
        damage = apply_damage(attacker, defender)
        hit_records.append((defender.id, damage))

    removed = cleanup_dead_pieces(game_state.board)
    game_over, winner = update_game_over_state(game_state)

    hits_text = ", ".join(f"{target_id}({dmg})" for target_id, dmg in hit_records)
    game_state.last_action = ("cannon_attack", attacker.id, center_x, center_y, hit_records)
    game_state.message = (
        f"{attacker.id} fired cannon at center ({center_x}, {center_y}). Hits: {hits_text}."
    )

    if removed:
        removed_ids = ", ".join(piece.id for piece in removed)
        game_state.message += f" Removed: {removed_ids}."

    game_state.available_attacks = []
    game_state.available_cannon_centers = []
    if game_over:
        game_state.message += f" Game Over! Winner: {winner}."
    return True


def _end_turn_after_attack(game_state) -> None:
    previous_player = game_state.current_player

    game_state.clear_selection()
    game_state.clear_attack_ready_pieces()
    game_state.switch_player()
    game_state.next_round_if_needed(previous_player)
    game_state.set_phase(PHASE_MOVE)

    game_state.message += f" Turn ended. Now it is {game_state.current_player}'s move."