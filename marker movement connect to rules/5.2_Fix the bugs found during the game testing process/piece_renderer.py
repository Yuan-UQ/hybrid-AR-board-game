"""
Piece rendering.

Draws live pieces as coloured circles with a type label and an HP bar.
Dead pieces are rendered by death_marker_renderer, not here.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from xiangqi_arena.core.enums import Faction
from xiangqi_arena.rules.buff_rules import (
    get_attack_effect_bonus,
    get_defence_bonus,
)
from xiangqi_arena.state.game_state import GameState
from xiangqi_arena.ui.board_renderer import node_to_pixel
import xiangqi_arena.ui.display_config as dcfg
from xiangqi_arena.ui.display_config import (
    C_ORCSIDE_FILL, C_HP_EMPTY, C_HP_FULL, C_PIECE_BORDER, C_PIECE_TEXT,
    C_HUMANSIDE_FILL, HP_BAR_H, HP_BAR_OFFSET_Y, HP_BAR_W, PIECE_LABELS,
    PIECE_RADIUS,
)

_FONT_PIECE: pygame.font.Font | None = None
_FONT_HP: pygame.font.Font | None = None
_SPRITE_FRAMES: dict[tuple[str, str], list[pygame.Surface]] = {}
_SPRITE_LAST_X: dict[str, int] = {}
_SPRITE_FACING: dict[str, str] = {}
_SPRITE_LAST_HP: dict[str, int] = {}
_SPRITE_ANIMATIONS: dict[str, dict] = {}
_SPRITE_HIDDEN_AFTER_DEATH: set[str] = set()
_HISTORY_CURSOR: int = 0
_DEATH_BLINK_DURATION_MS = 1000
_DEATH_BLINK_COUNT = 2
_BUFF_FX_HISTORY_CURSOR = 0
_ATTACK_HIT_EFFECT_PATH = Path(__file__).resolve().parents[2] / "ArtResource" / "Effect" / "Attack_effect.png"
_ATTACK_HIT_EFFECT_FRAME_MS = 80
_ATTACK_HIT_EFFECT_TARGET_H = 52
_ATTACK_HIT_EFFECT_FRAMES: list[pygame.Surface] | None = None
_ATTACK_HIT_EFFECTS: list[dict] = []

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_HUMANSIDE_CHARACTER_ROOT = _PROJECT_ROOT / "ArtResource" / "Character" / "HumanSide"
_ORCSIDE_CHARACTER_ROOT = _PROJECT_ROOT / "ArtResource" / "Character" / "OrcSide"
_SPRITE_CONFIG = {
    "GeneralHuman": {
        "path": _HUMANSIDE_CHARACTER_ROOT / "General_Human" / "Idle.png",
        "animations": {
            "Idle": _HUMANSIDE_CHARACTER_ROOT / "General_Human" / "Idle.png",
            "Attack": _HUMANSIDE_CHARACTER_ROOT / "General_Human" / "Attack.png",
            "Death": _HUMANSIDE_CHARACTER_ROOT / "General_Human" / "Death.png",
            "Hurt": _HUMANSIDE_CHARACTER_ROOT / "General_Human" / "Hurt.png",
            "Walk": _HUMANSIDE_CHARACTER_ROOT / "General_Human" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 70,
        "initial_facing": "left",
    },
    "ArcherHuman": {
        "path": _HUMANSIDE_CHARACTER_ROOT / "Archer_Human" / "Idle.png",
        "animations": {
            "Idle": _HUMANSIDE_CHARACTER_ROOT / "Archer_Human" / "Idle.png",
            "Attack": _HUMANSIDE_CHARACTER_ROOT / "Archer_Human" / "Attack.png",
            "Death": _HUMANSIDE_CHARACTER_ROOT / "Archer_Human" / "Death.png",
            "Hurt": _HUMANSIDE_CHARACTER_ROOT / "Archer_Human" / "Hurt.png",
            "Walk": _HUMANSIDE_CHARACTER_ROOT / "Archer_Human" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 58,
        "initial_facing": "left",
    },
    "LancerHuman": {
        "path": _HUMANSIDE_CHARACTER_ROOT / "Rider_Human" / "Idle.png",
        "animations": {
            "Idle": _HUMANSIDE_CHARACTER_ROOT / "Rider_Human" / "Idle.png",
            "Attack": _HUMANSIDE_CHARACTER_ROOT / "Rider_Human" / "Attack.png",
            "Death": _HUMANSIDE_CHARACTER_ROOT / "Rider_Human" / "Death.png",
            "Hurt": _HUMANSIDE_CHARACTER_ROOT / "Rider_Human" / "Hurt.png",
            "Walk": _HUMANSIDE_CHARACTER_ROOT / "Rider_Human" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 89,
        "initial_facing": "left",
    },
    "WizardHuman": {
        "path": _HUMANSIDE_CHARACTER_ROOT / "Wizard_Human" / "Wizard-Idle.png",
        "animations": {
            "Idle": _HUMANSIDE_CHARACTER_ROOT / "Wizard_Human" / "Wizard-Idle.png",
            "Attack": _HUMANSIDE_CHARACTER_ROOT / "Wizard_Human" / "Attack.png",
            "Death": _HUMANSIDE_CHARACTER_ROOT / "Wizard_Human" / "DEATH.png",
            "Hurt": _HUMANSIDE_CHARACTER_ROOT / "Wizard_Human" / "Hurt.png",
            "Walk": _HUMANSIDE_CHARACTER_ROOT / "Wizard_Human" / "Wizard-Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 58,
        "initial_facing": "left",
    },
    "Soldier1Human": {
        "path": _HUMANSIDE_CHARACTER_ROOT / "Soldier1_Human" / "Idle.png",
        "animations": {
            "Idle": _HUMANSIDE_CHARACTER_ROOT / "Soldier1_Human" / "Idle.png",
            "Attack": _HUMANSIDE_CHARACTER_ROOT / "Soldier1_Human" / "Attack.png",
            "AttackBuff": _HUMANSIDE_CHARACTER_ROOT / "Soldier1_Human" / "Attack02.png",
            "Death": _HUMANSIDE_CHARACTER_ROOT / "Soldier1_Human" / "Death.png",
            "Hurt": _HUMANSIDE_CHARACTER_ROOT / "Soldier1_Human" / "Hurt.png",
            "Walk": _HUMANSIDE_CHARACTER_ROOT / "Soldier1_Human" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 58,
        "initial_facing": "left",
    },
    "Soldier2Human": {
        "path": _HUMANSIDE_CHARACTER_ROOT / "Soldier2_Human" / "Idle.png",
        "animations": {
            "Idle": _HUMANSIDE_CHARACTER_ROOT / "Soldier2_Human" / "Idle.png",
            "Attack": _HUMANSIDE_CHARACTER_ROOT / "Soldier2_Human" / "Attack.png",
            "AttackBuff": _HUMANSIDE_CHARACTER_ROOT / "Soldier2_Human" / "Attack02.png",
            "Death": _HUMANSIDE_CHARACTER_ROOT / "Soldier2_Human" / "Death.png",
            "Hurt": _HUMANSIDE_CHARACTER_ROOT / "Soldier2_Human" / "Hurt.png",
            "Walk": _HUMANSIDE_CHARACTER_ROOT / "Soldier2_Human" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 58,
        "initial_facing": "left",
    },
    "Soldier3Human": {
        "path": _HUMANSIDE_CHARACTER_ROOT / "Soldier3_Human" / "Idle.png",
        "animations": {
            "Idle": _HUMANSIDE_CHARACTER_ROOT / "Soldier3_Human" / "Idle.png",
            "Attack": _HUMANSIDE_CHARACTER_ROOT / "Soldier3_Human" / "Attack.png",
            "AttackBuff": _HUMANSIDE_CHARACTER_ROOT / "Soldier3_Human" / "Attack02.png",
            "Death": _HUMANSIDE_CHARACTER_ROOT / "Soldier3_Human" / "Death.png",
            "Hurt": _HUMANSIDE_CHARACTER_ROOT / "Soldier3_Human" / "Hurt.png",
            "Walk": _HUMANSIDE_CHARACTER_ROOT / "Soldier3_Human" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 58,
        "initial_facing": "left",
    },
    "GeneralOrc": {
        "path": _ORCSIDE_CHARACTER_ROOT / "General_Orc" / "Idle.png",
        "animations": {
            "Idle": _ORCSIDE_CHARACTER_ROOT / "General_Orc" / "Idle.png",
            "Attack": _ORCSIDE_CHARACTER_ROOT / "General_Orc" / "Attack.png",
            "Death": _ORCSIDE_CHARACTER_ROOT / "General_Orc" / "Death.png",
            "Hurt": _ORCSIDE_CHARACTER_ROOT / "General_Orc" / "Hurt.png",
            "Walk": _ORCSIDE_CHARACTER_ROOT / "General_Orc" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 70,
        "initial_facing": "right",
    },
    "ArcherSkeleton": {
        "path": _ORCSIDE_CHARACTER_ROOT / "Archer_Skeleton" / "Idle.png",
        "animations": {
            "Idle": _ORCSIDE_CHARACTER_ROOT / "Archer_Skeleton" / "Idle.png",
            "Attack": _ORCSIDE_CHARACTER_ROOT / "Archer_Skeleton" / "Attack.png",
            "Death": _ORCSIDE_CHARACTER_ROOT / "Archer_Skeleton" / "Death.png",
            "Hurt": _ORCSIDE_CHARACTER_ROOT / "Archer_Skeleton" / "Hurt.png",
            "Walk": _ORCSIDE_CHARACTER_ROOT / "Archer_Skeleton" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 58,
        "initial_facing": "right",
    },
    "RiderOrc": {
        "path": _ORCSIDE_CHARACTER_ROOT / "Rider_Orc" / "Idle.png",
        "animations": {
            "Idle": _ORCSIDE_CHARACTER_ROOT / "Rider_Orc" / "Idle.png",
            "Attack": _ORCSIDE_CHARACTER_ROOT / "Rider_Orc" / "Attack.png",
            "Death": _ORCSIDE_CHARACTER_ROOT / "Rider_Orc" / "Death.png",
            "Hurt": _ORCSIDE_CHARACTER_ROOT / "Rider_Orc" / "Hurt.png",
            "Walk": _ORCSIDE_CHARACTER_ROOT / "Rider_Orc" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 72,
        "initial_facing": "right",
    },
    "Slime Orc": {
        "path": _ORCSIDE_CHARACTER_ROOT / "Slime_Orc" / "Idle.png",
        "animations": {
            "Idle": _ORCSIDE_CHARACTER_ROOT / "Slime_Orc" / "Idle.png",
            "Attack": _ORCSIDE_CHARACTER_ROOT / "Slime_Orc" / "Attack.png",
            "Death": _ORCSIDE_CHARACTER_ROOT / "Slime_Orc" / "Death.png",
            "Hurt": _ORCSIDE_CHARACTER_ROOT / "Slime_Orc" / "Hurt.png",
            "Walk": _ORCSIDE_CHARACTER_ROOT / "Slime_Orc" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 45,
        "initial_facing": "right",
    },
    "Soldier1Orc": {
        "path": _ORCSIDE_CHARACTER_ROOT / "Soldier1_Orc" / "Idle.png",
        "animations": {
            "Idle": _ORCSIDE_CHARACTER_ROOT / "Soldier1_Orc" / "Idle.png",
            "Attack": _ORCSIDE_CHARACTER_ROOT / "Soldier1_Orc" / "Attack.png",
            "AttackBuff": _ORCSIDE_CHARACTER_ROOT / "Soldier1_Orc" / "Attack02.png",
            "Death": _ORCSIDE_CHARACTER_ROOT / "Soldier1_Orc" / "Death.png",
            "Hurt": _ORCSIDE_CHARACTER_ROOT / "Soldier1_Orc" / "Hurt.png",
            "Walk": _ORCSIDE_CHARACTER_ROOT / "Soldier1_Orc" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 58,
        "initial_facing": "right",
    },
    "Soldier2Skeleton": {
        "path": _ORCSIDE_CHARACTER_ROOT / "Soldier2_Skeleton" / "Idle.png",
        "animations": {
            "Idle": _ORCSIDE_CHARACTER_ROOT / "Soldier2_Skeleton" / "Idle.png",
            "Attack": _ORCSIDE_CHARACTER_ROOT / "Soldier2_Skeleton" / "Attack.png",
            "AttackBuff": _ORCSIDE_CHARACTER_ROOT / "Soldier2_Skeleton" / "Attack02.png",
            "Death": _ORCSIDE_CHARACTER_ROOT / "Soldier2_Skeleton" / "Death.png",
            "Hurt": _ORCSIDE_CHARACTER_ROOT / "Soldier2_Skeleton" / "Hurt.png",
            "Walk": _ORCSIDE_CHARACTER_ROOT / "Soldier2_Skeleton" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 68,
        "initial_facing": "right",
    },
    "Soldier3Skeleton": {
        "path": _ORCSIDE_CHARACTER_ROOT / "Soldier3_Skeleton" / "Idle.png",
        "animations": {
            "Idle": _ORCSIDE_CHARACTER_ROOT / "Soldier3_Skeleton" / "Idle.png",
            "Attack": _ORCSIDE_CHARACTER_ROOT / "Soldier3_Skeleton" / "Attack.png",
            "AttackBuff": _ORCSIDE_CHARACTER_ROOT / "Soldier3_Skeleton" / "Attack02.png",
            "Death": _ORCSIDE_CHARACTER_ROOT / "Soldier3_Skeleton" / "Death.png",
            "Hurt": _ORCSIDE_CHARACTER_ROOT / "Soldier3_Skeleton" / "Hurt.png",
            "Walk": _ORCSIDE_CHARACTER_ROOT / "Soldier3_Skeleton" / "Walk.png",
        },
        "frame_w": 100,
        "frame_h": 100,
        "frame_ms": 140,
        "target_h": 54,
        "initial_facing": "right",
    },
}


def _get_fonts() -> tuple[pygame.font.Font, pygame.font.Font]:
    global _FONT_PIECE, _FONT_HP
    if _FONT_PIECE is None:
        sz = max(12, min(24, int(17 * dcfg.UI_SCALE)))
        _FONT_PIECE = pygame.font.Font(None, sz)
        _FONT_PIECE.set_bold(True)
    if _FONT_HP is None:
        sz = max(8, min(16, int(10 * dcfg.UI_SCALE)))
        _FONT_HP = pygame.font.Font(None, sz)
    return _FONT_PIECE, _FONT_HP


def invalidate_layout_caches() -> None:
    """Clear font/sprite caches after window resize so sizes match UI_SCALE."""
    global _FONT_PIECE, _FONT_HP, _SPRITE_FRAMES, _ATTACK_HIT_EFFECT_FRAMES
    _FONT_PIECE = None
    _FONT_HP = None
    _SPRITE_FRAMES = {}
    _ATTACK_HIT_EFFECT_FRAMES = None


def _load_sprite_frames(piece_id: str, animation: str = "Idle") -> list[pygame.Surface]:
    config = _SPRITE_CONFIG[piece_id]
    path = config.get("animations", {}).get(animation, config["path"])
    sheet = pygame.image.load(str(path)).convert_alpha()
    frame_w = int(config["frame_w"])
    frame_h = int(config["frame_h"])
    target_h = max(20, int(int(config["target_h"]) * dcfg.UI_SCALE))
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


def _get_sprite_frames(piece_id: str, animation: str = "Idle") -> list[pygame.Surface]:
    key = (piece_id, animation)
    if key not in _SPRITE_FRAMES:
        _SPRITE_FRAMES[key] = _load_sprite_frames(piece_id, animation)
    return _SPRITE_FRAMES[key]


def _animation_duration_ms(piece_id: str, animation: str) -> int:
    frames = _get_sprite_frames(piece_id, animation)
    frame_ms = int(_SPRITE_CONFIG[piece_id]["frame_ms"])
    return max(frame_ms, len(frames) * frame_ms)


def _default_facing_toward_enemy(faction: Faction) -> str:
    """
    Screen convention for raw sprites (drawn facing +x on the asset):
    - "right" = no horizontal flip
    - "left"  = flip horizontally

    Board: OrcSide low x, HumanSide high x → each side faces toward +x or -x
    to look at the opponent, not the map edge.
    """
    return "left" if faction is Faction.HumanSide else "right"


def _update_sprite_facing(piece_id: str, faction: Faction) -> str:
    """
    Idle/default facing is faction-based only.

    Do not infer facing from per-frame board_x changes: vision sync can jitter
    grid x and would flip Human pieces to face the wrong way (same as Orc).
    Walk/attack facing updates come from history processing and trigger_attack_animation.
    """
    if piece_id not in _SPRITE_FACING:
        _SPRITE_FACING[piece_id] = _default_facing_toward_enemy(faction)
    return _SPRITE_FACING[piece_id]


def trigger_attack_animation(
    piece_id: str,
    target_pos: tuple[int, int],
    state: GameState,
) -> None:
    piece = state.pieces.get(piece_id)
    if piece is None or piece_id not in _SPRITE_CONFIG:
        return

    if target_pos[0] < piece.pos[0]:
        _SPRITE_FACING[piece_id] = "left"
    elif target_pos[0] > piece.pos[0]:
        _SPRITE_FACING[piece_id] = "right"
    _start_sprite_animation(piece_id, "Attack")


def _start_sprite_animation(
    piece_id: str,
    animation: str,
    *,
    duration_ms: int | None = None,
    from_pos: tuple[int, int] | None = None,
    to_pos: tuple[int, int] | None = None,
    hold_last: bool = False,
) -> None:
    if piece_id not in _SPRITE_CONFIG:
        return

    if animation not in _SPRITE_CONFIG[piece_id].get("animations", {"Idle": None}):
        return

    if animation != "Death":
        _SPRITE_HIDDEN_AFTER_DEATH.discard(piece_id)

    _SPRITE_ANIMATIONS[piece_id] = {
        "name": animation,
        "started_at": pygame.time.get_ticks(),
        "duration_ms": duration_ms or _animation_duration_ms(piece_id, animation),
        "from_pos": from_pos,
        "to_pos": to_pos,
        "hold_last": hold_last,
    }


def _process_sprite_history(state: GameState) -> None:
    global _HISTORY_CURSOR

    if _HISTORY_CURSOR > len(state.history):
        _HISTORY_CURSOR = 0

    for entry in state.history[_HISTORY_CURSOR:]:
        event_type = entry.get("type")

        if event_type == "move" and entry.get("piece_id") in _SPRITE_CONFIG:
            piece_id = str(entry["piece_id"])
            from_pos = entry.get("from")
            to_pos = entry.get("to")
            if from_pos is not None and to_pos is not None:
                if to_pos[0] < from_pos[0]:
                    _SPRITE_FACING[piece_id] = "left"
                elif to_pos[0] > from_pos[0]:
                    _SPRITE_FACING[piece_id] = "right"
                _SPRITE_LAST_X[piece_id] = to_pos[0]
                _start_sprite_animation(
                    piece_id,
                    "Walk",
                    duration_ms=1500,
                    from_pos=from_pos,
                    to_pos=to_pos,
                )

        elif event_type == "attack":
            attacker_id = entry.get("attacker_id")
            if attacker_id in _SPRITE_CONFIG:
                attacker = state.pieces.get(str(attacker_id))
                target_pos = entry.get("target_pos")
                if attacker is not None and target_pos is not None:
                    if target_pos[0] < attacker.pos[0]:
                        _SPRITE_FACING[str(attacker_id)] = "left"
                    elif target_pos[0] > attacker.pos[0]:
                        _SPRITE_FACING[str(attacker_id)] = "right"
                attack_anim = (
                    "AttackBuff"
                    if bool(entry.get("attacker_has_attack_buff", False))
                    else "Attack"
                )
                _start_sprite_animation(str(attacker_id), attack_anim)

            target_id = entry.get("target_id")
            if target_id in _SPRITE_CONFIG:
                if int(entry.get("target_hp_after", 1)) <= 0:
                    _start_sprite_animation(str(target_id), "Death", hold_last=True)
                else:
                    _start_sprite_animation(str(target_id), "Hurt")

        elif event_type == "death" and entry.get("piece_id") in _SPRITE_CONFIG:
            _start_sprite_animation(str(entry["piece_id"]), "Death", hold_last=True)

    _HISTORY_CURSOR = len(state.history)


def _active_sprite_animation(
    piece_id: str,
    *,
    faction: Faction | None = None,
) -> dict | None:
    animation = _SPRITE_ANIMATIONS.get(piece_id)
    if animation is None:
        return None

    elapsed = pygame.time.get_ticks() - int(animation["started_at"])
    duration_ms = int(animation["duration_ms"])
    if animation["name"] == "Death" and animation["hold_last"]:
        if elapsed >= duration_ms + _DEATH_BLINK_DURATION_MS:
            _SPRITE_HIDDEN_AFTER_DEATH.add(piece_id)
            del _SPRITE_ANIMATIONS[piece_id]
            return None
        return animation

    if elapsed >= duration_ms and not animation["hold_last"]:
        if animation["name"] == "Walk" and faction is not None:
            _SPRITE_FACING[piece_id] = _default_facing_toward_enemy(faction)
        del _SPRITE_ANIMATIONS[piece_id]
        return None
    return animation


def has_death_animation_finished(piece_id: str) -> bool:
    """
    Return True once the full death sequence is finished.

    For hold_last Death animations, this includes the blink segment.
    """
    animation = _SPRITE_ANIMATIONS.get(piece_id)
    if animation is None:
        return piece_id in _SPRITE_HIDDEN_AFTER_DEATH
    if str(animation.get("name")) != "Death":
        return False
    elapsed = pygame.time.get_ticks() - int(animation.get("started_at", 0))
    duration_ms = int(animation.get("duration_ms", 0))
    if bool(animation.get("hold_last", False)):
        return duration_ms > 0 and elapsed >= (duration_ms + _DEATH_BLINK_DURATION_MS)
    return duration_ms > 0 and elapsed >= duration_ms


def is_death_animation_active(piece_id: str) -> bool:
    """Return True while a Death animation is actively playing."""
    animation = _SPRITE_ANIMATIONS.get(piece_id)
    if animation is None:
        return False
    return str(animation.get("name")) == "Death"


def _should_skip_death_frame(animation: dict | None) -> bool:
    if animation is None or animation["name"] != "Death" or not animation["hold_last"]:
        return False

    elapsed = pygame.time.get_ticks() - int(animation["started_at"])
    duration_ms = int(animation["duration_ms"])
    if elapsed < duration_ms:
        return False

    blink_elapsed = elapsed - duration_ms
    phase_count = _DEATH_BLINK_COUNT * 2
    phase_ms = max(1, _DEATH_BLINK_DURATION_MS // phase_count)
    return (blink_elapsed // phase_ms) % 2 == 1


def _update_sprite_hp_animations(state: GameState) -> None:
    for piece_id in _SPRITE_CONFIG:
        piece = state.pieces.get(piece_id)
        if piece is None:
            continue

        previous_hp = _SPRITE_LAST_HP.get(piece.id)
        if previous_hp is not None and piece.hp < previous_hp:
            active_animation = _SPRITE_ANIMATIONS.get(piece.id)
            # Keep move readability: if trap damage happens on arrival, let the
            # walk animation finish before switching to hurt/death.
            if active_animation is not None and str(active_animation.get("name")) == "Walk":
                continue
            if piece.hp <= 0 or piece.is_dead:
                _start_sprite_animation(piece.id, "Death", hold_last=True)
            else:
                _start_sprite_animation(piece.id, "Hurt")

        _SPRITE_LAST_HP[piece.id] = piece.hp


def _sprite_render_position(
    piece_pos: tuple[int, int],
    animation: dict | None,
) -> tuple[int, int]:
    if animation is None or animation["name"] != "Walk":
        return node_to_pixel(*piece_pos)

    from_pos = animation.get("from_pos")
    to_pos = animation.get("to_pos")
    if from_pos is None or to_pos is None:
        return node_to_pixel(*piece_pos)

    elapsed = pygame.time.get_ticks() - int(animation["started_at"])
    duration_ms = max(1, int(animation["duration_ms"]))
    t = min(1.0, max(0.0, elapsed / duration_ms))
    from_px, from_py = node_to_pixel(*from_pos)
    to_px, to_py = node_to_pixel(*to_pos)
    return (
        int(from_px + (to_px - from_px) * t),
        int(from_py + (to_py - from_py) * t),
    )


def _sprite_frame(piece_id: str, animation: dict | None) -> pygame.Surface:
    animation_name = "Idle" if animation is None else str(animation["name"])
    frames = _get_sprite_frames(piece_id, animation_name)
    if not frames:
        frames = _get_sprite_frames(piece_id, "Idle")

    frame_ms = int(_SPRITE_CONFIG[piece_id]["frame_ms"])
    if animation is None:
        frame_idx = (pygame.time.get_ticks() // frame_ms) % len(frames)
    else:
        elapsed = pygame.time.get_ticks() - int(animation["started_at"])
        if animation["name"] == "Walk":
            frame_idx = (elapsed // frame_ms) % len(frames)
        else:
            frame_idx = min(len(frames) - 1, elapsed // frame_ms)

    return frames[int(frame_idx)]


def draw_piece_sprite_at(
    screen: pygame.Surface,
    piece_id: str,
    faction: Faction,
    px: int,
    py: int,
    *,
    alpha: int = 255,
    tint: tuple[int, int, int] | None = None,
) -> bool:
    """Render a piece sprite (Idle frame) at *(px, py)* with optional alpha/tint.

    Used by external overlays such as the illegal-move retract animation.
    Returns True when a sprite was drawn, False if the piece has no sprite
    config (caller may then draw a fallback shape).
    """
    if piece_id not in _SPRITE_CONFIG:
        return False
    if not _get_sprite_frames(piece_id, "Idle"):
        return False

    frame = _sprite_frame(piece_id, None)
    if _update_sprite_facing(piece_id, faction) == "left":
        frame = pygame.transform.flip(frame, True, False)

    if tint is not None or alpha < 255:
        overlay = frame.copy()
        if tint is not None:
            tint_surf = pygame.Surface(overlay.get_size(), pygame.SRCALPHA)
            tint_surf.fill((*tint, 110))
            overlay.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        if alpha < 255:
            overlay.set_alpha(int(max(0, min(255, alpha))))
        frame = overlay

    sprite_x = px - frame.get_width() // 2
    sprite_y = py + PIECE_RADIUS - frame.get_height()
    screen.blit(frame, (sprite_x, sprite_y))
    return True


def _draw_piece_sprite(
    screen: pygame.Surface,
    piece_id: str,
    faction: Faction,
    px: int,
    py: int,
    animation: dict | None = None,
) -> bool:
    if piece_id not in _SPRITE_CONFIG:
        return False

    if not _get_sprite_frames(piece_id, "Idle"):
        return False

    frame = _sprite_frame(piece_id, animation)
    if _update_sprite_facing(piece_id, faction) == "left":
        frame = pygame.transform.flip(frame, True, False)

    shadow_rect = pygame.Rect(0, 0, PIECE_RADIUS + 16, 10)
    shadow_rect.center = (px, py + PIECE_RADIUS - 5)
    pygame.draw.ellipse(screen, (25, 20, 15), shadow_rect)

    sprite_x = px - frame.get_width() // 2
    sprite_y = py + PIECE_RADIUS - frame.get_height()
    screen.blit(frame, (sprite_x, sprite_y))
    return True


def _draw_piece_buffs(
    screen: pygame.Surface,
    piece,
    px: int,
    py: int,
    *,
    attack_bonus: int,
    defence_bonus: int,
) -> None:
    if attack_bonus <= 0 and defence_bonus <= 0:
        return

    ticks = pygame.time.get_ticks()
    if defence_bonus > 0:
        _draw_aura(
            screen,
            px,
            py - 4,
            body_rgb=(255, 235, 120),
            particle_rgb=(255, 245, 165),
            ticks=ticks,
            seed=hash((piece.id, "def")),
        )
    if attack_bonus > 0:
        _draw_aura(
            screen,
            px,
            py - 2,
            body_rgb=(255, 105, 105),
            particle_rgb=(245, 85, 85),
            ticks=ticks,
            seed=hash((piece.id, "atk")),
        )


def _draw_aura(
    screen: pygame.Surface,
    px: int,
    py: int,
    *,
    body_rgb: tuple[int, int, int],
    particle_rgb: tuple[int, int, int],
    ticks: int,
    seed: int,
) -> None:
    pulse = (pygame.time.get_ticks() % 1000) / 1000.0
    pulse_alpha = int(90 + 75 * (1.0 - abs(0.5 - pulse) * 2.0))
    aura_r = PIECE_RADIUS + 18
    aura = pygame.Surface((aura_r * 2, aura_r * 2), pygame.SRCALPHA)
    for r in range(aura_r, 0, -1):
        t = r / max(1, aura_r)
        layer_alpha = int(pulse_alpha * (1.0 - t) ** 1.15)
        if layer_alpha > 0:
            pygame.draw.circle(aura, (*body_rgb, layer_alpha), (aura_r, aura_r), r)
    screen.blit(aura, (px - aura_r, py - aura_r))

    particle_span = PIECE_RADIUS + 20
    for idx in range(13):
        phase = (ticks * 0.12 + ((seed + idx * 37) % 1000)) % 1000
        y_off = int((phase / 1000.0) * particle_span)
        x_off = ((seed // (idx + 3)) % 31) - 15
        line_h = 5 + ((seed + idx) % 5)
        x = px + x_off
        y2 = py + PIECE_RADIUS - 3 - y_off
        y1 = y2 - line_h
        pygame.draw.line(
            screen,
            particle_rgb,
            (x, y1),
            (x, y2),
            2,
        )


def _process_attack_hit_effect_history(state: GameState) -> None:
    global _BUFF_FX_HISTORY_CURSOR
    if _BUFF_FX_HISTORY_CURSOR > len(state.history):
        _BUFF_FX_HISTORY_CURSOR = 0

    for entry in state.history[_BUFF_FX_HISTORY_CURSOR:]:
        if entry.get("type") != "attack":
            continue
        if not entry.get("attacker_has_attack_buff", False):
            continue
        pos = entry.get("target_pos")
        if pos is None:
            continue
        _ATTACK_HIT_EFFECTS.append(
            {
                "pos": tuple(pos),
                "started_at": pygame.time.get_ticks(),
            }
        )
    _BUFF_FX_HISTORY_CURSOR = len(state.history)


def _get_attack_hit_effect_frames() -> list[pygame.Surface]:
    global _ATTACK_HIT_EFFECT_FRAMES
    if _ATTACK_HIT_EFFECT_FRAMES is None:
        sheet = pygame.image.load(str(_ATTACK_HIT_EFFECT_PATH)).convert_alpha()
        frames: list[pygame.Surface] = []
        frame_w = 100
        frame_h = 100
        target_h = max(24, int(_ATTACK_HIT_EFFECT_TARGET_H * dcfg.UI_SCALE))
        for x in range(0, sheet.get_width(), frame_w):
            frame = sheet.subsurface(pygame.Rect(x, 0, frame_w, frame_h)).copy()
            bounds = frame.get_bounding_rect(min_alpha=1)
            if bounds.width == 0 or bounds.height == 0:
                continue
            cropped = frame.subsurface(bounds).copy()
            target_w = max(
                1,
                int(cropped.get_width() * target_h / cropped.get_height()),
            )
            frames.append(
                pygame.transform.scale(cropped, (target_w, target_h))
            )
        _ATTACK_HIT_EFFECT_FRAMES = frames
    return _ATTACK_HIT_EFFECT_FRAMES


def draw_attack_hit_effects(screen: pygame.Surface, state: GameState) -> None:
    _process_attack_hit_effect_history(state)
    frames = _get_attack_hit_effect_frames()
    if not frames:
        return

    now = pygame.time.get_ticks()
    duration_ms = len(frames) * _ATTACK_HIT_EFFECT_FRAME_MS
    active_effects: list[dict] = []
    for effect in _ATTACK_HIT_EFFECTS:
        elapsed = now - int(effect["started_at"])
        if elapsed >= duration_ms:
            continue
        frame_idx = min(len(frames) - 1, max(0, elapsed // _ATTACK_HIT_EFFECT_FRAME_MS))
        frame = frames[int(frame_idx)]
        px, py = node_to_pixel(*effect["pos"])
        screen.blit(frame, (px - frame.get_width() // 2, py - frame.get_height() // 2))
        active_effects.append(effect)
    _ATTACK_HIT_EFFECTS[:] = active_effects


def draw_pieces(
    screen: pygame.Surface,
    state: GameState,
    *,
    visible_piece_ids: set[str] | None = None,
) -> None:
    """
    Draw pieces.

    When *visible_piece_ids* is provided, only draw non-dead pieces whose IDs
    are present in that set. This is used by the camera/vision integration so
    that untracked pieces simply disappear without being treated as dead.
    """
    _process_sprite_history(state)
    _update_sprite_hp_animations(state)
    font_piece, font_hp = _get_fonts()

    for piece in state.pieces.values():
        if visible_piece_ids is not None and not piece.is_dead and piece.id not in visible_piece_ids:
            continue
        if piece.id in _SPRITE_HIDDEN_AFTER_DEATH:
            continue
        if piece.is_dead and piece.id not in _SPRITE_CONFIG:
            continue

        animation = _active_sprite_animation(piece.id, faction=piece.faction)
        if (
            piece.is_dead
            and piece.id in _SPRITE_CONFIG
            and animation is None
            and piece.id not in _SPRITE_HIDDEN_AFTER_DEATH
        ):
            _start_sprite_animation(piece.id, "Death", hold_last=True)
            animation = _active_sprite_animation(piece.id, faction=piece.faction)

        px, py = _sprite_render_position(piece.pos, animation)
        fill = C_HUMANSIDE_FILL if piece.faction == Faction.HumanSide else C_ORCSIDE_FILL

        if _should_skip_death_frame(animation):
            continue

        if _draw_piece_sprite(screen, piece.id, piece.faction, px, py, animation):
            attack_bonus = get_attack_effect_bonus(piece, state)
            defence_bonus = get_defence_bonus(piece)
            _draw_piece_buffs(
                screen,
                piece,
                px,
                py,
                attack_bonus=attack_bonus,
                defence_bonus=defence_bonus,
            )
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
            continue

        # Shadow
        pygame.draw.circle(screen, (30, 20, 10), (px + 2, py + 2), PIECE_RADIUS)
        # Fill
        pygame.draw.circle(screen, fill, (px, py), PIECE_RADIUS)
        # Border
        pygame.draw.circle(screen, C_PIECE_BORDER, (px, py), PIECE_RADIUS, 2)

        # Role label
        label = PIECE_LABELS.get(piece.id, "?")
        txt_surf = font_piece.render(label, True, C_PIECE_TEXT)
        screen.blit(txt_surf, (px - txt_surf.get_width() // 2,
                               py - txt_surf.get_height() // 2))

        # HP bar
        bar_x = px - HP_BAR_W // 2
        bar_y = py + HP_BAR_OFFSET_Y
        pygame.draw.rect(screen, C_HP_EMPTY,
                         pygame.Rect(bar_x, bar_y, HP_BAR_W, HP_BAR_H))
        ratio = max(0.0, piece.hp / piece.max_hp)
        filled_w = int(HP_BAR_W * ratio)
        if filled_w > 0:
            pygame.draw.rect(screen, C_HP_FULL,
                             pygame.Rect(bar_x, bar_y, filled_w, HP_BAR_H))

        # HP number
        hp_txt = font_hp.render(f"{piece.hp}", True, (220, 220, 220))
        screen.blit(hp_txt, (px - hp_txt.get_width() // 2,
                             bar_y + HP_BAR_H + 1))
