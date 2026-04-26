"""
Display constants shared across all ui/ modules.

All pixel geometry and colour definitions live here so that other ui modules
stay free of magic numbers.
"""

# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
WINDOW_W: int = 1600
WINDOW_H: int = 920
FPS: int = 60
WINDOW_TITLE: str = "hybrid-AR-board-game-frontend"

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

# Unified HUD layout geometry
HUD_MARGIN: int = 10
SIDE_PANEL_W: int = 250
PANEL_GAP: int = 12
BOTTOM_PANEL_H: int = 190

# Background-board image placement.  The source art is perspective-drawn, so
# board nodes use calibrated ratios instead of a single CELL value.
BOARD_IMAGE_LEFT: int = HUD_MARGIN + SIDE_PANEL_W + PANEL_GAP
BOARD_IMAGE_TOP: int = HUD_MARGIN
BOARD_IMAGE_W: int = WINDOW_W - 2 * (HUD_MARGIN + SIDE_PANEL_W + PANEL_GAP)
BOARD_IMAGE_H: int = WINDOW_H - BOTTOM_PANEL_H - HUD_MARGIN * 3

# Derived
BOARD_RIGHT: int  = BOARD_IMAGE_LEFT + BOARD_IMAGE_W
BOARD_BOTTOM: int = BOARD_IMAGE_TOP + BOARD_IMAGE_H

# ---------------------------------------------------------------------------
# HUD panels
# ---------------------------------------------------------------------------
LEFT_PANEL_X: int = HUD_MARGIN
RIGHT_PANEL_X: int = WINDOW_W - HUD_MARGIN - SIDE_PANEL_W
SIDE_PANEL_Y: int = HUD_MARGIN
SIDE_PANEL_H: int = BOARD_IMAGE_H
BOTTOM_PANEL_X: int = HUD_MARGIN
BOTTOM_PANEL_Y: int = WINDOW_H - HUD_MARGIN - BOTTOM_PANEL_H
BOTTOM_PANEL_W: int = WINDOW_W - HUD_MARGIN * 2

# Backward-compat aliases used by older code paths.
PANEL_X: int = RIGHT_PANEL_X
PANEL_W: int = SIDE_PANEL_W
PANEL_PAD: int = 10

# ---------------------------------------------------------------------------
# Piece rendering
# ---------------------------------------------------------------------------
PIECE_RADIUS: int = 24
HP_BAR_W: int     = 42
HP_BAR_H: int     = 5
HP_BAR_OFFSET_Y: int = PIECE_RADIUS + 3   # below the circle centre

# Click-snap threshold (pixels)
NODE_SNAP: int = 22

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
C_ORCSIDE_LABEL   = (140, 160, 255)
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
