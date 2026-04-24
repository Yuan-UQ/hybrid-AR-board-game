"""
Side-panel and HUD rendering.

Draws:
  - Player banner (whose turn, round, phase)
  - Phase instruction text
  - HP summary for both factions
  - Active event point summary
  - Last action / event message
  - Skip / End-Turn button
"""

from __future__ import annotations

import pygame

from xiangqi_arena.core.enums import Faction, Phase, PieceType, VictoryState
from xiangqi_arena.rules.damage_rules import pawn_has_ally_bonus
from xiangqi_arena.state.game_state import GameState
from xiangqi_arena.ui.display_config import (
    C_AMMO, C_BLACK_LABEL, C_BTN_BG, C_BTN_HOVER, C_BTN_TEXT,
    C_HP_EMPTY, C_HP_FULL, C_MED, C_MSG_TEXT, C_MUTED, C_PANEL_BG,
    C_PANEL_BORDER, C_PANEL_TEXT, C_RED_LABEL, C_TRAP,
    C_VICTORY_BLK, C_VICTORY_DRAW, C_VICTORY_RED,
    PANEL_PAD, PANEL_W, PANEL_X, WINDOW_H, WINDOW_W,
)
from xiangqi_arena.core.enums import EventPointType

# Button rect (computed once)
BTN_W  = PANEL_W - PANEL_PAD * 2
BTN_H  = 36
BTN_X  = PANEL_X + PANEL_PAD
BTN_Y  = WINDOW_H - BTN_H - PANEL_PAD - 12

BUTTON_RECT = pygame.Rect(BTN_X, BTN_Y, BTN_W, BTN_H)

_PHASE_INSTRUCTIONS: dict[Phase, str] = {
    Phase.START:       "",   # auto-processed, no instruction needed
    Phase.MOVEMENT:    "Click a piece → click green node  |  Enter=skip  |  S=Surrender  D=Draw",
    Phase.RECOGNITION: "",   # auto-processed
    Phase.ATTACK:      "Click a red target to attack  |  Enter=skip  |  S=Surrender  D=Draw",
    Phase.RESOLVE:     "",   # auto-processed
}

_PHASE_NAMES: dict[Phase, str] = {
    Phase.START:       "START",
    Phase.MOVEMENT:    "MOVEMENT",
    Phase.RECOGNITION: "RECOGNITION",
    Phase.ATTACK:      "ATTACK",
    Phase.RESOLVE:     "RESOLVE",
}

_FONT_TITLE:   pygame.font.Font | None = None
_FONT_BODY:    pygame.font.Font | None = None
_FONT_SMALL:   pygame.font.Font | None = None
_FONT_BTN:     pygame.font.Font | None = None


def _fonts() -> tuple:
    global _FONT_TITLE, _FONT_BODY, _FONT_SMALL, _FONT_BTN
    if _FONT_TITLE is None:
        _FONT_TITLE = pygame.font.SysFont("Arial", 17, bold=True)
        _FONT_BODY  = pygame.font.SysFont("Arial", 14)
        _FONT_SMALL = pygame.font.SysFont("monospace", 12)
        _FONT_BTN   = pygame.font.SysFont("Arial", 14, bold=True)
    return _FONT_TITLE, _FONT_BODY, _FONT_SMALL, _FONT_BTN


def draw_panel(
    screen: pygame.Surface,
    state: GameState,
    log: list[str] | None = None,
    btn_label: str = "Skip / End Turn",
    btn_hover: bool = False,
) -> None:
    """
    Render the full right-side info panel.

    Parameters
    ----------
    log:
        Message history, newest entry at index 0. Displayed top-to-bottom
        so the latest action is always visible at the top of the log section.
    """
    ft, fb, fs, fbtn = _fonts()

    # Panel background
    panel_rect = pygame.Rect(PANEL_X - 6, 0, WINDOW_W - PANEL_X + 6, WINDOW_H)
    pygame.draw.rect(screen, C_PANEL_BG, panel_rect)
    pygame.draw.line(screen, C_PANEL_BORDER,
                     (PANEL_X - 6, 0), (PANEL_X - 6, WINDOW_H), 2)

    y = PANEL_PAD + 8

    # --- Active player banner ---
    active = state.active_faction
    faction_colour = C_RED_LABEL if active == Faction.RED else C_BLACK_LABEL
    faction_name   = "RED" if active == Faction.RED else "BLACK"
    banner = ft.render(f"{faction_name}'s Turn", True, faction_colour)
    screen.blit(banner, (PANEL_X + PANEL_PAD, y))
    y += banner.get_height() + 4

    # Round
    round_txt = fb.render(f"Round {state.round_number}", True, C_PANEL_TEXT)
    screen.blit(round_txt, (PANEL_X + PANEL_PAD, y))
    y += round_txt.get_height() + 2

    # Phase
    phase_name = _PHASE_NAMES.get(state.current_phase, str(state.current_phase))
    phase_surf = ft.render(f"Phase: {phase_name}", True, C_PANEL_TEXT)
    screen.blit(phase_surf, (PANEL_X + PANEL_PAD, y))
    y += phase_surf.get_height() + 8

    # Divider
    pygame.draw.line(screen, C_PANEL_BORDER,
                     (PANEL_X + 4, y), (WINDOW_W - 4, y), 1)
    y += 6

    # --- Instructions ---
    instr = _PHASE_INSTRUCTIONS.get(state.current_phase, "")
    for line in _wrap(instr, fb, PANEL_W - PANEL_PAD * 2):
        s = fb.render(line, True, C_MSG_TEXT)
        screen.blit(s, (PANEL_X + PANEL_PAD, y))
        y += s.get_height() + 2
    y += 6

    # --- HP summary ---
    pygame.draw.line(screen, C_PANEL_BORDER,
                     (PANEL_X + 4, y), (WINDOW_W - 4, y), 1)
    y += 6
    hdr = fs.render("  #  name       HP        ATK", True, C_MUTED)
    screen.blit(hdr, (PANEL_X + PANEL_PAD, y))
    y += hdr.get_height() + 4

    for faction in (Faction.RED, Faction.BLACK):
        fc = C_RED_LABEL if faction == Faction.RED else C_BLACK_LABEL
        fn = "Red" if faction == Faction.RED else "Black"
        draw_tag = "  [Draw?]" if state.players[faction].draw_requested else ""
        flbl = fs.render(f"▶ {fn}{draw_tag}", True, fc)
        screen.blit(flbl, (PANEL_X + PANEL_PAD, y))
        y += flbl.get_height() + 2

        pieces = [p for p in state.pieces.values() if p.faction == faction]
        for p in pieces:
            if p.is_dead:
                c       = C_MUTED
                hp_str  = "dead"
                atk_str = "--"
            else:
                c      = C_PANEL_TEXT
                hp_str = f"{p.hp}/{p.max_hp}"
                # Show grouping bonus indicator for Pawns with an active ally nearby
                if (p.piece_type is PieceType.PAWN
                        and pawn_has_ally_bonus(p, state)):
                    atk_str = f"{p.atk}(+1)"
                else:
                    atk_str = str(p.atk)

            from xiangqi_arena.ui.display_config import PIECE_LABELS
            lbl_char  = PIECE_LABELS.get(p.piece_type.value, "?")
            short_id  = p.id.split("_", 1)[-1][:7]
            line_str  = f"  {lbl_char} {short_id:<8} HP{hp_str:<6} A{atk_str}"
            s = fs.render(line_str, True, c)
            screen.blit(s, (PANEL_X + PANEL_PAD, y))
            y += s.get_height() + 1

        y += 4

    # --- Event points info (up to 2) ---
    active_eps = [ep for ep in state.event_points
                  if ep.is_valid and not ep.is_triggered]
    if active_eps:
        pygame.draw.line(screen, C_PANEL_BORDER,
                         (PANEL_X + 4, y), (WINDOW_W - 4, y), 1)
        y += 6
        _EC = {
            EventPointType.AMMUNITION: C_AMMO,
            EventPointType.MEDICAL:    C_MED,
            EventPointType.TRAP:       C_TRAP,
        }
        for ep in active_eps:
            ec  = _EC.get(ep.event_type, C_PANEL_TEXT)
            lbl = {"ammunition": "◆+2ATK", "medical": "✚+1HP", "trap": "✕-1HP"}.get(
                ep.event_type.value, ep.event_type.value
            )
            ep_txt = fb.render(f"  {lbl}  @ {ep.pos}", True, ec)
            screen.blit(ep_txt, (PANEL_X + PANEL_PAD, y))
            y += ep_txt.get_height() + 2
        y += 4

    # --- Action / event log (newest at top) ---
    log_entries = log if log else []
    if log_entries:
        pygame.draw.line(screen, C_PANEL_BORDER,
                         (PANEL_X + 4, y), (WINDOW_W - 4, y), 1)
        y += 6
        lbl_hdr = fs.render("─ log (latest first) ─", True, C_MUTED)
        screen.blit(lbl_hdr, (PANEL_X + PANEL_PAD, y))
        y += lbl_hdr.get_height() + 3

        for entry in log_entries:
            # Distinguish event lines from action lines by prefix
            ec = C_AMMO if ("✦" in entry or "triggered" in entry or
                            "Spawned" in entry) else C_MSG_TEXT
            for line in _wrap(entry, fs, PANEL_W - PANEL_PAD * 2):
                s = fs.render(line, True, ec)
                screen.blit(s, (PANEL_X + PANEL_PAD, y))
                y += s.get_height() + 2
            if y > BTN_Y - 14:   # don't overflow into the button
                break

    # --- Skip / End-Turn button ---
    btn_colour = C_BTN_HOVER if btn_hover else C_BTN_BG
    pygame.draw.rect(screen, btn_colour, BUTTON_RECT, border_radius=6)
    pygame.draw.rect(screen, C_PANEL_BORDER, BUTTON_RECT, 1, border_radius=6)
    btn_surf = fbtn.render(btn_label, True, C_BTN_TEXT)
    screen.blit(btn_surf, (
        BUTTON_RECT.centerx - btn_surf.get_width() // 2,
        BUTTON_RECT.centery - btn_surf.get_height() // 2,
    ))


def draw_victory_overlay(screen: pygame.Surface, state: GameState) -> None:
    """
    Modal victory dialog.

    Layout (centered on screen):
      ┌──────────────────────────────┐
      │   ★  RED WINS!  ★            │
      │                              │
      │   General has fallen.        │
      │                              │
      │   Press Escape to quit       │
      └──────────────────────────────┘
    """
    vs = state.victory_state

    # Choose copy and colour by outcome
    if vs == VictoryState.RED_WIN:
        title     = "RED  WINS!"
        black_surrendered = state.players[Faction.BLACK].has_surrendered
        subtitle  = "Black has surrendered." if black_surrendered else "The Black General has fallen."
        box_fill  = (90, 20, 20)
        box_border= C_VICTORY_RED
        title_c   = C_VICTORY_RED
    elif vs == VictoryState.BLACK_WIN:
        title     = "BLACK  WINS!"
        red_surrendered = state.players[Faction.RED].has_surrendered
        subtitle  = "Red has surrendered." if red_surrendered else "The Red General has fallen."
        box_fill  = (20, 20, 70)
        box_border= C_VICTORY_BLK
        title_c   = C_VICTORY_BLK
    else:
        title     = "DRAW"
        subtitle  = "Both sides have agreed to a draw."
        box_fill  = (50, 50, 20)
        box_border= C_VICTORY_DRAW
        title_c   = C_VICTORY_DRAW

    # ── Dim the whole screen ──────────────────────────────────────────────
    dim = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 180))
    screen.blit(dim, (0, 0))

    # ── Dialog box ────────────────────────────────────────────────────────
    BOX_W, BOX_H = 480, 260
    bx = WINDOW_W // 2 - BOX_W // 2
    by = WINDOW_H // 2 - BOX_H // 2

    # Shadow
    shadow = pygame.Rect(bx + 6, by + 6, BOX_W, BOX_H)
    pygame.draw.rect(screen, (0, 0, 0), shadow, border_radius=14)

    # Box background
    box_rect = pygame.Rect(bx, by, BOX_W, BOX_H)
    pygame.draw.rect(screen, box_fill, box_rect, border_radius=14)
    pygame.draw.rect(screen, box_border, box_rect, 3, border_radius=14)

    # ── Title ─────────────────────────────────────────────────────────────
    font_title = pygame.font.SysFont("Arial", 52, bold=True)
    font_sub   = pygame.font.SysFont("Arial", 19)
    font_hint  = pygame.font.SysFont("Arial", 14)

    stars = "★  " + title + "  ★"
    t_surf = font_title.render(stars, True, title_c)
    screen.blit(t_surf, (
        WINDOW_W // 2 - t_surf.get_width() // 2,
        by + 42,
    ))

    # Divider line
    pygame.draw.line(screen, box_border,
                     (bx + 30, by + 110), (bx + BOX_W - 30, by + 110), 1)

    # ── Subtitle ──────────────────────────────────────────────────────────
    s_surf = font_sub.render(subtitle, True, (220, 220, 220))
    screen.blit(s_surf, (
        WINDOW_W // 2 - s_surf.get_width() // 2,
        by + 130,
    ))

    # ── Hint ──────────────────────────────────────────────────────────────
    h_surf = font_hint.render("Press  Escape  to quit", True, (160, 160, 160))
    screen.blit(h_surf, (
        WINDOW_W // 2 - h_surf.get_width() // 2,
        by + BOX_H - 36,
    ))


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _wrap(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    """Very simple word-wrap returning a list of lines."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]
