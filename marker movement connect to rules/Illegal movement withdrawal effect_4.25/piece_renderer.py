"""
Piece rendering.

Draws live pieces as coloured circles with a type label and an HP bar.
Dead pieces are rendered by death_marker_renderer, not here.
"""

from __future__ import annotations

import pygame

from xiangqi_arena.core.enums import Faction
from xiangqi_arena.state.game_state import GameState
from xiangqi_arena.ui.board_renderer import node_to_pixel
from xiangqi_arena.ui.display_config import (
    C_BLACK_FILL, C_HP_EMPTY, C_HP_FULL, C_PIECE_BORDER, C_PIECE_TEXT,
    C_RED_FILL, HP_BAR_H, HP_BAR_OFFSET_Y, HP_BAR_W, PIECE_LABELS,
    PIECE_RADIUS,
)

_FONT_PIECE: pygame.font.Font | None = None
_FONT_HP: pygame.font.Font | None = None


def _get_fonts() -> tuple[pygame.font.Font, pygame.font.Font]:
    global _FONT_PIECE, _FONT_HP
    if _FONT_PIECE is None:
        _FONT_PIECE = pygame.font.SysFont("Arial", 17, bold=True)
    if _FONT_HP is None:
        _FONT_HP = pygame.font.SysFont("monospace", 10)
    return _FONT_PIECE, _FONT_HP


def _draw_piece_at(
    screen: pygame.Surface,
    px: int,
    py: int,
    piece,
    font_piece: pygame.font.Font,
    font_hp: pygame.font.Font,
) -> None:
    fill = C_RED_FILL if piece.faction == Faction.RED else C_BLACK_FILL

    pygame.draw.circle(screen, (30, 20, 10), (px + 2, py + 2), PIECE_RADIUS)
    pygame.draw.circle(screen, fill, (px, py), PIECE_RADIUS)
    pygame.draw.circle(screen, C_PIECE_BORDER, (px, py), PIECE_RADIUS, 2)

    label = PIECE_LABELS.get(piece.piece_type.value, "?")
    txt_surf = font_piece.render(label, True, C_PIECE_TEXT)
    screen.blit(txt_surf, (px - txt_surf.get_width() // 2,
                           py - txt_surf.get_height() // 2))

    bar_x = px - HP_BAR_W // 2
    bar_y = py + HP_BAR_OFFSET_Y
    pygame.draw.rect(screen, C_HP_EMPTY,
                     pygame.Rect(bar_x, bar_y, HP_BAR_W, HP_BAR_H))
    ratio = max(0.0, piece.hp / piece.max_hp)
    filled_w = int(HP_BAR_W * ratio)
    if filled_w > 0:
        pygame.draw.rect(screen, C_HP_FULL,
                         pygame.Rect(bar_x, bar_y, filled_w, HP_BAR_H))

    hp_txt = font_hp.render(f"{piece.hp}", True, (220, 220, 220))
    screen.blit(hp_txt, (px - hp_txt.get_width() // 2,
                         bar_y + HP_BAR_H + 1))


def draw_pieces(
    screen: pygame.Surface,
    state: GameState,
    hidden_piece_ids: set[str] | None = None,
    rollback_piece_id: str | None = None,
    rollback_from: tuple[int, int] | None = None,
    rollback_to: tuple[int, int] | None = None,
    rollback_started_at_ms: int | None = None,
    rollback_duration_ms: int | None = None,
    current_time_ms: int | None = None,
) -> None:
    """Draw all live pieces plus an optional rollback animation overlay."""
    font_piece, font_hp = _get_fonts()
    hidden_piece_ids = hidden_piece_ids or set()

    for piece in state.pieces.values():
        if piece.is_dead or piece.id in hidden_piece_ids:
            continue

        px, py = node_to_pixel(*piece.pos)
        _draw_piece_at(screen, px, py, piece, font_piece, font_hp)

    if (
        rollback_piece_id is None
        or rollback_from is None
        or rollback_to is None
        or rollback_started_at_ms is None
        or rollback_duration_ms is None
        or current_time_ms is None
    ):
        return

    piece = state.pieces.get(rollback_piece_id)
    if piece is None or piece.is_dead:
        return

    if current_time_ms >= rollback_started_at_ms + rollback_duration_ms:
        return

    progress = max(
        0.0,
        min(1.0, (current_time_ms - rollback_started_at_ms) / max(1, rollback_duration_ms)),
    )
    from_px, from_py = node_to_pixel(*rollback_from)
    to_px, to_py = node_to_pixel(*rollback_to)
    px = int(round(from_px + (to_px - from_px) * progress))
    py = int(round(from_py + (to_py - from_py) * progress))
    _draw_piece_at(screen, px, py, piece, font_piece, font_hp)
