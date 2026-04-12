from core.enums import EventType
from rules.damage_rules import capped_heal
from rules.death_rules import refresh_death_state
from state.game_state import GameState


def resolve_event_trigger(state: GameState, piece_id: str) -> str | None:
    piece = state.pieces[piece_id]
    for event_point in state.event_points:
        if not event_point.active or event_point.position != piece.position:
            continue
        if event_point.event_type is EventType.AMMO:
            piece.atk += 1
            piece.permanent_buffs.append("ammo+1")
            message = f"{piece_id} triggered AMMO, ATK -> {piece.atk}"
        elif event_point.event_type is EventType.MEDICAL:
            capped_heal(piece, 1)
            message = f"{piece_id} triggered MEDICAL, HP -> {piece.hp}"
        else:
            piece.hp -= 1
            refresh_death_state(piece)
            if piece.is_dead:
                state.board.clear_position(piece.position)
            message = f"{piece_id} triggered TRAP, HP -> {piece.hp}"
        event_point.triggered = True
        event_point.active = False
        state.history.append(message)
        return message
    return None
