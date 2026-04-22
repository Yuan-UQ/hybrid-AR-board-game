from __future__ import annotations

"""
Bridge layer between detect_marker.py vision output and teammate movement_rules.py.

What this module does
---------------------
1. Accepts vision-side piece positions in the form used by detect_marker:
      {aruco_id: (x, y)}
2. Creates a lightweight backend state object that matches the subset required by
   movement_rules.py.
3. Evaluates whether a detected move is legal.
4. Computes attack opportunities after a legal move.

Important note
--------------
The uploaded movement_rules.py depends on the package paths:
    xiangqi_arena.core.constants
    xiangqi_arena.core.enums
    xiangqi_arena.core.utils
    xiangqi_arena.models.piece
    xiangqi_arena.state.game_state
Those files are not present in the current upload, so this bridge injects minimal
shim modules into sys.modules and then imports movement_rules.py unchanged.

This means you can still reuse your teammate's movement_rules.py without editing
its internal logic.
"""

from dataclasses import dataclass
from enum import Enum
import importlib.util
import sys
import types
from pathlib import Path
from typing import Dict, List, Optional, Tuple

Pos = Tuple[int, int]

BOARD_COLS = 9
BOARD_ROWS = 10
ORTHOGONAL_DIRECTIONS: tuple[Pos, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))
ROOK_MAX_RANGE = 3
CANNON_MOVE_MAX = 2
PALACE_BOUNDS = {
    "RED": {"x": (3, 5), "y": (0, 2)},
    "BLACK": {"x": (3, 5), "y": (7, 9)},
}

BASE_STATS = {
    "GENERAL": {"hp": 10, "atk": 1},
    "ROOK": {"hp": 5, "atk": 2},
    "HORSE": {"hp": 4, "atk": 3},
    "CANNON": {"hp": 5, "atk": 1},
    "PAWN": {"hp": 3, "atk": 1},
}

PIECE_NAME_BY_ID = {
    10: "red_general",
    11: "red_chariot",
    12: "red_horse",
    13: "red_cannon",
    14: "red_pawn_1",
    15: "red_pawn_2",
    16: "red_pawn_3",
    17: "black_general",
    18: "black_chariot",
    19: "black_horse",
    20: "black_cannon",
    21: "black_pawn_1",
    22: "black_pawn_2",
    23: "black_pawn_3",
}


class Faction(Enum):
    RED = "RED"
    BLACK = "BLACK"


class PieceType(Enum):
    GENERAL = "GENERAL"
    ROOK = "ROOK"
    HORSE = "HORSE"
    CANNON = "CANNON"
    PAWN = "PAWN"


@dataclass
class PieceAdapter:
    aruco_id: int
    name: str
    faction: Faction
    piece_type: PieceType
    pos: Pos
    hp: int
    max_hp: int
    atk: int
    is_dead: bool = False
    is_operable: bool = True


class BoardAdapter:
    def __init__(self, pieces: Dict[int, PieceAdapter]):
        self._pieces = pieces

    def living_pieces(self) -> List[PieceAdapter]:
        return [p for p in self._pieces.values() if not p.is_dead]

    def is_within(self, x: int, y: int) -> bool:
        return 0 <= x < BOARD_COLS and 0 <= y < BOARD_ROWS

    def piece_at(self, x: int, y: int) -> Optional[PieceAdapter]:
        for p in self.living_pieces():
            if p.pos == (x, y):
                return p
        return None

    def is_empty(self, x: int, y: int) -> bool:
        return self.piece_at(x, y) is None

    def is_occupied(self, x: int, y: int) -> bool:
        return self.piece_at(x, y) is not None


@dataclass
class GameStateAdapter:
    board: BoardAdapter


@dataclass
class MoveCheckResult:
    ok: bool
    reason: str
    legal_moves: List[Pos]
    attack_options: dict


@dataclass
class AttackPreview:
    can_attack: bool
    kind: str
    targets: List[dict]
    extra: dict


# -----------------------------------------------------------------------------
# Utility helpers required by teammate movement_rules.py
# -----------------------------------------------------------------------------

def is_within_board(x: int, y: int) -> bool:
    return 0 <= x < BOARD_COLS and 0 <= y < BOARD_ROWS


def has_crossed_river(x: int, y: int, faction: Faction) -> bool:
    if faction is Faction.RED:
        return y >= 5
    return y <= 4


def horse_reachable(x: int, y: int, is_occupied_fn) -> List[Pos]:
    # Standard Xiangqi horse with leg-blocking.
    result: List[Pos] = []
    patterns = [
        ((0, 1), (-1, 2)),
        ((0, 1), (1, 2)),
        ((0, -1), (-1, -2)),
        ((0, -1), (1, -2)),
        ((1, 0), (2, -1)),
        ((1, 0), (2, 1)),
        ((-1, 0), (-2, -1)),
        ((-1, 0), (-2, 1)),
    ]
    for leg, landing in patterns:
        lx, ly = x + leg[0], y + leg[1]
        if not is_within_board(lx, ly) or is_occupied_fn(lx, ly):
            continue
        nx, ny = x + landing[0], y + landing[1]
        if is_within_board(nx, ny):
            result.append((nx, ny))
    return result


# -----------------------------------------------------------------------------
# Minimal shim package so uploaded movement_rules.py can be imported unchanged
# -----------------------------------------------------------------------------

def _ensure_module(name: str) -> types.ModuleType:
    mod = sys.modules.get(name)
    if mod is None:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
    return mod



def install_xiangqi_shims() -> None:
    _ensure_module("xiangqi_arena")
    _ensure_module("xiangqi_arena.core")
    _ensure_module("xiangqi_arena.models")
    _ensure_module("xiangqi_arena.state")

    constants_mod = _ensure_module("xiangqi_arena.core.constants")
    constants_mod.ROOK_MAX_RANGE = ROOK_MAX_RANGE
    constants_mod.CANNON_MOVE_MAX = CANNON_MOVE_MAX
    constants_mod.PALACE_BOUNDS = {
        Faction.RED: PALACE_BOUNDS["RED"],
        Faction.BLACK: PALACE_BOUNDS["BLACK"],
    }

    enums_mod = _ensure_module("xiangqi_arena.core.enums")
    enums_mod.Faction = Faction
    enums_mod.PieceType = PieceType

    utils_mod = _ensure_module("xiangqi_arena.core.utils")
    utils_mod.ORTHOGONAL_DIRECTIONS = ORTHOGONAL_DIRECTIONS
    utils_mod.has_crossed_river = has_crossed_river
    utils_mod.horse_reachable = horse_reachable
    utils_mod.is_within_board = is_within_board

    piece_mod = _ensure_module("xiangqi_arena.models.piece")
    piece_mod.Piece = PieceAdapter

    state_mod = _ensure_module("xiangqi_arena.state.game_state")
    state_mod.GameState = GameStateAdapter



def load_uploaded_movement_rules(path: str | Path = "/mnt/data/movement_rules.py"):
    install_xiangqi_shims()
    path = Path(path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    spec = importlib.util.spec_from_file_location("uploaded_movement_rules", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load movement_rules from: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -----------------------------------------------------------------------------
# Piece metadata + engine
# -----------------------------------------------------------------------------

def parse_piece_meta(aruco_id: int) -> tuple[str, Faction, PieceType]:
    name = PIECE_NAME_BY_ID[aruco_id]
    faction = Faction.RED if name.startswith("red_") else Faction.BLACK
    if "general" in name:
        piece_type = PieceType.GENERAL
    elif "chariot" in name:
        piece_type = PieceType.ROOK
    elif "horse" in name:
        piece_type = PieceType.HORSE
    elif "cannon" in name:
        piece_type = PieceType.CANNON
    elif "pawn" in name:
        piece_type = PieceType.PAWN
    else:
        raise ValueError(f"Unknown piece name: {name}")
    return name, faction, piece_type


class VisionRuleEngine:
    def __init__(self, movement_rules_path: str | Path = "/mnt/data/movement_rules.py"):
        self.rules = load_uploaded_movement_rules(movement_rules_path)
        self.pieces: Dict[int, PieceAdapter] = {}
        self.last_moved_id: Optional[int] = None

    def _rebuild_state(self) -> GameStateAdapter:
        return GameStateAdapter(board=BoardAdapter(self.pieces))

    def sync_from_vision(self, piece_cells: Dict[int, Pos]) -> None:
        """Initialise or hard-sync backend positions from detect_marker piece_last_cell."""
        new_pieces: Dict[int, PieceAdapter] = {}
        for aruco_id, pos in piece_cells.items():
            name, faction, piece_type = parse_piece_meta(aruco_id)
            stats = BASE_STATS[piece_type.value]
            old = self.pieces.get(aruco_id)
            hp = old.hp if old else stats["hp"]
            atk = old.atk if old else stats["atk"]
            is_dead = old.is_dead if old else False
            is_operable = (not is_dead)
            new_pieces[aruco_id] = PieceAdapter(
                aruco_id=aruco_id,
                name=name,
                faction=faction,
                piece_type=piece_type,
                pos=pos,
                hp=hp,
                max_hp=stats["hp"],
                atk=atk,
                is_dead=is_dead,
                is_operable=is_operable,
            )
        self.pieces = new_pieces

    def check_move(self, aruco_id: int, old_pos: Pos, new_pos: Pos, current_player: str) -> MoveCheckResult:
        piece = self.pieces[aruco_id]
        state = self._rebuild_state()

        if piece.faction.value != current_player:
            legal_moves = self.rules.get_legal_moves(piece, state)
            return MoveCheckResult(
                ok=False,
                reason=f"Not {current_player}'s piece: {piece.name}",
                legal_moves=sorted(legal_moves),
                attack_options={},
            )

        if piece.pos != old_pos:
            # Vision and backend diverged. Re-anchor to vision old_pos before check.
            piece.pos = old_pos
            state = self._rebuild_state()

        legal_moves: List[Pos] = sorted(self.rules.get_legal_moves(piece, state))
        if new_pos not in legal_moves:
            return MoveCheckResult(
                ok=False,
                reason=f"Illegal move for {piece.name}: {old_pos} -> {new_pos}",
                legal_moves=legal_moves,
                attack_options={},
            )

        # Commit move.
        piece.pos = new_pos
        self.last_moved_id = aruco_id
        attack_preview = self.preview_attack(aruco_id)
        return MoveCheckResult(
            ok=True,
            reason=f"Legal move for {piece.name}: {old_pos} -> {new_pos}",
            legal_moves=legal_moves,
            attack_options={
                "can_attack": attack_preview.can_attack,
                "kind": attack_preview.kind,
                "targets": attack_preview.targets,
                "extra": attack_preview.extra,
            },
        )

    def preview_attack(self, aruco_id: int) -> AttackPreview:
        piece = self.pieces[aruco_id]
        state = self._rebuild_state()
        if piece.is_dead or not piece.is_operable:
            return AttackPreview(False, "none", [], {})

        if piece.piece_type is PieceType.CANNON:
            return self._preview_cannon_attack(piece, state)
        return self._preview_standard_attack(piece, state)

    def _preview_standard_attack(self, piece: PieceAdapter, state: GameStateAdapter) -> AttackPreview:
        reachable = self.rules.reachable_nodes(piece, state)
        targets = []
        for pos in reachable:
            target = state.board.piece_at(*pos)
            if target is None or target.faction is piece.faction or target.is_dead:
                continue
            damage = self._compute_damage(piece, target)
            targets.append({
                "target_id": target.aruco_id,
                "target_name": target.name,
                "pos": pos,
                "damage": damage,
            })
        return AttackPreview(bool(targets), "standard", targets, {})

    def _preview_cannon_attack(self, piece: PieceAdapter, state: GameStateAdapter) -> AttackPreview:
        x, y = piece.pos
        direction_map = {
            (0, -1): "UP",
            (0, 1): "DOWN",
            (-1, 0): "LEFT",
            (1, 0): "RIGHT",
        }
        all_targets: List[dict] = []
        directions: List[dict] = []

        for dx, dy in ORTHOGONAL_DIRECTIONS:
            cx, cy = x + 3 * dx, y + 3 * dy
            if not is_within_board(cx, cy):
                continue
            center = state.board.piece_at(cx, cy)
            if center is None or center.faction is piece.faction or center.is_dead:
                continue

            affected = []
            cross_cells = [
                (cx, cy),
                (cx, cy - 1),
                (cx, cy + 1),
                (cx - 1, cy),
                (cx + 1, cy),
            ]
            seen_ids = set()
            for tx, ty in cross_cells:
                if not is_within_board(tx, ty):
                    continue
                target = state.board.piece_at(tx, ty)
                if target is None or target.faction is piece.faction or target.is_dead:
                    continue
                if target.aruco_id in seen_ids:
                    continue
                seen_ids.add(target.aruco_id)
                damage = self._compute_damage(piece, target)
                payload = {
                    "target_id": target.aruco_id,
                    "target_name": target.name,
                    "pos": (tx, ty),
                    "damage": damage,
                }
                affected.append(payload)
                all_targets.append(payload)

            directions.append({
                "direction": direction_map[(dx, dy)],
                "center": (cx, cy),
                "affected": affected,
            })

        return AttackPreview(bool(directions), "cannon_aoe", all_targets, {"directions": directions})

    def _compute_damage(self, attacker: PieceAdapter, target: PieceAdapter) -> int:
        damage = attacker.atk
        if attacker.piece_type is PieceType.PAWN and self._pawn_has_adjacent_ally(attacker):
            damage += 1
        if target.piece_type is PieceType.GENERAL and self._general_in_own_palace(target):
            damage = max(0, damage - 1)
        return max(0, damage)

    def _pawn_has_adjacent_ally(self, pawn: PieceAdapter) -> bool:
        px, py = pawn.pos
        for other in self.pieces.values():
            if other.aruco_id == pawn.aruco_id or other.is_dead or other.faction is not pawn.faction:
                continue
            ox, oy = other.pos
            if abs(ox - px) <= 1 and abs(oy - py) <= 1:
                return True
        return False

    def _general_in_own_palace(self, general: PieceAdapter) -> bool:
        if general.piece_type is not PieceType.GENERAL:
            return False
        bounds = PALACE_BOUNDS[general.faction.value]
        x, y = general.pos
        return bounds["x"][0] <= x <= bounds["x"][1] and bounds["y"][0] <= y <= bounds["y"][1]

    def describe_attack(self, aruco_id: int) -> str:
        preview = self.preview_attack(aruco_id)
        piece = self.pieces[aruco_id]
        if not preview.can_attack:
            return f"{piece.name}: no attack available"
        if preview.kind == "standard":
            parts = [f"{t['target_name']}@{t['pos']} dmg={t['damage']}" for t in preview.targets]
            return f"{piece.name}: can attack -> " + ", ".join(parts)
        dir_parts = []
        for d in preview.extra.get("directions", []):
            if d["affected"]:
                hit_txt = ", ".join(f"{h['target_name']}@{h['pos']} dmg={h['damage']}" for h in d["affected"])
            else:
                hit_txt = "no enemy in cross"
            dir_parts.append(f"{d['direction']} center={d['center']} [{hit_txt}]")
        return f"{piece.name}: cannon attack directions -> " + " | ".join(dir_parts)


if __name__ == "__main__":
    # Minimal smoke test using your documented opening positions.
    engine = VisionRuleEngine("/mnt/data/movement_rules.py")
    engine.sync_from_vision({
        10: (4, 0),
        11: (0, 0),
        12: (1, 0),
        13: (7, 0),
        14: (2, 3),
        15: (4, 3),
        16: (6, 3),
        17: (4, 9),
        18: (0, 9),
        19: (1, 9),
        20: (7, 9),
        21: (2, 6),
        22: (4, 6),
        23: (6, 6),
    })
    result = engine.check_move(13, (7, 0), (7, 2), "RED")
    print(result)
    print(engine.describe_attack(13))
