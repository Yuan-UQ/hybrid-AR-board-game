"""
Event point rendering.

Draws all active event points on the board using a distinctive icon per type:
  Ammunition → orange diamond  (ATK +2)
  Medical    → green cross     (HP +1)
  Trap       → purple X        (HP -1)
"""

from __future__ import annotations

import math
from pathlib import Path

import pygame

from xiangqi_arena.core.enums import EventPointType
from xiangqi_arena.state.game_state import GameState
from xiangqi_arena.ui.board_renderer import node_to_pixel
from xiangqi_arena.ui.display_config import C_AMMO, C_MED, C_TRAP

_ICON_SIZE = 10   # half-size for drawing shapes
_FLOAT_AMPLITUDE_PX = 5
_FLOAT_SPEED = 0.0035
_GLOW_RADIUS_PAD = 9
_GLOW_ALPHA_BASE = 90
_GLOW_ALPHA_PULSE = 140
_ICON_Y_OFFSET_PX = -17
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_HEAL_EFFECT_PATH = _PROJECT_ROOT / "ArtResource" / "Effect" / "Heal_Effect.png"
_HEAL_EFFECT_FRAME_MS = 120
_HEAL_EFFECT_TARGET_H = 58
_HEAL_EFFECT_FRAMES: list[pygame.Surface] | None = None
_HEAL_EFFECTS: list[dict] = []
_HISTORY_CURSOR = 0


def draw_event_points(
    screen: pygame.Surface,
    state: GameState,
    *,
    draw_heal_effects: bool = True,
) -> None:
    """Draw active event point icons and optional heal effects."""
    _process_heal_effect_history(state)
    ticks = pygame.time.get_ticks()

    for ep in state.event_points:
        if ep.is_valid and not ep.is_triggered:
            px, py = node_to_pixel(*ep.pos)
            float_phase = _event_float_phase(ep.event_type)
            float_offset = int(
                math.sin(ticks * _FLOAT_SPEED + float_phase) * _FLOAT_AMPLITUDE_PX
            )
            py += float_offset + _ICON_Y_OFFSET_PX
            if ep.event_type == EventPointType.AMMUNITION:
                _draw_event_glow(screen, px, py, C_AMMO, ticks, float_phase)
                _draw_diamond(screen, px, py, C_AMMO)
            elif ep.event_type == EventPointType.MEDICAL:
                _draw_event_glow(screen, px, py, C_MED, ticks, float_phase)
                _draw_cross(screen, px, py, C_MED)
            elif ep.event_type == EventPointType.TRAP:
                _draw_event_glow(screen, px, py, C_TRAP, ticks, float_phase)
                _draw_x(screen, px, py, C_TRAP)

    if draw_heal_effects:
        _draw_heal_effects(screen)


def _process_heal_effect_history(state: GameState) -> None:
    global _HISTORY_CURSOR

    if _HISTORY_CURSOR > len(state.history):
        _HISTORY_CURSOR = 0

    for entry in state.history[_HISTORY_CURSOR:]:
        if entry.get("type") != "event_trigger":
            continue
        if entry.get("event_type") != EventPointType.MEDICAL.value:
            continue
        if entry.get("spawn_heal_effect", True) is False:
            continue

        piece = state.pieces.get(str(entry.get("piece_id")))
        pos = entry.get("pos")
        if piece is None or pos is None:
            continue
        if tuple(pos) != piece.pos:
            continue

        _HEAL_EFFECTS.append({
            "pos": tuple(pos),
            "started_at": pygame.time.get_ticks(),
        })

    _HISTORY_CURSOR = len(state.history)


def _draw_heal_effects(screen: pygame.Surface) -> None:
    frames = _get_heal_effect_frames()
    if not frames:
        return

    now = pygame.time.get_ticks()
    duration_ms = len(frames) * _HEAL_EFFECT_FRAME_MS
    active_effects: list[dict] = []

    for effect in _HEAL_EFFECTS:
        elapsed = now - int(effect["started_at"])
        if elapsed >= duration_ms:
            continue

        frame_idx = min(len(frames) - 1, elapsed // _HEAL_EFFECT_FRAME_MS)
        frame = frames[int(frame_idx)]
        px, py = node_to_pixel(*effect["pos"])
        screen.blit(frame, (px - frame.get_width() // 2, py - frame.get_height() // 2))
        active_effects.append(effect)

    _HEAL_EFFECTS[:] = active_effects


def make_pending_heal_effect(pos: tuple[int, int]) -> dict:
    return {"pos": tuple(pos), "started_at": pygame.time.get_ticks()}


def is_pending_heal_effect_finished(effect: dict | None) -> bool:
    if effect is None:
        return True
    frames = _get_heal_effect_frames()
    if not frames:
        return True
    duration_ms = len(frames) * _HEAL_EFFECT_FRAME_MS
    elapsed = pygame.time.get_ticks() - int(effect["started_at"])
    return elapsed >= duration_ms


def draw_pending_heal_effect(screen: pygame.Surface, effect: dict | None) -> None:
    if effect is None:
        return
    frames = _get_heal_effect_frames()
    if not frames:
        return
    elapsed = pygame.time.get_ticks() - int(effect["started_at"])
    frame_idx = min(len(frames) - 1, max(0, elapsed // _HEAL_EFFECT_FRAME_MS))
    frame = frames[int(frame_idx)]
    px, py = node_to_pixel(*effect["pos"])
    screen.blit(frame, (px - frame.get_width() // 2, py - frame.get_height() // 2))


def draw_heal_effect_overlays(screen: pygame.Surface) -> None:
    """Draw queued heal effects (from history) without event point icons."""
    _draw_heal_effects(screen)


def _event_float_phase(event_type: EventPointType) -> float:
    if event_type == EventPointType.AMMUNITION:
        return 0.0
    if event_type == EventPointType.MEDICAL:
        return 1.9
    return 3.8


def _draw_event_glow(
    screen: pygame.Surface,
    px: int,
    py: int,
    colour: tuple[int, int, int],
    ticks: int,
    phase: float,
) -> None:
    pulse = (math.sin(ticks * (_FLOAT_SPEED * 0.8) + phase) + 1.0) * 0.5
    alpha = int(_GLOW_ALPHA_BASE + _GLOW_ALPHA_PULSE * pulse)
    radius = _ICON_SIZE + _GLOW_RADIUS_PAD + int(2 * pulse)
    glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    # Soft radial gradient glow: layered circles from outer to inner.
    for r in range(radius, 0, -1):
        t = r / max(1, radius)   # outer=1, inner≈0
        layer_alpha = int(alpha * (1.0 - t) ** 1.25)
        if layer_alpha <= 0:
            continue
        pygame.draw.circle(glow, (*colour, layer_alpha), (radius, radius), r)

    # Bright core to keep icon center readable.
    core_r = max(1, radius // 3)
    pygame.draw.circle(glow, (*colour, min(255, alpha + 55)), (radius, radius), core_r)
    screen.blit(glow, (px - radius, py - radius))


def _get_heal_effect_frames() -> list[pygame.Surface]:
    global _HEAL_EFFECT_FRAMES
    if _HEAL_EFFECT_FRAMES is None:
        _HEAL_EFFECT_FRAMES = _load_heal_effect_frames()
    return _HEAL_EFFECT_FRAMES


def _load_heal_effect_frames() -> list[pygame.Surface]:
    sheet = pygame.image.load(str(_HEAL_EFFECT_PATH)).convert_alpha()
    frames: list[pygame.Surface] = []
    frame_w = 100
    frame_h = 100

    for x in range(0, sheet.get_width(), frame_w):
        frame = sheet.subsurface(pygame.Rect(x, 0, frame_w, frame_h)).copy()
        bounds = frame.get_bounding_rect(min_alpha=1)
        if bounds.width == 0 or bounds.height == 0:
            continue
        cropped = frame.subsurface(bounds).copy()
        target_w = max(1, int(cropped.get_width() * _HEAL_EFFECT_TARGET_H / cropped.get_height()))
        frames.append(pygame.transform.scale(cropped, (target_w, _HEAL_EFFECT_TARGET_H)))

    return frames


# ---------------------------------------------------------------------------
# Shape helpers
# ---------------------------------------------------------------------------

def _draw_diamond(surf: pygame.Surface, cx: int, cy: int,
                  colour: tuple) -> None:
    """Pixel-art diamond icon."""
    unit = 3
    layout = {
        -2: [0],
        -1: [-1, 0, 1],
        0: [-2, -1, 0, 1, 2],
        1: [-1, 0, 1],
        2: [0],
    }
    _draw_pixel_layout(surf, cx, cy, unit, layout, colour)
    _draw_pixel_layout_outline(surf, cx, cy, unit, layout, (240, 240, 240))


def _draw_cross(surf: pygame.Surface, cx: int, cy: int,
                colour: tuple) -> None:
    """Pixel-art plus icon."""
    unit = 3
    layout = {
        -2: [0],
        -1: [0],
        0: [-2, -1, 0, 1, 2],
        1: [0],
        2: [0],
    }
    _draw_pixel_layout(surf, cx, cy, unit, layout, colour)
    _draw_pixel_layout_outline(surf, cx, cy, unit, layout, (240, 240, 240))


def _draw_x(surf: pygame.Surface, cx: int, cy: int,
            colour: tuple) -> None:
    """Pixel-art X icon."""
    unit = 3
    layout = {
        -2: [-2, 2],
        -1: [-1, 1],
        0: [0],
        1: [-1, 1],
        2: [-2, 2],
    }
    _draw_pixel_layout(surf, cx, cy, unit, layout, colour)
    _draw_pixel_layout_outline(surf, cx, cy, unit, layout, (240, 240, 240))


def _draw_pixel_layout(
    surf: pygame.Surface,
    cx: int,
    cy: int,
    unit: int,
    layout: dict[int, list[int]],
    colour: tuple[int, int, int],
) -> None:
    for gy, row in layout.items():
        for gx in row:
            rect = pygame.Rect(cx + gx * unit, cy + gy * unit, unit, unit)
            pygame.draw.rect(surf, colour, rect)


def _draw_pixel_layout_outline(
    surf: pygame.Surface,
    cx: int,
    cy: int,
    unit: int,
    layout: dict[int, list[int]],
    outline: tuple[int, int, int],
) -> None:
    pixels = {(gx, gy) for gy, row in layout.items() for gx in row}
    for gx, gy in pixels:
        if (gx - 1, gy) not in pixels or (gx + 1, gy) not in pixels or (gx, gy - 1) not in pixels or (gx, gy + 1) not in pixels:
            rect = pygame.Rect(cx + gx * unit, cy + gy * unit, unit, unit)
            pygame.draw.rect(surf, outline, rect, width=1)
