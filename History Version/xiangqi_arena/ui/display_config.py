"""
Display constants shared across all ui/ modules.

All pixel geometry and colour definitions live here so that other ui modules
stay free of magic numbers.
"""

# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
WINDOW_W: int = 920
WINDOW_H: int = 710
FPS: int = 60
WINDOW_TITLE: str = "Xiangqi Arena"

# ---------------------------------------------------------------------------
# Board geometry
# Board nodes are laid out as a 9 × 10 intersection grid.
# y = 0 (Red's home row) is drawn at the BOTTOM of the board area.
# y = 9 (Black's home row) is drawn at the TOP of the board area.
# ---------------------------------------------------------------------------
CELL: int = 63           # pixels between adjacent nodes
BOARD_LEFT: int = 42     # left pixel margin to the first column (x=0)
BOARD_TOP: int = 42      # top pixel margin to the first row  (y=9)

# Derived
BOARD_RIGHT: int  = BOARD_LEFT + 8 * CELL   # pixel x of rightmost column
BOARD_BOTTOM: int = BOARD_TOP  + 9 * CELL   # pixel y of bottom row (y=0)

# ---------------------------------------------------------------------------
# Side panel (info / status)
# ---------------------------------------------------------------------------
PANEL_X: int  = BOARD_RIGHT + 55   # left edge of info panel
PANEL_W: int  = WINDOW_W - PANEL_X - 8
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
C_RED_FILL      = (192,  28,  28)   # red faction circle
C_BLACK_FILL    = ( 35,  35,  35)   # black faction circle
C_PIECE_BORDER  = (255, 255, 255)
C_PIECE_TEXT    = (255, 255, 255)
C_DEAD_FILL     = (140, 140, 140)
C_DEAD_X        = (200,  40,  40)

# Highlights
C_SELECTED      = (255, 210,   0)   # gold ring: selected piece
C_MOVE_DOT      = ( 50, 200,  50)   # green: valid move
C_ATTACK_DOT    = (220,  50,  50)   # red: valid attack target / cannon center
C_HOVER         = (200, 200,  50, 60)

# Event points
C_AMMO          = (255, 165,   0)   # orange — ammunition
C_MED           = (  0, 180,  60)   # green — medical
C_TRAP          = (160,   0, 200)   # purple — trap

# Side panel
C_PANEL_BG      = ( 28,  28,  45)
C_PANEL_BORDER  = ( 60,  60,  90)
C_PANEL_TEXT    = (220, 220, 220)
C_RED_LABEL     = (230,  80,  80)
C_BLACK_LABEL   = (140, 160, 255)
C_MSG_TEXT      = (255, 215,  80)   # yellow instructions
C_MUTED         = (130, 130, 130)
C_HP_FULL       = ( 60, 200,  60)
C_HP_EMPTY      = ( 80,  40,  40)
C_BTN_BG        = ( 55,  55,  80)
C_BTN_HOVER     = ( 80,  80, 120)
C_BTN_TEXT      = (230, 230, 230)
C_VICTORY_RED   = (220,  60,  60)
C_VICTORY_BLK   = (100, 130, 255)
C_VICTORY_DRAW  = (200, 200,  80)

# ---------------------------------------------------------------------------
# Piece-type display labels
# ---------------------------------------------------------------------------
PIECE_LABELS = {
    "general": "K",
    "rook":    "R",
    "horse":   "H",
    "cannon":  "C",
    "pawn":    "P",
}
