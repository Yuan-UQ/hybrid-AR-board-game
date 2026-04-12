from random import Random

from core.config import GameConfig
from core.constants import DEFAULT_OPENING_LAYOUT
from core.enums import PhaseType, PieceType, Side, VictoryStatus
from models.board import Board
from models.piece import Piece
from models.player import Player
from rules.attack_rules import cannon_attack_profiles, legal_attacks_for_piece
from rules.event_rules import should_spawn_event, spawn_event
from rules.movement_rules import is_legal_move
from rules.victory_rules import evaluate_victory
from state.game_state import GameState

from modification.attack import queue_attack, resolve_pending_attack
from modification.event import resolve_event_trigger
from modification.move import execute_move


def end_turn(state: GameState) -> None:
    previous_side = state.current_side
    state.current_side = Side.BLACK if previous_side is Side.RED else Side.RED
    if previous_side is Side.BLACK:
        state.round_number += 1
    state.current_phase = PhaseType.START
    state.action.reset()


def build_initial_state(config: GameConfig | None = None) -> GameState:
    config = config or GameConfig()
    rng = Random(config.random_seed)
    board = Board()
    players = {
        Side.RED: Player(side=Side.RED),
        Side.BLACK: Player(side=Side.BLACK),
    }
    pieces: dict[str, Piece] = {}
    for side, layout in DEFAULT_OPENING_LAYOUT.items():
        bundle = [
            Piece.create(f"{side.name.lower()}_general", PieceType.GENERAL, side, layout["general"]),
            Piece.create(f"{side.name.lower()}_chariot", PieceType.CHARIOT, side, layout["chariot"]),
            Piece.create(f"{side.name.lower()}_horse", PieceType.HORSE, side, layout["horse"]),
            Piece.create(f"{side.name.lower()}_cannon", PieceType.CANNON, side, layout["cannon"]),
        ]
        for index, position in enumerate(layout["pawns"], start=1):
            bundle.append(Piece.create(f"{side.name.lower()}_pawn_{index}", PieceType.PAWN, side, position))
        players[side].piece_ids = [piece.piece_id for piece in bundle]
        for piece in bundle:
            pieces[piece.piece_id] = piece
            board.place_piece(piece.piece_id, piece.position)
    return GameState(board=board, players=players, pieces=pieces, config=config, rng=rng)


def restart_game(state: GameState) -> GameState:
    return build_initial_state(state.config)


def select_piece(state: GameState, piece_id: str) -> str:
    piece = state.pieces.get(piece_id)
    if piece is None:
        return "Unknown piece."
    if piece.is_dead:
        return "That piece is dead."
    if piece.side is not state.current_side:
        return "You can only operate your own pieces."
    if state.action.piece_id is not None and state.action.piece_id != piece_id and state.action.has_moved:
        return "Only one piece can be operated each turn."
    state.action.piece_id = piece_id
    return f"Selected {piece_id}."


def clear_selection(state: GameState) -> str:
    if state.action.has_moved:
        return "Selection locked after action."
    state.action.piece_id = None
    state.action.selected_target = None
    state.action.cannon_direction = None
    return "Selection cleared."


def try_move_piece(state: GameState, piece_id: str, destination: tuple[int, int]) -> str:
    if state.victory_status is not VictoryStatus.ONGOING:
        return "Game is over. Press R to restart."
    if state.current_phase is not PhaseType.MOVE:
        return "Move is only allowed in MOVE phase."
    if state.action.has_moved or state.action.skipped_move:
        return "This turn has already moved."
    piece = state.pieces.get(piece_id)
    if piece is None or piece.is_dead or piece.side is not state.current_side:
        return "Invalid piece selection."
    if state.action.piece_id is not None and state.action.piece_id != piece_id:
        return "Only one piece can be operated each turn."
    if not is_legal_move(state, piece, destination):
        return "Illegal move."
    execute_move(state, piece_id, destination)
    return f"Moved {piece_id} to {destination}"


def finish_move_with_auto_attack(state: GameState, piece_id: str, destination: tuple[int, int]) -> str:
    move_message = try_move_piece(state, piece_id, destination)
    if not move_message.startswith("Moved"):
        return move_message

    messages = [move_message]
    event_message = resolve_event_trigger(state, piece_id)
    if event_message:
        messages.append(event_message)
    return finish_selected_piece_action(state, piece_id, messages)


def finish_skip_move_with_auto_attack(state: GameState) -> str:
    if state.victory_status is not VictoryStatus.ONGOING:
        return "Game is over. Press R to restart."
    if state.current_phase is not PhaseType.MOVE:
        return "Skip move is only allowed in MOVE phase."
    piece_id = state.action.piece_id
    if piece_id is None:
        return "Select a piece first, then press S to skip movement and attack."
    piece = state.pieces.get(piece_id)
    if piece is None or piece.is_dead or piece.side is not state.current_side:
        return "Invalid piece selection."
    state.action.skipped_move = True
    return finish_selected_piece_action(state, piece_id, [f"{piece_id} skipped movement."])


def finish_selected_piece_action(state: GameState, piece_id: str, messages: list[str]) -> str:
    piece = state.pieces[piece_id]
    if not piece.is_dead:
        attack_message = queue_first_available_attack(state, piece_id)
        if attack_message:
            messages.append(attack_message)
        else:
            messages.append("No target in range.")

    state.victory_status = evaluate_victory(state)
    if state.victory_status is VictoryStatus.ONGOING:
        end_turn(state)
        messages.append(start_current_turn(state))
    else:
        messages.append(f"Game over: {state.victory_status.name}.")
    return "\n".join(messages)


def queue_first_available_attack(state: GameState, piece_id: str) -> str | None:
    piece = state.pieces.get(piece_id)
    if piece is None or piece.is_dead:
        return None
    if piece.piece_type is PieceType.CANNON:
        profiles = sorted(
            cannon_attack_profiles(state, piece),
            key=lambda profile: (len(profile.target_ids), profile.center[1], profile.center[0]),
            reverse=True,
        )
        if not profiles:
            return None
        queue_attack(state, piece_id, direction=profiles[0].direction)
        return resolve_pending_attack(state)

    targets = sorted(legal_attacks_for_piece(state, piece), key=lambda position: (position[1], position[0]))
    if not targets:
        return None
    queue_attack(state, piece_id, target=targets[0])
    return resolve_pending_attack(state)


def request_draw(state: GameState) -> str:
    if state.victory_status is not VictoryStatus.ONGOING:
        return "Game is already over."
    state.players[state.current_side].agreed_to_draw = True
    if all(player.agreed_to_draw for player in state.players.values()):
        state.victory_status = VictoryStatus.DRAW
        return "Both players agreed to a draw."
    return f"{state.current_side.name} requested a draw. Opponent must also request draw."


def surrender(state: GameState) -> str:
    if state.victory_status is not VictoryStatus.ONGOING:
        return "Game is already over."
    state.players[state.current_side].has_surrendered = True
    state.victory_status = VictoryStatus.BLACK_WIN if state.current_side is Side.RED else VictoryStatus.RED_WIN
    return f"{state.current_side.name} surrendered."


def start_current_turn(state: GameState) -> str:
    if state.victory_status is not VictoryStatus.ONGOING:
        return f"Game is over: {state.victory_status.name}. Press R to restart."
    if state.current_phase is PhaseType.MOVE:
        return f"{state.current_side.name} is already moving."
    messages: list[str] = []
    if should_spawn_event(state):
        spawned = spawn_event(state)
        if spawned is not None:
            messages.append(f"Event spawned: {spawned.event_type.name} at {spawned.position}")
    state.current_phase = PhaseType.MOVE
    messages.append(f"{state.current_side.name} to move.")
    return "\n".join(messages)


def render_board(state: GameState) -> str:
    rows: list[str] = []
    labels = {
        PieceType.GENERAL: "G",
        PieceType.CHARIOT: "R",
        PieceType.HORSE: "H",
        PieceType.CANNON: "C",
        PieceType.PAWN: "P",
    }
    for y in reversed(range(state.board.height)):
        cells: list[str] = []
        for x in range(state.board.width):
            marker = "."
            piece_id = state.board.get_piece_at((x, y))
            if piece_id is not None:
                piece = state.pieces[piece_id]
                marker = labels[piece.piece_type]
                if piece.side is Side.BLACK:
                    marker = marker.lower()
            for event_point in state.event_points:
                if event_point.active and event_point.position == (x, y):
                    marker = event_point.event_type.name[0]
                    break
            cells.append(marker)
        rows.append(f"{y:>2} " + " ".join(cells))
    rows.append("   " + " ".join(str(x) for x in range(state.board.width)))
    return "\n".join(rows)


def render_status(state: GameState) -> str:
    selected = state.selected_piece()
    lines = [
        f"Round {state.round_number} | Side {state.current_side.name} | Phase {state.current_phase.name} | Result {state.victory_status.name}",
        f"Selected: {selected.piece_id if selected else 'none'}",
        render_board(state),
        "Pieces:",
    ]
    for piece in sorted(state.pieces.values(), key=lambda item: (item.side.name, item.piece_id)):
        status = "dead" if piece.is_dead else f"hp={piece.hp}/{piece.max_hp}"
        lines.append(f"  {piece.piece_id:<14} {piece.side.name:<5} {piece.piece_type.name:<7} pos={piece.position} atk={piece.atk} {status}")
    if state.event_points:
        active = [event for event in state.event_points if event.active]
        lines.append("Events: " + (", ".join(f"{event.event_type.name}@{event.position}" for event in active) if active else "none"))
    if state.history:
        lines.append("Recent: " + " | ".join(state.history[-3:]))
    return "\n".join(lines)


def run_cli() -> None:
    state = build_initial_state()
    print("Xiangqi Arena MVP")
    print("Commands: enter, status, select <id>, clear, move <id> x y, skip, draw, surrender, restart, quit")
    print(render_status(state))
    while True:
        try:
            raw = input("> ").strip()
        except EOFError:
            break
        if not raw:
            continue
        parts = raw.split()
        command = parts[0].lower()
        try:
            if command in {"quit", "exit"}:
                break
            if command == "enter":
                message = start_current_turn(state)
            elif command == "status":
                message = render_status(state)
            elif command == "select" and len(parts) == 2:
                message = select_piece(state, parts[1])
            elif command == "clear":
                message = clear_selection(state)
            elif command == "move" and len(parts) == 4:
                message = finish_move_with_auto_attack(state, parts[1], (int(parts[2]), int(parts[3])))
            elif command == "skip":
                message = finish_skip_move_with_auto_attack(state)
            elif command == "draw":
                message = request_draw(state)
            elif command == "surrender":
                message = surrender(state)
            elif command == "restart":
                state = restart_game(state)
                message = "Game restarted."
            else:
                message = "Unknown command or wrong arguments."
        except ValueError:
            message = "Coordinates must be integers."
        print(message)


def main() -> None:
    try:
        from ui.pygame_app import PygameApp
    except ModuleNotFoundError as exc:
        if exc.name != "pygame":
            raise
        run_cli()
        return

    app = PygameApp(build_initial_state())
    app.run()


if __name__ == "__main__":
    main()
