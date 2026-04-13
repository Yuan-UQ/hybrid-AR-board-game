from dataclasses import dataclass

import pygame

from core.enums import PhaseType, PieceType, VictoryStatus
from main import (
    clear_selection,
    finish_move_with_auto_attack,
    finish_skip_move_with_auto_attack,
    request_draw,
    restart_game,
    select_piece,
    start_current_turn,
    surrender,
)
from rules.movement_rules import legal_moves_for_piece
from state.game_state import GameState

PIECE_LABELS = {
    PieceType.GENERAL: "G",
    PieceType.CHARIOT: "R",
    PieceType.HORSE: "H",
    PieceType.CANNON: "C",
    PieceType.PAWN: "P",
}


@dataclass(slots=True)
class Button:
    key: str
    label: str
    rect: pygame.Rect


class PygameApp:
    def __init__(self, state: GameState) -> None:
        self.state = state
        self.width = 1280
        self.height = 860
        self.margin = 40
        self.cell = 78
        self.board_origin = (70, 100)
        self.board_size = (self.cell * 8, self.cell * 9)
        self.side_panel_x = 860
        self.message = "Press Start Game or Enter to begin."
        self.running = True
        self.move_confirmed = False
        self.buttons: list[Button] = []

        pygame.init()
        pygame.display.set_caption("Xiangqi Arena MVP")
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.SysFont("microsoftyaheiui", 30, bold=True)
        self.body_font = pygame.font.SysFont("microsoftyaheiui", 20)
        self.small_font = pygame.font.SysFont("consolas", 18)
        self.piece_font = pygame.font.SysFont("microsoftyaheiui", 24, bold=True)
        self._build_buttons()

    def _build_buttons(self) -> None:
        labels = [
            ("advance", "Start Game"),
            ("skip", "Skip Move"),
            ("draw", "Draw"),
            ("surrender", "Give Up"),
        ]
        self.buttons = []
        start_x = self.side_panel_x + 8
        start_y = 716
        button_w = 146
        button_h = 44
        gap = 12
        for index, (key, label) in enumerate(labels):
            x = start_x + (index % 2) * (button_w + gap)
            y = start_y + (index // 2) * (button_h + gap)
            rect = pygame.Rect(x, y, button_w, button_h)
            self.buttons.append(Button(key=key, label=label, rect=rect))

    def run(self) -> None:
        while self.running:
            self._handle_events()
            self._render()
            self.clock.tick(60)
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)

    def _handle_keydown(self, key: int) -> None:
        if key == pygame.K_RETURN:
            self.message = self._handle_enter()
            return
        if key == pygame.K_ESCAPE:
            self.message = clear_selection(self.state)
            self.move_confirmed = False
            return
        if key == pygame.K_r:
            self.state = restart_game(self.state)
            self.move_confirmed = False
            self.message = "Game restarted. Press Enter to begin."
            return
        if key == pygame.K_s:
            self.move_confirmed = False
            self.message = finish_skip_move_with_auto_attack(self.state)
            return
        if key == pygame.K_d:
            self.message = request_draw(self.state)
            return
        if key == pygame.K_q:
            self.message = surrender(self.state)
            return

    def _handle_enter(self) -> str:
        if self.state.victory_status is not VictoryStatus.ONGOING:
            return f"Game is over: {self.state.victory_status.name}. Press R to restart."
        if self.state.current_phase is PhaseType.START:
            self.move_confirmed = False
            return start_current_turn(self.state)
        if self.state.current_phase is PhaseType.MOVE:
            piece = self.state.selected_piece()
            if piece is None:
                return "Select one of your pieces first."
            moves = legal_moves_for_piece(self.state, piece)
            if not moves:
                return f"{piece.piece_id} has no legal move. Select another piece or press S to skip."
            self.move_confirmed = True
            return f"Move confirmed for {piece.piece_id}. Click a highlighted destination."
        return "Movement is automatic after selecting and confirming a piece."

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for button in self.buttons:
            if button.rect.collidepoint(pos):
                self._trigger_button(button.key)
                return
        position = self._screen_to_board(pos)
        if position is None:
            return
        self.message = self._handle_board_click(position)

    def _trigger_button(self, key: str) -> None:
        if key == "advance":
            self.message = self._handle_enter()
        elif key == "skip":
            self.move_confirmed = False
            self.message = finish_skip_move_with_auto_attack(self.state)
        elif key == "draw":
            self.message = request_draw(self.state)
        elif key == "surrender":
            self.message = surrender(self.state)

    def _board_to_screen(self, position: tuple[int, int]) -> tuple[int, int]:
        x, y = position
        origin_x, origin_y = self.board_origin
        return origin_x + x * self.cell, origin_y + (9 - y) * self.cell

    def _screen_to_board(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        px, py = pos
        origin_x, origin_y = self.board_origin
        board_x = round((px - origin_x) / self.cell)
        board_y = 9 - round((py - origin_y) / self.cell)
        if 0 <= board_x <= 8 and 0 <= board_y <= 9:
            center = self._board_to_screen((board_x, board_y))
            if (center[0] - px) ** 2 + (center[1] - py) ** 2 <= 24 ** 2:
                return board_x, board_y
        return None

    def _handle_board_click(self, position: tuple[int, int]) -> str:
        piece_id = self.state.board.get_piece_at(position)
        selected_id = self.state.action.piece_id
        if self.state.victory_status is not VictoryStatus.ONGOING:
            return "Game is over. Press R to restart."
        if self.state.current_phase is PhaseType.MOVE:
            if piece_id is not None:
                self.move_confirmed = False
                message = select_piece(self.state, piece_id)
                if message.startswith("Selected"):
                    piece = self.state.pieces[piece_id]
                    moves = legal_moves_for_piece(self.state, piece)
                    return f"{message} Recommended moves: {moves}. Press Enter to confirm movement."
                return message
            if selected_id is None:
                return "Select a piece first."
            if not self.move_confirmed:
                return "Press Enter to confirm this piece before moving."
            selected_piece = self.state.pieces[selected_id]
            if position not in legal_moves_for_piece(self.state, selected_piece):
                return "Click one of the highlighted recommended destinations."
            self.move_confirmed = False
            return finish_move_with_auto_attack(self.state, selected_id, position)
        return "Board click is only active in MOVE phase."

    def _render(self) -> None:
        self.screen.fill((241, 232, 214))
        self._draw_background()
        self._draw_board()
        self._draw_highlights()
        self._draw_pieces()
        self._draw_side_panel()
        pygame.display.flip()

    def _draw_background(self) -> None:
        pygame.draw.rect(self.screen, (228, 210, 180), pygame.Rect(34, 48, 760, 776), border_radius=24)
        pygame.draw.rect(self.screen, (248, 241, 228), pygame.Rect(820, 48, 410, 776), border_radius=24)
        pygame.draw.rect(self.screen, (186, 158, 118), pygame.Rect(820, 48, 410, 776), 2, border_radius=24)

    def _draw_board(self) -> None:
        origin_x, origin_y = self.board_origin
        board_w, board_h = self.board_size
        pygame.draw.rect(
            self.screen,
            (196, 160, 102),
            pygame.Rect(origin_x - 42, origin_y - 42, board_w + 84, board_h + 84),
            border_radius=22,
        )
        for x in range(9):
            start = (origin_x + x * self.cell, origin_y)
            end = (origin_x + x * self.cell, origin_y + board_h)
            pygame.draw.line(self.screen, (73, 50, 38), start, end, 3)
        for y in range(10):
            start = (origin_x, origin_y + y * self.cell)
            end = (origin_x + board_w, origin_y + y * self.cell)
            pygame.draw.line(self.screen, (73, 50, 38), start, end, 3)
        pygame.draw.rect(
            self.screen,
            (183, 148, 93),
            pygame.Rect(origin_x - 10, origin_y + 4 * self.cell + 8, board_w + 20, self.cell - 16),
            border_radius=8,
        )
        river = self.title_font.render("RIVER", True, (92, 62, 44))
        self.screen.blit(river, river.get_rect(center=(origin_x + board_w // 2, origin_y + 4 * self.cell + self.cell // 2)))
        for x in range(9):
            label = self.small_font.render(str(x), True, (42, 30, 24))
            self.screen.blit(label, (origin_x + x * self.cell - 5, origin_y + board_h + 16))
        for y in range(10):
            label = self.small_font.render(str(9 - y), True, (42, 30, 24))
            self.screen.blit(label, (origin_x - 28, origin_y + y * self.cell - 9))

    def _draw_highlights(self) -> None:
        piece_id = self.state.action.piece_id
        if piece_id is None or piece_id not in self.state.pieces:
            return
        piece = self.state.pieces[piece_id]
        if piece.is_dead:
            return
        selected_center = self._board_to_screen(piece.position)
        pygame.draw.circle(self.screen, (241, 196, 15), selected_center, 32, 5)
        if self.state.current_phase is PhaseType.MOVE:
            for position in legal_moves_for_piece(self.state, piece):
                color = (46, 204, 113) if self.move_confirmed else (52, 152, 219)
                self._draw_target_marker(position, color)

    def _draw_target_marker(self, position: tuple[int, int], color: tuple[int, int, int]) -> None:
        center = self._board_to_screen(position)
        pygame.draw.circle(self.screen, color, center, 13)
        pygame.draw.circle(self.screen, (255, 248, 230), center, 6)

    def _draw_pieces(self) -> None:
        for piece in self.state.pieces.values():
            if piece.is_dead:
                continue
            center = self._board_to_screen(piece.position)
            fill = (191, 54, 54) if piece.side.name == "RED" else (53, 58, 66)
            text_color = (255, 244, 226) if piece.side.name == "RED" else (225, 232, 236)
            pygame.draw.circle(self.screen, fill, center, 26)
            pygame.draw.circle(self.screen, (251, 235, 208), center, 26, 3)
            label = self.piece_font.render(PIECE_LABELS[piece.piece_type], True, text_color)
            self.screen.blit(label, label.get_rect(center=center))
            hp_tag = self.small_font.render(str(piece.hp), True, (250, 250, 250))
            self.screen.blit(hp_tag, (center[0] + 18, center[1] - 28))
            self._draw_hp_bar(center, piece.hp, piece.max_hp)
        for event_point in self.state.event_points:
            if not event_point.active:
                continue
            center = self._board_to_screen(event_point.position)
            color = {
                "AMMO": (243, 156, 18),
                "MEDICAL": (39, 174, 96),
                "TRAP": (142, 68, 173),
            }[event_point.event_type.name]
            pygame.draw.circle(self.screen, color, center, 11)

    def _draw_hp_bar(self, center: tuple[int, int], hp: int, max_hp: int) -> None:
        width = 48
        height = 7
        x = center[0] - width // 2
        y = center[1] + 32
        ratio = max(0.0, min(1.0, hp / max_hp))
        fill_width = int(width * ratio)
        if ratio > 0.5:
            fill = (39, 174, 96)
        elif ratio > 0.25:
            fill = (241, 196, 15)
        else:
            fill = (231, 76, 60)
        pygame.draw.rect(self.screen, (42, 30, 24), pygame.Rect(x, y, width, height), border_radius=3)
        if fill_width:
            pygame.draw.rect(self.screen, fill, pygame.Rect(x, y, fill_width, height), border_radius=3)

    def _draw_side_panel(self) -> None:
        x = self.side_panel_x
        self._draw_top_summary(pygame.Rect(60, 24, 1170, 58))
        self._draw_panel_box(pygame.Rect(x, 110, 320, 260), "Status")
        self._draw_status_summary(pygame.Rect(x + 18, 150, 284, 204))
        self._draw_panel_box(pygame.Rect(x, 390, 320, 290), "Event")
        self._draw_event_summary(pygame.Rect(x + 18, 430, 284, 228))
        self._draw_buttons()
        self._blit_text(self.small_font, "Keyboard: Enter / Esc / R / S / D / Q", (98, 84, 68), (x + 8, 676))

    def _draw_buttons(self) -> None:
        for button in self.buttons:
            pygame.draw.rect(self.screen, (79, 93, 85), button.rect, border_radius=12)
            pygame.draw.rect(self.screen, (204, 173, 114), button.rect, 2, border_radius=12)
            label = self.body_font.render(button.label, True, (250, 246, 237))
            self.screen.blit(label, label.get_rect(center=button.rect.center))

    def _draw_panel_box(self, rect: pygame.Rect, title: str) -> None:
        pygame.draw.rect(self.screen, (236, 227, 212), rect, border_radius=18)
        pygame.draw.rect(self.screen, (176, 149, 111), rect, 2, border_radius=18)
        self._blit_text(self.body_font, title, (92, 62, 44), (rect.x + 18, rect.y + 14))

    def _draw_top_summary(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, (248, 241, 228), rect, border_radius=16)
        pygame.draw.rect(self.screen, (176, 149, 111), rect, 2, border_radius=16)
        labels = [
            ("Player", self.state.current_side.name),
            ("Round", str(self.state.round_number)),
            ("Phase", self.state.current_phase.name),
            ("Result", self.state.victory_status.name),
        ]
        section_width = rect.width // len(labels)
        for index, (title, value) in enumerate(labels):
            section_x = rect.x + 22 + index * section_width
            self._blit_text(self.small_font, title, (120, 92, 68), (section_x, rect.y + 10))
            self._blit_text(self.body_font, value, (56, 42, 31), (section_x, rect.y + 28))

    def _draw_status_summary(self, rect: pygame.Rect) -> None:
        selected = self.state.selected_piece()
        lines = [
            f"Current: {self.state.current_side.name}",
            f"Selected: {selected.piece_id if selected else 'None'}",
        ]
        if selected and not selected.is_dead:
            lines.extend(
                [
                    f"Type: {selected.piece_type.name}",
                    f"HP: {selected.hp}/{selected.max_hp}",
                    f"ATK: {selected.atk}",
                    "DEAD: NO",
                    f"Pos: {selected.position}",
                    f"Phase: {self.state.current_phase.name}",
                    f"Result: {self.state.victory_status.name}",
                ]
            )
        elif selected and selected.is_dead:
            lines.extend(
                [
                    f"Type: {selected.piece_type.name}",
                    "HP: 0",
                    f"ATK: {selected.atk}",
                    "DEAD: YES",
                    f"Phase: {self.state.current_phase.name}",
                    f"Result: {self.state.victory_status.name}",
                ]
            )
        else:
            red_alive = sum(1 for piece in self.state.pieces.values() if piece.side.name == "RED" and not piece.is_dead)
            black_alive = sum(1 for piece in self.state.pieces.values() if piece.side.name == "BLACK" and not piece.is_dead)
            red_dead = sum(1 for piece in self.state.pieces.values() if piece.side.name == "RED" and piece.is_dead)
            black_dead = sum(1 for piece in self.state.pieces.values() if piece.side.name == "BLACK" and piece.is_dead)
            lines.extend(
                [
                    f"Red ALIVE: {red_alive}",
                    f"Red DEAD: {red_dead}",
                    f"Black ALIVE: {black_alive}",
                    f"Black DEAD: {black_dead}",
                    f"Phase: {self.state.current_phase.name}",
                    f"Result: {self.state.victory_status.name}",
                ]
            )
        y = rect.y
        for line in lines:
            self._blit_text(self.body_font, line, (62, 49, 38), (rect.x, y))
            y += 20

    def _draw_event_summary(self, rect: pygame.Rect) -> None:
        event_lines = self._split_log_text(self.message)
        active_events = [
            f"{event.event_type.name} at {event.position}"
            for event in self.state.event_points
            if event.active
        ]
        if active_events:
            event_lines.extend(active_events[:3])
        elif self.state.history:
            event_lines.extend(f"Log: {line}" for line in self.state.history[-3:])
        else:
            event_lines.append("No event yet.")

        previous_clip = self.screen.get_clip()
        self.screen.set_clip(rect)
        y = rect.y
        for line in event_lines:
            if y + self.body_font.get_linesize() > rect.bottom:
                self._blit_text(self.body_font, "...", (62, 49, 38), (rect.x, max(rect.y, rect.bottom - self.body_font.get_linesize())))
                break
            y = self._draw_wrapped_text(line, rect.x, y, rect.width, self.body_font, (62, 49, 38))
            y += 8
        self.screen.set_clip(previous_clip)

    def _split_log_text(self, text: str) -> list[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines or [""]

    def _draw_wrapped_text(self, text: str, x: int, y: int, width: int, font: pygame.font.Font, color: tuple[int, int, int]) -> int:
        words = text.split()
        if not words:
            return y
        current = words[0]
        line_y = y
        for word in words[1:]:
            trial = f"{current} {word}"
            if font.size(trial)[0] <= width:
                current = trial
            else:
                self._blit_text(font, current, color, (x, line_y))
                line_y += font.get_linesize()
                current = word
        self._blit_text(font, current, color, (x, line_y))
        return line_y + font.get_linesize()

    def _blit_text(self, font: pygame.font.Font, text: str, color: tuple[int, int, int], pos: tuple[int, int]) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, pos)
