"""
Display constants shared across all ui/ modules.

All pixel geometry and colour definitions live here so that other ui modules
stay free of magic numbers.

**Responsive layout** — call `apply_layout_for_window_size(w, h)` after
`set_mode` or on `VIDEORESIZE` so all derived `BOARD_*` / panel / `NODE_SNAP`
values match the current window. Defaults are applied at import via
`apply_layout_for_window_size(1600, 920)`.
"""

# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
WINDOW_W: int = 1600
WINDOW_H: int = 920
FPS: int = 60
WINDOW_TITLE: str = "hybrid-AR-board-game-frontend"

# Scale vs design (1600×920); also used for sprite / font scaling in UI
UI_SCALE: float = 1.0

# ---------------------------------------------------------------------------
# Board geometry
# Board nodes are laid out as a 10 × 9 intersection grid.
# The board is rendered sideways:
# x = 0 (OrcSide's home column) is drawn on the LEFT.
# x = 9 (HumanSide's home column) is drawn on the RIGHT.
# ---------------------------------------------------------------------------
CELL: int = 63           # legacy fallback spacing for generated debug geometry
BOARD_LEFT: int = 42     # legacy fallback left margin
BOARD_TOP: int = 42      # legacy fallback top margin

# Unified HUD layout geometry (recomputed in apply_layout_for_window_size)
HUD_MARGIN: int = 10
SIDE_PANEL_W: int = 250
PANEL_GAP: int = 12
BOTTOM_PANEL_H: int = 190

# Background-board image placement.  The source art is perspective-drawn, so
# board nodes use calibrated ratios instead of a single CELL value.
BOARD_IMAGE_LEFT: int = 0
BOARD_IMAGE_TOP: int = 0
BOARD_IMAGE_W: int = 0
BOARD_IMAGE_H: int = 0

# The full available board area (used for drawing a backdrop to reduce letterboxing).
BOARD_AVAIL_LEFT: int = 0
BOARD_AVAIL_TOP: int = 0
BOARD_AVAIL_W: int = 0
BOARD_AVAIL_H: int = 0

# Derived
BOARD_RIGHT: int = 0
BOARD_BOTTOM: int = 0

# ---------------------------------------------------------------------------
# HUD panels
# ---------------------------------------------------------------------------
LEFT_PANEL_X: int = 0
RIGHT_PANEL_X: int = 0
SIDE_PANEL_Y: int = 0
SIDE_PANEL_H: int = 0
BOTTOM_PANEL_X: int = 0
BOTTOM_PANEL_Y: int = 0
BOTTOM_PANEL_W: int = 0

# Top bar (global HUD header)
TOP_BAR_H: int = 0

# Backward-compat aliases used by older code paths.
PANEL_X: int = 0
PANEL_W: int = 0
PANEL_PAD: int = 10

# ---------------------------------------------------------------------------
# Bottom action buttons (Skip / Draw / Surrender)
# ---------------------------------------------------------------------------
SKIP_BTN_W: int = 220
SKIP_BTN_H: int = 36
ACTION_BTN_W: int = 170
ACTION_BTN_H: int = 36
ACTION_BTN_GAP_X: int = 10
ACTION_ROW_GAP_Y: int = 10

# Highlight rings (read by highlight_renderer)
HIGHLIGHT_MOVE_R: int = 10
HIGHLIGHT_ATTACK_R: int = 12

# ---------------------------------------------------------------------------
# Piece rendering
# ---------------------------------------------------------------------------
PIECE_RADIUS: int = 24
HP_BAR_W: int     = 42
HP_BAR_H: int     = 5
HP_BAR_OFFSET_Y: int = 27   # PIECE_RADIUS + 3 after apply_layout

# Click-snap threshold (pixels)
NODE_SNAP: int = 22


def apply_layout_for_window_size(w: int, h: int) -> None:
    """
    Recompute all size-dependent module globals. Call on startup and
    on pygame.VIDEORESIZE (after set_mode to the new size).
    """
    global WINDOW_W, WINDOW_H, UI_SCALE, HUD_MARGIN, SIDE_PANEL_W, PANEL_GAP, BOTTOM_PANEL_H
    global BOARD_IMAGE_LEFT, BOARD_IMAGE_TOP, BOARD_IMAGE_W, BOARD_IMAGE_H, BOARD_RIGHT, BOARD_BOTTOM
    global BOARD_AVAIL_LEFT, BOARD_AVAIL_TOP, BOARD_AVAIL_W, BOARD_AVAIL_H
    global LEFT_PANEL_X, RIGHT_PANEL_X, SIDE_PANEL_Y, SIDE_PANEL_H, BOTTOM_PANEL_X, BOTTOM_PANEL_Y, BOTTOM_PANEL_W
    global TOP_BAR_H
    global PANEL_X, PANEL_W, PANEL_PAD
    global SKIP_BTN_W, SKIP_BTN_H, ACTION_BTN_W, ACTION_BTN_H, ACTION_BTN_GAP_X, ACTION_ROW_GAP_Y
    global PIECE_RADIUS, HP_BAR_W, HP_BAR_H, HP_BAR_OFFSET_Y, NODE_SNAP
    global HIGHLIGHT_MOVE_R, HIGHLIGHT_ATTACK_R

    w = max(1024, min(4096, int(w)))
    h = max(680, min(2304, int(h)))
    WINDOW_W, WINDOW_H = w, h
    # Balance width/height; avoid extreme stretch on ultra-wide
    UI_SCALE = max(0.55, min(1.6, min(w / 1600.0, h / 920.0)))

    HUD_MARGIN = max(6, int(8 * UI_SCALE) + 2)
    PANEL_PAD = max(6, int(10 * UI_SCALE))
    # Side rosters: ~15% of width, keep board readable on small windows
    SIDE_PANEL_W = max(176, min(300, int(w * 0.155)))
    PANEL_GAP = max(8, int(12 * UI_SCALE))
    BOTTOM_PANEL_H = max(148, min(280, int(h * 0.205)))
    TOP_BAR_H = max(44, int(56 * UI_SCALE))

    # Keep minimum board area; shrink side columns if needed
    min_board = 400
    while True:
        board_try = w - 2 * (HUD_MARGIN + SIDE_PANEL_W + PANEL_GAP)
        if board_try >= min_board or SIDE_PANEL_W <= 160:
            break
        SIDE_PANEL_W = max(160, SIDE_PANEL_W - 8)

    # Compute the central "available board area" first (full height between top
    # margin and bottom panel, and full width between side panels).
    avail_left = HUD_MARGIN + SIDE_PANEL_W + PANEL_GAP
    avail_top = HUD_MARGIN + TOP_BAR_H
    avail_w = w - 2 * (HUD_MARGIN + SIDE_PANEL_W + PANEL_GAP)
    avail_h = h - TOP_BAR_H - BOTTOM_PANEL_H - HUD_MARGIN * 3
    avail_w = max(240, avail_w)
    avail_h = max(240, avail_h)

    BOARD_AVAIL_LEFT = int(avail_left)
    BOARD_AVAIL_TOP = int(avail_top)
    BOARD_AVAIL_W = int(avail_w)
    BOARD_AVAIL_H = int(avail_h)

    # Keep the board background image aspect ratio to avoid distortion.
    # Native art size is 819×546 (see ui/board_renderer.py).
    board_aspect = 819.0 / 546.0
    if avail_w / avail_h >= board_aspect:
        # Too wide: height-limited
        BOARD_IMAGE_H = avail_h
        BOARD_IMAGE_W = int(round(avail_h * board_aspect))
    else:
        # Too tall: width-limited
        BOARD_IMAGE_W = avail_w
        BOARD_IMAGE_H = int(round(avail_w / board_aspect))

    # Center within the available board area (letterbox/pillarbox).
    BOARD_IMAGE_LEFT = int(avail_left + (avail_w - BOARD_IMAGE_W) / 2)
    BOARD_IMAGE_TOP = int(avail_top + (avail_h - BOARD_IMAGE_H) / 2)

    BOARD_RIGHT = BOARD_IMAGE_LEFT + BOARD_IMAGE_W
    BOARD_BOTTOM = BOARD_IMAGE_TOP + BOARD_IMAGE_H

    LEFT_PANEL_X = HUD_MARGIN
    RIGHT_PANEL_X = w - HUD_MARGIN - SIDE_PANEL_W
    # Match the side panels' vertical span to the board image (same top and height).
    SIDE_PANEL_Y = BOARD_IMAGE_TOP
    SIDE_PANEL_H = BOARD_IMAGE_H
    BOTTOM_PANEL_X = HUD_MARGIN
    BOTTOM_PANEL_Y = h - HUD_MARGIN - BOTTOM_PANEL_H
    BOTTOM_PANEL_W = w - HUD_MARGIN * 2
    PANEL_X = RIGHT_PANEL_X
    PANEL_W = SIDE_PANEL_W

    cw = BOARD_IMAGE_W / 10.0
    ch = BOARD_IMAGE_H / 9.0
    NODE_SNAP = max(12, int(0.34 * min(cw, ch)))

    SKIP_BTN_H = max(30, int(36 * UI_SCALE))
    SKIP_BTN_W = max(150, int(220 * UI_SCALE))
    ACTION_BTN_W = max(120, int(170 * UI_SCALE))
    ACTION_BTN_H = SKIP_BTN_H
    ACTION_BTN_GAP_X = max(6, int(8 * UI_SCALE))
    ACTION_ROW_GAP_Y = max(6, int(8 * UI_SCALE))

    PIECE_RADIUS = max(16, min(36, int(24 * UI_SCALE)))
    HP_BAR_W = max(30, int(40 * UI_SCALE))
    HP_BAR_H = max(4, int(5 * UI_SCALE))
    HP_BAR_OFFSET_Y = PIECE_RADIUS + 3

    HIGHLIGHT_MOVE_R = max(6, int(10 * UI_SCALE))
    HIGHLIGHT_ATTACK_R = max(7, int(12 * UI_SCALE))


# Initial layout for import-time defaults
apply_layout_for_window_size(WINDOW_W, WINDOW_H)

# ---------------------------------------------------------------------------
# Colours  (R, G, B)
# ---------------------------------------------------------------------------

# Board surface
C_BG            = (245, 222, 179)   # wheat — board background
C_BOARD_LINE    = ( 90,  55,  20)   # dark brown grid lines
C_NODE_DOT      = ( 90,  55,  20)
C_RIVER_FILL    = (173, 216, 230, 90)   # pale-blue river (with alpha)
C_PALACE_LINE   = (140,  90,  40)       # palace diagonal lines

# Pieces
C_HUMANSIDE_FILL      = (192,  28,  28)   # HumanSide faction circle
C_ORCSIDE_FILL    = ( 35,  35,  35)   # OrcSide faction circle
C_PIECE_BORDER  = (255, 255, 255)
C_PIECE_TEXT    = (255, 255, 255)
C_DEAD_FILL     = (140, 140, 140)
C_DEAD_X        = (200,  40,  40)

# Highlights
C_SELECTED      = (255, 210,   0)   # gold ring: selected piece
C_MOVE_DOT      = ( 50, 200,  50)   # green: valid move
C_ATTACK_DOT    = (220,  50,  50)   # HumanSide: valid attack target / wizard center
C_HOVER         = (200, 200,  50, 60)

# Event points
C_AMMO          = (255, 165,   0)   # orange — ammunition
C_MED           = (  0, 180,  60)   # green — medical
C_TRAP          = (160,   0, 200)   # purple — trap

# Side panel
C_PANEL_BG      = ( 28,  28,  45)
C_PANEL_BORDER  = ( 60,  60,  90)
C_PANEL_TEXT    = (220, 220, 220)
C_HUMANSIDE_LABEL     = (230,  80,  80)
# OrcSide: green contrast vs HumanSide red
C_ORCSIDE_LABEL   = (120, 230, 140)
C_MSG_TEXT      = (255, 215,  80)   # yellow instructions
C_MUTED         = (130, 130, 130)
C_HP_FULL       = ( 60, 200,  60)
C_HP_EMPTY      = ( 80,  40,  40)
C_BTN_BG        = ( 55,  55,  80)
C_BTN_HOVER     = ( 80,  80, 120)
C_BTN_TEXT      = (230, 230, 230)
C_VICTORY_HUMANSIDE   = (220,  60,  60)
C_VICTORY_ORCSIDE   = (100, 130, 255)
C_VICTORY_DRAW  = (200, 200,  80)

# ---------------------------------------------------------------------------
# Piece display labels
# ---------------------------------------------------------------------------
PIECE_LABELS = {
    "GeneralHuman": "GH",
    "ArcherHuman": "AH",
    "LancerHuman": "LH",
    "WizardHuman": "WH",
    "Soldier1Human": "1H",
    "Soldier2Human": "2H",
    "Soldier3Human": "3H",
    "GeneralOrc": "GO",
    "ArcherSkeleton": "AS",
    "RiderOrc": "RO",
    "Slime Orc": "SO",
    "Soldier1Orc": "1O",
    "Soldier2Skeleton": "2S",
    "Soldier3Skeleton": "3S",
}
