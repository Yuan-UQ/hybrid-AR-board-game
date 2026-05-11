"""
Projectile rendering for delayed ranged attacks.
"""

from __future__ import annotations

import math
from pathlib import Path

import pygame

from xiangqi_arena.state.game_state import GameState
from xiangqi_arena.ui.board_renderer import node_to_pixel

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CHARACTER_ROOT = _PROJECT_ROOT / "ArtResource" / "Character"

PROJECTILE_DURATION_MS = 500

_PROJECTILE_CONFIG = {
    "ArcherHuman": {
        "path": _CHARACTER_ROOT / "HumanSide" / "Archer_Human" / "Arrow.png",
        "frame_w": 32,
        "frame_h": 32,
        "target_h": 19,
    },
    "WizardHuman": {
        "path": _CHARACTER_ROOT / "HumanSide" / "Wizard_Human" / "Effect.png",
        "frame_w": 100,
        "frame_h": 100,
        "target_h": 42,
    },
    "ArcherSkeleton": {
        "path": _CHARACTER_ROOT / "OrcSide" / "Archer_Skeleton" / "Arrow.png",
        "frame_w": 32,
        "frame_h": 32,
        "target_h": 19,
    },
    "Slime Orc": {
        "path": _CHARACTER_ROOT / "OrcSide" / "Slime_Orc" / "Effect.png",
        "fallback_path": _CHARACTER_ROOT / "OrcSide" / "Slime_Orc" / "Attack.png",
        "frame_w": 100,
        "frame_h": 100,
        "target_h": 42,
    },
}

_PROJECTILE_FRAMES: dict[str, list[pygame.Surface]] = {}


def is_ranged_attacker(piece_id: str) -> bool:
    return piece_id in _PROJECTILE_CONFIG


def make_pending_ranged_attack(
    attacker_id: str,
    target_pos: tuple[int, int],
    state: GameState,
    is_wizard: bool,
) -> dict:
    attacker = state.pieces[attacker_id]
    return {
        "attacker_id": attacker_id,
        "from_pos": attacker.pos,
        "target_pos": target_pos,
        "is_wizard": is_wizard,
        "started_at": pygame.time.get_ticks(),
        "duration_ms": PROJECTILE_DURATION_MS,
    }


def is_ranged_attack_finished(pending_attack: dict) -> bool:
    elapsed = pygame.time.get_ticks() - int(pending_attack["started_at"])
    return elapsed >= int(pending_attack["duration_ms"])


def draw_ranged_attack(screen: pygame.Surface, pending_attack: dict | None) -> None:
    if pending_attack is None:
        return

    attacker_id = str(pending_attack["attacker_id"])
    if attacker_id not in _PROJECTILE_CONFIG:
        return

    from_pos = pending_attack["from_pos"]
    target_pos = pending_attack["target_pos"]
    elapsed = pygame.time.get_ticks() - int(pending_attack["started_at"])
    duration_ms = max(1, int(pending_attack["duration_ms"]))
    progress = min(1.0, max(0.0, elapsed / duration_ms))

    sx, sy = node_to_pixel(*from_pos)
    tx, ty = node_to_pixel(*target_pos)
    px = int(sx + (tx - sx) * progress)
    py = int(sy + (ty - sy) * progress)

    frames = _get_projectile_frames(attacker_id)
    if not frames:
        return

    frame_idx = int((elapsed // 80) % len(frames))
    frame = frames[frame_idx]
    frame = _rotate_projectile(frame, sx, sy, tx, ty)
    screen.blit(frame, (px - frame.get_width() // 2, py - frame.get_height() // 2))


def _get_projectile_frames(attacker_id: str) -> list[pygame.Surface]:
    if attacker_id not in _PROJECTILE_FRAMES:
        _PROJECTILE_FRAMES[attacker_id] = _load_projectile_frames(attacker_id)
    return _PROJECTILE_FRAMES[attacker_id]


def _load_projectile_frames(attacker_id: str) -> list[pygame.Surface]:
    config = _PROJECTILE_CONFIG[attacker_id]
    path = Path(config["path"])
    if not path.exists() and "fallback_path" in config:
        path = Path(config["fallback_path"])

    sheet = pygame.image.load(str(path)).convert_alpha()
    frame_w = int(config["frame_w"])
    frame_h = int(config["frame_h"])
    target_h = int(config["target_h"])
    frames: list[pygame.Surface] = []

    for x in range(0, sheet.get_width(), frame_w):
        frame = sheet.subsurface(pygame.Rect(x, 0, frame_w, frame_h)).copy()
        bounds = frame.get_bounding_rect(min_alpha=1)
        if bounds.width == 0 or bounds.height == 0:
            continue
        cropped = frame.subsurface(bounds).copy()
        target_w = max(1, int(cropped.get_width() * target_h / cropped.get_height()))
        frames.append(pygame.transform.scale(cropped, (target_w, target_h)))

    return frames


def _rotate_projectile(
    frame: pygame.Surface,
    sx: int,
    sy: int,
    tx: int,
    ty: int,
) -> pygame.Surface:
    dx = tx - sx
    dy = ty - sy
    if dx == 0 and dy == 0:
        return frame
    angle = -math.degrees(math.atan2(dy, dx))
    return pygame.transform.rotate(frame, angle)
