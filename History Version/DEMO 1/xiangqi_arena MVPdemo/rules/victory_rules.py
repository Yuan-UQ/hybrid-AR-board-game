from core.enums import PieceType, Side, VictoryStatus
from state.game_state import GameState


def evaluate_victory(state: GameState) -> VictoryStatus:
    red_general = next((piece for piece in state.pieces.values() if piece.side is Side.RED and piece.piece_type is PieceType.GENERAL), None)
    black_general = next((piece for piece in state.pieces.values() if piece.side is Side.BLACK and piece.piece_type is PieceType.GENERAL), None)
    if red_general is not None and red_general.is_dead:
        return VictoryStatus.BLACK_WIN
    if black_general is not None and black_general.is_dead:
        return VictoryStatus.RED_WIN
    if state.players[Side.RED].has_surrendered:
        return VictoryStatus.BLACK_WIN
    if state.players[Side.BLACK].has_surrendered:
        return VictoryStatus.RED_WIN
    if all(player.agreed_to_draw for player in state.players.values()):
        return VictoryStatus.DRAW
    return VictoryStatus.ONGOING
