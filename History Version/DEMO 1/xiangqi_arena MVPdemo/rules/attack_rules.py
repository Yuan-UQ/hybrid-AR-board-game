from dataclasses import dataclass

from core.enums import PieceType
from core.utils import Position, add_position, orthogonal_line
from models.piece import Piece
from state.game_state import GameState

from rules.movement_rules import HORSE_JUMPS, ORTHOGONAL_DIRECTIONS, _general_moves, _pawn_moves


@dataclass(slots=True)
class CannonAttackProfile:
    direction: Position
    center: Position
    affected_positions: list[Position]
    target_ids: list[str]


def _enemy_at(state: GameState, piece: Piece, position: Position) -> str | None:
    target_id = state.board.get_piece_at(position)
    if target_id is None:
        return None
    target = state.pieces[target_id]
    if target.is_dead or target.side is piece.side:
        return None
    return target_id


def _general_attacks(state: GameState, piece: Piece) -> list[Position]:
    return [position for position in _general_moves(piece) if _enemy_at(state, piece, position)]


def _chariot_attacks(state: GameState, piece: Piece) -> list[Position]:
    attacks: list[Position] = []
    for direction in ORTHOGONAL_DIRECTIONS:
        for position in orthogonal_line(piece.position, direction, 3):
            target_id = state.board.get_piece_at(position)
            if target_id is None:
                continue
            target = state.pieces[target_id]
            if not target.is_dead and target.side is not piece.side:
                attacks.append(position)
            break
    return attacks


def _horse_attacks(state: GameState, piece: Piece) -> list[Position]:
    attacks: list[Position] = []
    for jump, leg in HORSE_JUMPS:
        leg_position = add_position(piece.position, leg)
        destination = add_position(piece.position, jump)
        if state.board.is_occupied(leg_position):
            continue
        if _enemy_at(state, piece, destination):
            attacks.append(destination)
    return attacks


def _pawn_attacks(state: GameState, piece: Piece) -> list[Position]:
    return [position for position in _pawn_moves(piece) if _enemy_at(state, piece, position)]


def cannon_attack_profiles(state: GameState, piece: Piece) -> list[CannonAttackProfile]:
    profiles: list[CannonAttackProfile] = []
    if piece.piece_type is not PieceType.CANNON or piece.is_dead:
        return profiles
    for direction in ORTHOGONAL_DIRECTIONS:
        center_line = orthogonal_line(piece.position, direction, 3)
        if len(center_line) < 3:
            continue
        center = center_line[2]
        center_id = _enemy_at(state, piece, center)
        if center_id is None:
            continue
        affected_positions = [
            center,
            add_position(center, (0, 1)),
            add_position(center, (0, -1)),
            add_position(center, (1, 0)),
            add_position(center, (-1, 0)),
        ]
        target_ids: list[str] = []
        for position in affected_positions:
            target_id = _enemy_at(state, piece, position)
            if target_id is not None and target_id not in target_ids:
                target_ids.append(target_id)
        profiles.append(CannonAttackProfile(direction=direction, center=center, affected_positions=affected_positions, target_ids=target_ids))
    return profiles


def legal_attacks_for_piece(state: GameState, piece: Piece) -> list[Position]:
    if piece.is_dead or piece.side is not state.current_side:
        return []
    if piece.piece_type is PieceType.GENERAL:
        return _general_attacks(state, piece)
    if piece.piece_type is PieceType.CHARIOT:
        return _chariot_attacks(state, piece)
    if piece.piece_type is PieceType.HORSE:
        return _horse_attacks(state, piece)
    if piece.piece_type is PieceType.CANNON:
        return [profile.center for profile in cannon_attack_profiles(state, piece)]
    return _pawn_attacks(state, piece)
