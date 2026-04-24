# Xiangqi Arena — Project Directory Outline

This document provides a structured overview of the project repository, covering the purpose, file descriptions, and contributor credits for each module. It is intended as a reference for team members and for future development.

---

## Project Overview

Xiangqi Arena is a hybrid AR board game that uses a physical Chinese chess board as its play surface. An overhead camera detects ArUco fiducial markers attached to the board corners and physical pieces, feeding positional data into a digital rule engine that manages game state, combat resolution, event points, and victory conditions. The goal is to preserve the physical and social feel of a tabletop game while offloading rule enforcement and state tracking to the computer.

---

## Top-Level Files

| File | Description |
|------|-------------|
| `README.md` | English project overview covering game background, turn structure, piece attributes, board rules, and system responsibilities. |
| `Project Description.png` | Visual project description image for presentations and external communication. |
| `Xiangqi Arena Rulebook V3.pdf` | Game rulebook (Version 3). Specifies piece attributes, movement rules, combat mechanics, event point system, and victory conditions. Primarily written by Kobe. |
| `Xiangqi Arena Project Directory and Module Development Guide v2.pdf` | Engineering documentation (Version 2). Covers module architecture, interface specifications, and development guidelines. Primarily written by Kobe. |
| `simulate.py` | End-to-end integration test script. Runs multiple game scenarios without a UI or camera to verify the correctness of the logic layer. |
| `.gitignore` | Git ignore configuration. |

---

## BoardDetection/

> **Role:** An early exploratory attempt at the vision layer. This branch has limited relevance to the project's current progress and is kept in the repository so that relevant team members can reference it when explaining individual contributions.

This module uses OpenCV ArUco detection to locate the board area via four corner markers (IDs 0–3), applies a perspective warp to produce a top-down view, and generates a 9×10 intersection grid on the warped image.


### File Descriptions

```
BoardDetection/
├── detect_marker.py                  # Standalone ArUco detection script. Detects the four
│                                     # corner markers in real time and draws IDs and centres.
├── markers/
│   ├── aruco_0.png ~ aruco_3.png     # ArUco marker images for the four board corners
│                                     # (DICT_4X4_50, IDs 0–3).
└── Board_detect/
    ├── digital_board_xiangqi.py      # Core script: reads camera → detects corner markers →
    │                                 # perspective warp → generates 9×10 grid (with optional
    │                                 # snap-to-board-lines) → live display. Supports keyboard
    │                                 # tuning of inner offset, quad expansion ratio, and snap radius.
    └── warp_xiangqi_board.py         # Helper script for board perspective transformation.
```

---

## Fiducial Marker Recognition/

> **Role:** The main experimental implementation of the vision recognition layer, contributed by **Andy**. Built on top of BoardDetection, it extends the system to semantically locate the board corners and track all 14 physical pieces by type and position. The next steps are to improve recognition stability and connect this layer to the backend logic layer (`xiangqi_arena`).

### File Descriptions

```
Fiducial Marker Recognition/pythonProject/
├── detect_marker.py           # Main program: full board + piece recognition and move tracking.
│                              # - Uses four corner markers (IDs 0–3) with semantic labels
│                              #   (RED_LEFT / RED_RIGHT / BLACK_LEFT / BLACK_RIGHT) and
│                              #   per-corner pixel offsets that can be tuned at runtime.
│                              # - Detects all 14 piece markers (IDs 10–23) in real time,
│                              #   estimates each piece's foot position, and confirms moves
│                              #   only after a stable-frame threshold (debounce).
│                              # - Displays a status panel showing current player, round,
│                              #   phase, and recent move log.
│                              # - Links to stable_board_view for a clean digital board overlay.
│                              # - Writes move records to a JSONL file.
│                              # - Supports extensive command-line arguments and live keyboard
│                              #   calibration controls.
├── detect_marker_2.py         # Alternative / updated detection script with similar logic,
│                              # used for comparison experiments or iterative development.
├── stable_board_view.py       # Stable digital board rendering module. Displays piece positions
│                              # on a pre-rendered 9×10 canvas (fixed topology) rather than
│                              # overlaying the raw camera feed, avoiding grid jitter. Writes
│                              # move records to JSONL.
├── generate_marker/
│   └── generate_markers.py    # Utility script: batch-generates ArUco marker images for
│                              # board corners and all 14 piece markers.
└── markers/
    ├── marker_0.png ~ marker_13.png   # Board corner and piece marker images
    │                                  # (IDs 0–3 for corners; IDs 10–13+ for pieces).
    ├── red_general.png                # Red General (帅)
    ├── red_chariot.png                # Red Chariot (车)
    ├── red_horse.png                  # Red Horse (马)
    ├── red_cannon.png                 # Red Cannon (炮)
    ├── red_pawn_1/2/3.png             # Red Pawns ×3 (兵)
    ├── black_general.png              # Black General (将)
    ├── black_chariot.png              # Black Chariot (车)
    ├── black_horse.png                # Black Horse (马)
    ├── black_cannon.png               # Black Cannon (炮)
    └── black_pawn_1/2/3.png           # Black Pawns ×3 (卒)
```

---

## prototype/

> **Role:** Early conceptual designs for the final presentation layer, contributed by **QingYang** and **Lily** (with a separate prototype by Niko). These prototypes were used to align the team on interface layout, game flow, and visual style before development began, and serve as a reference for building the display layer.

### File Descriptions

```
prototype/
├── Niko prototype.md              # Niko's interactive prototype notes with Figma link.
│                                  # Covers basic piece movement interaction and UI layout
│                                  # demonstrating overall game flow.
├── prototype Lily/
│   ├── v1.md                      # Lily's v1.0 prototype notes with Figma link.
│   │                              # Shows the game UI wireframe: board layout, player status
│   │                              # bar, round/phase info, and side information panels.
│   └── prototype v1.0.png         # Screenshot / design export of Lily's prototype.
└── prototype_Qingyang/
    ├── link.md                    # QingYang's Figma prototype link.
    ├── Camera Setup.png           # Screen: camera setup guidance.
    ├── Capture.png                # Screen: board recognition / scanning.
    ├── Game Ready.png             # Screen: game ready / start.
    ├── Gameplay.png               # Screen: normal gameplay.
    ├── Invalid Move.png           # Screen: illegal move notification.
    ├── Re-detection.png           # Screen: board re-detection prompt.
    ├── Game Over.png              # Screen: game over.
    └── Setup Guide.png            # Screen: setup guide.
```

---

## xiangqi_arena/

> **Role:** The complete backend logic layer implementing the gameplay mechanics agreed upon by the team, written by **Kobe**. Game logic is implemented in Python; the visual display layer uses Pygame and is functional enough for a full playthrough. The codebase follows a modular architecture that cleanly separates the logic layer, state layer, rule layer, recognition interface, input handling, and UI rendering, making it straightforward to extend and to connect with the vision layer.

### Entry Points

```
xiangqi_arena/
├── __init__.py       # Package initialisation.
├── __main__.py       # Supports launching via `python -m xiangqi_arena`.
└── main.py           # Main entry point: initialises game state and starts the main loop.
```

### core/ — Core Configuration and Definitions

```
core/
├── config.py      # Runtime configuration toggles: debug flags, manual-input fallback,
│                  # UI settings, recognition integration switches.
├── constants.py   # Global constants: board dimensions, per-piece movement ranges,
│                  # palace boundary coordinates, etc.
├── enums.py       # Project-wide enumerations:
│                  #   Faction (RED / BLACK)
│                  #   PieceType (GENERAL, ROOK, HORSE, CANNON, PAWN)
│                  #   EventPointType (AMMUNITION, MEDICAL, TRAP)
│                  #   Phase (START → MOVEMENT → RECOGNITION → ATTACK → RESOLVE)
│                  #   VictoryState (ONGOING, RED_WIN, BLACK_WIN, DRAW)
└── utils.py       # Geometry and board utility functions: orthogonal directions,
                   # horse reachability, river-crossing check, boundary validation.
```

### models/ — Data Models

```
models/
├── board.py         # Board class: 9×10 grid managing piece layout with occupancy
│                    # queries and piece add/remove operations.
├── piece.py         # Piece class: per-piece state — faction, type, position, HP,
│                    # ATK, death flag, and operability flag.
├── player.py        # Player class: player information and faction binding.
└── event_point.py   # EventPoint class: temporary digital-only event points
                     # (Ammunition: ATK +1 / Medical: HP +1 / Trap: HP -1).
```

### state/ — Game State Management

```
state/
└── game_state.py    # GameState class: holds the complete game state — board, both
                     # players, current phase, round number, active event points, and
                     # victory state. Provides build_default_state() to create a
                     # standard starting position.
```

### rules/ — Rule Adjudication (Pure Functions — No State Mutation)

```
rules/
├── movement_rules.py  # Legal move sets per piece type: General palace restriction,
│                      # Rook orthogonal ≤3 with path blocking, Horse L-shape with
│                      # leg blocking, Cannon move ≤2 (different from attack pattern),
│                      # Pawn forward-only before river / adds lateral after crossing.
├── attack_rules.py    # Legal attack targets per piece type: Cannon attacks exactly
│                      # 3 nodes away with a cross-shaped AOE; other pieces attack
│                      # enemy-occupied nodes within their movement range.
├── damage_rules.py    # Damage value calculation, including the Pawn's bonus ATK
│                      # when a friendly piece is within its 3×3 neighbourhood.
├── death_rules.py     # Piece death check: HP ≤ 0.
├── victory_rules.py   # Victory check: opponent General's HP ≤ 0 ends the game immediately.
├── event_rules.py     # Event point trigger check: a piece moving onto an event point
│                      # node activates its effect.
├── piece_rules.py     # Aggregation layer: exposes high-level interfaces such as
│                      # legal_moves() and legal_attack_targets().
└── illegal_rules.py   # Illegal operation detection: invalid destination, out-of-bounds, etc.
```

### flow/ — Turn and Phase Flow Control

```
flow/
├── phase.py   # Phase advancement: enforces the fixed sequence
│              # START → MOVEMENT → RECOGNITION → ATTACK → RESOLVE.
├── turn.py    # Turn start / end: start_turn() / end_turn(), switches current player.
├── round.py   # Round management: spawns an event point during START on odd rounds;
│              # provides round summary information.
└── action.py  # Action wrapper: encapsulates player operations (move, attack, skip)
               # into transferable Action objects.
```

### modification/ — State Mutation (Executes Actual Changes)

```
modification/
├── move.py          # apply_move() / apply_skip_move(): executes a piece move or skips
│                    # the movement phase.
├── attack.py        # apply_attack() / apply_cannon_attack() / apply_skip_attack():
│                    # executes a normal attack, the Cannon's AOE attack, or skips attack.
├── event.py         # apply_event_trigger() / spawn_event_point(): applies event point
│                    # effects and places new event points on the board.
└── spatial_rule.py  # Spatial helpers used by the modification layer: neighbourhood
                     # computation, zone checks, etc.
```

### recognition/ — Recognition Interface Layer (Bridge to Vision Layer)

```
recognition/
├── scanner_interface.py      # Abstract scanner interface to be implemented when
│                             # connecting the camera recognition module.
├── marker_parser.py          # Parses recognition output into piece ID and position data.
├── position_mapper.py        # Maps pixel / grid coordinates to logical board positions (col, row).
└── recognition_validator.py  # Validates the completeness and legality of recognition results.
```

### input_control/ — Input Handling

```
input_control/
├── keyboard_handler.py    # Keyboard event handling: phase advancement, quit, and other key mappings.
└── selection_handler.py   # Piece selection and target selection interaction logic
                           # (mouse click / keyboard navigation).
```

### ui/ — Pygame Visual Display Layer

```
ui/
├── display_config.py          # Display parameters: window size, cell size, margins, colour constants.
├── board_renderer.py          # Board rendering: draws the 9×10 grid, river boundary, and
│                              # palace diagonal lines.
├── piece_renderer.py          # Piece rendering: draws piece graphics and labels at
│                              # the corresponding board intersections.
├── highlight_renderer.py      # Highlight rendering: visual cues for the selected piece,
│                              # legal move destinations, and attackable targets.
├── event_renderer.py          # Event point rendering: displays Ammunition / Medical / Trap
│                              # point icons on the board.
├── death_marker_renderer.py   # Death marker rendering: marks the positions of defeated pieces.
└── others.py                  # Other UI elements: player info bars, round/phase labels,
                               # victory announcements, etc.
```


## xiangqi_arena MVPdemo/

> **Role:** Intermediate MVP version, written by **Lily**.

This folder represents an earlier playable version of the project with core game logic and a Pygame-based interface.

```text
xiangqi_arena MVPdemo/
├── __init__.py
├── main.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── constants.py
│   ├── enums.py
│   └── utils.py
├── models/
│   ├── __init__.py
│   ├── board.py
│   ├── piece.py
│   ├── player.py
│   └── event_point.py
├── rules/
│   ├── __init__.py
│   ├── movement_rules.py
│   ├── attack_rules.py
│   ├── damage_rules.py
│   ├── death_rules.py
│   ├── event_rules.py
│   └── victory_rules.py
├── modification/
│   ├── __init__.py
│   ├── move.py
│   ├── attack.py
│   ├── event.py
│   └── spatial_rule.py
├── state/
│   ├── __init__.py
│   └── game_state.py
└── ui/
    ├── __init__.py
    └── pygame_app.py
    

## xiangqi_arena_demo/

> **Role:** Standalone playable demo, written by **QingYang**.

This folder provides a simplified playable version of the game for testing and presentation.

```text
xiangqi_arena_demo/
├── README.md
├── config.py
├── main.py
├── core/
│   ├── board.py
│   ├── constants.py
│   ├── enums.py
│   ├── game_state.py
│   ├── piece.py
│   └── setup.py
├── engine/
│   ├── move_engine.py
│   ├── attack_engine.py
│   ├── turn_engine.py
│   ├── event_engine.py
│   └── validator.py
├── rules/
│   ├── common_rules.py
│   ├── general_rules.py
│   ├── rook_rules.py
│   ├── knight_rules.py
│   ├── cannon_rules.py
│   ├── pawn_rules.py
│   ├── damage_rules.py
│   ├── death_rules.py
│   ├── event_rules.py
│   └── victory_rules.py
└── ui/
    ├── board_ui.py
    ├── piece_ui.py
    ├── panel_ui.py
    ├── screens.py
    ├── colors.py
    ├── event_ui.py
    └── highlight_ui.py


## Niko's Files/

> **Role:** Niko's contribution includes an additional runnable project package, development configuration files, and a more complete gameplay implementation with multiple play modes.

These files extend beyond a simple prototype and include playable game code, packaging support, and gameplay orchestration modules.

### Top-Level Files

```text
pyproject.toml              # Project packaging and dependency configuration.
uv.lock                     # Dependency lock file for reproducible environment setup.

xiangqi_arena/
├── __init__.py             # Package initialisation.
├── __main__.py             # Supports launching via `python -m xiangqi_arena`.
├── main.py                 # Main entry point for the default gameplay loop.
├── console_game.py         # Console-based playable version.
├── pygame_game.py          # Pygame-based playable version.
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── constants.py
│   ├── enums.py
│   └── utils.py
├── models/
│   ├── __init__.py
│   ├── board.py
│   ├── piece.py
│   ├── player.py
│   └── event_point.py
├── state/
│   ├── __init__.py
│   └── game_state.py
├── rules/
│   ├── __init__.py
│   ├── movement_rules.py
│   ├── attack_rules.py
│   ├── damage_rules.py
│   ├── death_rules.py
│   ├── victory_rules.py
│   ├── event_rules.py
│   ├── piece_rules.py
│   └── illegal_rules.py
├── flow/
│   ├── __init__.py
│   ├── phase.py
│   ├── turn.py
│   ├── round.py
│   └── action.py
├── gameplay/
│   ├── __init__.py
│   ├── bootstrap.py
│   ├── board_sync.py
│   └── engine.py
├── modification/
│   ├── __init__.py
│   ├── move.py
│   ├── attack.py
│   ├── event.py
│   └── spatial_rule.py
├── recognition/
│   ├── __init__.py
│   ├── scanner_interface.py
│   ├── marker_parser.py
│   ├── position_mapper.py
│   └── recognition_validator.py
├── input_control/
│   ├── __init__.py
│   ├── keyboard_handler.py
│   └── selection_handler.py
└── ui/
    ├── __init__.py
    ├── board_renderer.py
    ├── piece_renderer.py
    ├── highlight_renderer.py
    ├── event_renderer.py
    ├── death_marker_renderer.py
    └── others.py
---

## Contributor Summary

| Module | Main Contributor(s) | Status |
|--------|---------------------|--------|
| `BoardDetection/` | — | Early exploration; archived for reference |
| `Fiducial Marker Recognition/` | Andy | Experimental; needs stability improvements and logic-layer integration |
| `prototype/` | QingYang, Lily (Niko separately) | Figma prototypes complete; reference for display-layer development |
| `xiangqi_arena/` (backend logic layer) | Kobe | Core logic complete and playable; UI and gameplay mechanics open for further refinement |
| Rulebook (PDF) | Kobe | Complete |
| Engineering Documentation (PDF) | Kobe | Complete |


---

## Planned Next Steps

1. **Vision layer stability:** Improve recognition robustness in `Fiducial Marker Recognition` to handle varying lighting conditions, camera angles, and partial occlusion.
2. **Vision–logic integration:** Connect the piece position output from `Fiducial Marker Recognition` to the scanner interface in `xiangqi_arena/recognition/`, enabling the physical board to drive the digital game state.
3. **Display layer development:** Build out `xiangqi_arena/ui/` in line with the `prototype/` designs, and integrate the camera feed with the game state display.
4. **Gameplay refinement:** Adjust piece attributes, movement/attack rules, event point spawn rates, and other game design parameters based on playtesting feedback.
