"""
End-to-end integration simulation for Xiangqi Arena (no UI / no input required).

Run with:
    python simulate.py

Each scenario prints its steps and asserts expected outcomes.
A final summary line reports how many scenarios passed.
"""

from __future__ import annotations

import traceback
from typing import Callable

from xiangqi_arena.core.enums import Faction, Phase, PieceType, VictoryState, EventPointType
from xiangqi_arena.flow.phase import advance_phase
from xiangqi_arena.flow.round import should_spawn_event_point, round_summary
from xiangqi_arena.flow.turn import end_turn, start_turn
from xiangqi_arena.modification.attack import (
    apply_attack,
    apply_cannon_attack,
    apply_skip_attack,
)
from xiangqi_arena.modification.event import apply_event_trigger, spawn_event_point
from xiangqi_arena.modification.move import apply_move, apply_skip_move
from xiangqi_arena.models.event_point import EventPoint
from xiangqi_arena.rules.event_rules import get_all_triggers, get_triggered_piece
from xiangqi_arena.rules.piece_rules import legal_attack_targets, legal_moves
from xiangqi_arena.rules.victory_rules import check_victory
from xiangqi_arena.state.game_state import GameState, build_default_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEP = "─" * 60


def step(msg: str) -> None:
    print(f"  ▸ {msg}")


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def _place(gs: GameState, pid: str, x: int, y: int) -> None:
    """Teleport a piece to (x, y) for test setup (bypasses rules)."""
    p = gs.pieces[pid]
    gs.board.remove_piece(*p.pos)
    p.pos = (x, y)
    gs.board.place_piece(pid, x, y)


def _run_phase(gs: GameState, phase: Phase, body: Callable[[], None]) -> None:
    """Assert we are in *phase*, run *body*, then print current summary."""
    assert gs.current_phase is phase, (
        f"Expected {phase.name}, got {gs.current_phase.name}"
    )
    step(f"Phase {phase.value}: {phase.name}")
    body()


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------

scenarios: list[tuple[str, Callable[[], None]]] = []


def scenario(name: str):
    def decorator(fn):
        scenarios.append((name, fn))
        return fn
    return decorator


# ===========================================================================
# Scenario 1: Full first turn — Red moves rook, skips attack
# ===========================================================================

@scenario("Full turn: move + skip attack")
def scenario_move_skip_attack():
    gs = build_default_state()
    section("Scenario 1 — Red: move rook, skip attack")

    # ── Phase START ────────────────────────────────────────────────────────
    _run_phase(gs, Phase.START, lambda: None)
    step(round_summary(gs))
    assert should_spawn_event_point(gs), "Round 1 should spawn event point"
    spawn_event_point(gs)
    assert len(gs.event_points) > 0
    ep_desc = "  /  ".join(f"{ep.event_type.value}@{ep.pos}" for ep in gs.event_points)
    ok(f"Event point(s) spawned: {ep_desc}")
    advance_phase(gs)

    # ── Phase MOVEMENT ────────────────────────────────────────────────────
    _run_phase(gs, Phase.MOVEMENT, lambda: None)
    rook = gs.pieces["red_rook"]   # (8, 0) after position update
    moves = legal_moves(rook, gs)
    step(f"red_rook legal moves: {sorted(moves)}")
    # Rook is at (8,0); (8,1) should be in its legal moves (up the column)
    assert (8, 1) in moves, f"Expected (8,1) in moves, got {moves}"
    apply_move("red_rook", (8, 1), gs)
    assert rook.pos == (8, 1)
    assert gs.board.get_piece_id_at(8, 1) == "red_rook"
    ok("Rook moved (8,0) → (8,1)")
    advance_phase(gs)

    # ── Phase RECOGNITION ─────────────────────────────────────────────────
    _run_phase(gs, Phase.RECOGNITION, lambda: None)
    triggers = get_all_triggers(gs)
    if triggers:
        for pid, ep in triggers:
            step(f"Event triggered: {pid} at {ep.pos} → {ep.event_type.value}")
            apply_event_trigger(pid, ep, gs)
    else:
        step("No event point triggered this recognition phase")
    ok("Recognition phase complete")
    advance_phase(gs)

    # ── Phase ATTACK ──────────────────────────────────────────────────────
    _run_phase(gs, Phase.ATTACK, lambda: None)
    attacks = legal_attack_targets(rook, gs)
    step(f"red_rook legal attacks: {attacks}")
    apply_skip_attack(gs)
    ok("Attack skipped")
    advance_phase(gs)

    # ── Phase RESOLVE ─────────────────────────────────────────────────────
    _run_phase(gs, Phase.RESOLVE, lambda: None)
    assert check_victory(gs) is VictoryState.ONGOING
    ok("Victory check: ONGOING")

    # end_turn switches to Black
    end_turn(gs)
    assert gs.active_faction is Faction.BLACK
    assert gs.current_phase is Phase.START
    assert gs.round_number == 1   # still round 1 (Black hasn't gone yet)
    ok(f"Turn ended → {gs.active_faction.value.upper()}'s turn, round {gs.round_number}")


# ===========================================================================
# Scenario 2: Red attacks and kills a piece
# ===========================================================================

@scenario("Attack: rook kills pawn")
def scenario_attack_kill():
    gs = build_default_state()
    section("Scenario 2 — Red rook kills Black pawn")

    # Place black pawn within rook range: rook is now at (8,0)
    _place(gs, "black_pawn_0", 8, 3)   # 3 nodes directly above rook (8,0)
    step("black_pawn_0 placed at (8,3)")

    # Fast-forward to ATTACK phase manually for this scenario
    gs.current_phase = Phase.ATTACK

    attacks = legal_attack_targets(gs.pieces["red_rook"], gs)
    step(f"red_rook attack targets: {attacks}")
    assert (8, 3) in attacks

    apply_attack("red_rook", (8, 3), gs)
    bp = gs.pieces["black_pawn_0"]
    step(f"black_pawn_0 HP after hit: {bp.hp}/{bp.max_hp}")
    assert bp.hp == 1, f"Expected 1 HP, got {bp.hp}"   # ATK=2, HP=3 → 1
    ok("First hit: pawn survives with 1 HP")

    # Hit again (new turn for test: reset action context)
    gs.action.reset()
    gs.current_phase = Phase.ATTACK
    apply_attack("red_rook", (8, 3), gs)
    step(f"black_pawn_0 HP after second hit: {bp.hp}")
    assert bp.is_dead
    assert gs.board.is_empty(0, 3)
    ok("Second hit: pawn killed and removed from board")
    assert check_victory(gs) is VictoryState.ONGOING
    ok("Game still ongoing (no general killed)")


# ===========================================================================
# Scenario 3: Kill General → immediate victory
# ===========================================================================

@scenario("Kill General → victory")
def scenario_kill_general():
    gs = build_default_state()
    section("Scenario 3 — Red horse kills Black General")

    # Weaken black general to 1 HP
    bg = gs.pieces["black_general"]   # (4, 9) — in black palace
    bg.hp = 1
    step(f"black_general HP set to 1 (pos: {bg.pos})")

    # Place red horse where it can reach (4, 9)
    # From (2, 8): step up (2,9) free → diag (4,9) ✓  (leg (2,9) must be empty)
    _place(gs, "red_horse", 2, 8)
    step("red_horse placed at (2,8)")

    gs.current_phase = Phase.ATTACK
    attacks = legal_attack_targets(gs.pieces["red_horse"], gs)
    step(f"red_horse attack targets: {attacks}")
    assert (4, 9) in attacks, f"Expected (4,9) in {attacks}"

    apply_attack("red_horse", (4, 9), gs)
    step(f"black_general HP after hit: {bg.hp}")
    assert bg.is_dead
    assert gs.board.is_empty(4, 9)
    assert gs.victory_state is VictoryState.RED_WIN
    ok(f"BLACK GENERAL KILLED → victory_state = {gs.victory_state.value}")


# ===========================================================================
# Scenario 4: Cannon AOE attack
# ===========================================================================

@scenario("Cannon AOE attack")
def scenario_cannon_aoe():
    gs = build_default_state()
    section("Scenario 4 — Red Cannon cross AOE")

    # Cannon at (3, 0), aim up, center (3, 3)
    _place(gs, "red_cannon", 3, 0)
    _place(gs, "black_pawn_0", 3, 3)   # center
    _place(gs, "black_pawn_1", 3, 4)   # 1 above center
    _place(gs, "black_pawn_2", 3, 2)   # 1 below center
    # (2, 3) and (4, 3) are empty in default → no pieces in left/right cross
    step("red_cannon at (3,0); black pawns at (3,2),(3,3),(3,4)")

    gs.current_phase = Phase.ATTACK
    cannon = gs.pieces["red_cannon"]
    attacks = legal_attack_targets(cannon, gs)
    step(f"Cannon valid center(s): {attacks}")
    assert (3, 3) in attacks

    apply_cannon_attack("red_cannon", (3, 3), gs)
    cannon_atk = gs.pieces["red_cannon"].atk   # 2 after stats adjustment
    for pid in ("black_pawn_0", "black_pawn_1", "black_pawn_2"):
        p = gs.pieces[pid]
        step(f"  {pid} HP: {p.hp}/{p.max_hp} (pos {p.pos})")
        expected = max(0, p.max_hp - cannon_atk)
        assert p.hp == expected or p.is_dead, \
            f"{pid} expected hp={expected}, got {p.hp}"
    ok(f"All 3 cross-AOE targets hit for {cannon_atk} damage each")


# ===========================================================================
# Scenario 5: Pawn nearby-ally attack bonus
# ===========================================================================

@scenario("Pawn nearby-ally ATK bonus")
def scenario_pawn_bonus():
    gs = build_default_state()
    section("Scenario 5 — Pawn gets +1 ATK from nearby ally")

    # Pawn at (4,4) — just crossed river. Place ally adjacent (3,4).
    pawn = gs.pieces["red_pawn_1"]   # default (4,3)
    _place(gs, "red_pawn_1", 4, 4)   # on river boundary

    # Place a friendly piece next to pawn to trigger bonus
    _place(gs, "red_pawn_0", 3, 4)   # immediately left → inside 3×3 of (4,4)
    step(f"red_pawn_1 at (4,4), red_pawn_0 at (3,4) — ally in 3×3 neighbourhood")

    # Place an enemy directly in front of pawn
    bp = gs.pieces["black_pawn_2"]
    _place(gs, "black_pawn_2", 4, 5)
    step(f"black_pawn_2 placed at (4,5) — directly ahead of pawn")

    gs.current_phase = Phase.ATTACK
    attacks = legal_attack_targets(pawn, gs)
    step(f"red_pawn_1 attack targets: {attacks}")
    assert (4, 5) in attacks

    apply_attack("red_pawn_1", (4, 5), gs)
    # Pawn ATK=1, ally bonus +1 = 2 total, no palace reduction → damage=2
    step(f"black_pawn_2 HP after hit: {bp.hp}")
    assert bp.hp == 1, f"Expected 1, got {bp.hp}"   # 3 - 2 = 1
    ok("Pawn bonus applied: pawn dealt 2 damage (base 1 + ally +1)")


# ===========================================================================
# Scenario 6: Full round — Red + Black each complete a turn → round advances
# ===========================================================================

@scenario("Full round: both players take a turn")
def scenario_full_round():
    gs = build_default_state()
    section("Scenario 6 — Full round (Red + Black), event point spawning rule")

    def take_minimal_turn(faction_name: str):
        step(f"--- {faction_name} minimal turn ---")
        assert gs.current_phase is Phase.START
        if should_spawn_event_point(gs):
            spawn_event_point(gs)
            ep_desc = "  /  ".join(f"{ep.event_type.value}@{ep.pos}" for ep in gs.event_points)
            step(f"  Event point(s) spawned: {ep_desc}")
        else:
            step(f"  No spawn (faction={gs.active_faction.value}, round={gs.round_number})")
        advance_phase(gs)   # START → MOVEMENT
        apply_skip_move(gs)
        advance_phase(gs)   # MOVEMENT → RECOGNITION
        for pid, ep in get_all_triggers(gs):
            apply_event_trigger(pid, ep, gs)
        advance_phase(gs)   # RECOGNITION → ATTACK
        apply_skip_attack(gs)
        advance_phase(gs)   # ATTACK → RESOLVE
        end_turn(gs)        # RESOLVE → next player START

    # Round 1, Red's turn: spawn occurs (odd round AND Red's turn)
    assert gs.round_number == 1 and gs.active_faction is Faction.RED
    assert should_spawn_event_point(gs), "Expected spawn on round 1 Red's turn"
    take_minimal_turn("RED")
    assert len(gs.event_points) > 0 and all(ep.is_valid for ep in gs.event_points), \
        "Event point(s) should persist after Red's turn"
    ok(f"Round 1 Red: {len(gs.event_points)} event point(s) spawned and still valid")

    # Round 1, Black's turn: NO spawn (same round, Black's turn)
    assert gs.round_number == 1 and gs.active_faction is Faction.BLACK
    assert not should_spawn_event_point(gs), \
        "Should NOT spawn again during Black's turn in same round"
    take_minimal_turn("BLACK")
    ok("Round 1 Black: no new spawn, event point(s) persist through Black's turn")

    # Round 2 starts: even round → no spawn; event points from round 1 still active
    assert gs.round_number == 2 and gs.active_faction is Faction.RED
    assert not should_spawn_event_point(gs), "Round 2 is even — no spawn"
    assert any(ep.is_valid for ep in gs.event_points), \
        "At least one event point from round 1 should still be valid in round 2"
    ok(f"After full round: round={gs.round_number}, active={gs.active_faction.value}")
    ok("Round 2 is even — no new spawn, but event point(s) from round 1 persist")


# ===========================================================================
# Scenario 7: Event point trigger — Medical heals, Trap kills (via trap)
# ===========================================================================

@scenario("Event point: Medical heal + Trap kill")
def scenario_event_points():
    gs = build_default_state()
    section("Scenario 7 — Event point effects")

    # MEDICAL heal
    pawn = gs.pieces["red_pawn_0"]   # (2,3)
    pawn.hp = 2
    step(f"red_pawn_0 HP set to 2 (max={pawn.max_hp})")
    med_ep = EventPoint(EventPointType.MEDICAL, (2, 3), 1)
    gs.event_points = [med_ep]
    apply_event_trigger("red_pawn_0", med_ep, gs)
    assert pawn.hp == 3 and len(gs.event_points) == 0
    ok(f"MEDICAL: HP healed back to {pawn.hp}/{pawn.max_hp}")

    # TRAP kill: HP at 1, trap reduces to 0 → dead
    gs2 = build_default_state()
    pawn2 = gs2.pieces["red_pawn_0"]
    pawn2.hp = 1
    step("red_pawn_0 HP set to 1 — will be killed by trap")
    trap_ep = EventPoint(EventPointType.TRAP, (2, 3), 1)
    gs2.event_points = [trap_ep]
    apply_event_trigger("red_pawn_0", trap_ep, gs2)
    assert pawn2.is_dead
    assert gs2.board.is_empty(2, 3)
    ok("TRAP: pawn killed (HP 1 → 0), removed from board")

    # AMMUNITION permanent buff stacks (each trigger now gives +2)
    gs3 = build_default_state()
    cannon = gs3.pieces["red_cannon"]
    base_atk = cannon.atk   # 2 (after constants change)
    _place(gs3, "red_cannon", 2, 2)
    for i in range(3):
        ammo_ep = EventPoint(EventPointType.AMMUNITION, (2, 2), i + 1)
        gs3.event_points = [ammo_ep]
        apply_event_trigger("red_cannon", ammo_ep, gs3)
    expected_atk = base_atk + 3 * 2   # base + three +2 stacks
    assert cannon.atk == expected_atk, f"Expected {expected_atk}, got {cannon.atk}"
    ok(f"AMMUNITION stacks: cannon ATK = {cannon.atk} (base {base_atk} + 3×2 buffs)")


# ===========================================================================
# Scenario 8: Pawn movement — pre/post river
# ===========================================================================

@scenario("Pawn movement: pre/post river")
def scenario_pawn_movement():
    gs = build_default_state()
    section("Scenario 8 — Pawn pre/post river movement options")

    pawn = gs.pieces["red_pawn_1"]   # (4,3) — before river (y<5)
    step(f"Pawn at {pawn.pos} — before river")
    pre_moves = legal_moves(pawn, gs)
    assert pre_moves == [(4, 4)], f"Expected [(4,4)], got {pre_moves}"
    ok(f"Pre-river: only forward → {pre_moves}")

    # Move pawn to y=5 (crossed river).
    # black_pawn_1 sits at (4,6) in the default setup — move it out of the way
    # so we can test lateral movement without an accidental blocker ahead.
    _place(gs, "black_pawn_1", 8, 6)
    _place(gs, "red_pawn_1", 4, 5)
    step(f"Pawn moved to {pawn.pos} — after river (y>=5 for Red)")
    post_moves = legal_moves(pawn, gs)
    step(f"Post-river moves: {sorted(post_moves)}")
    assert (4, 6) in post_moves   # forward
    assert (3, 5) in post_moves   # left
    assert (5, 5) in post_moves   # right
    ok(f"Post-river: forward + lateral → {sorted(post_moves)}")


# ===========================================================================
# Runner
# ===========================================================================

def run_all() -> None:
    print("\n" + "═" * 60)
    print("  XIANGQI ARENA — Integration Simulation")
    print("═" * 60)

    passed = 0
    failed = 0

    for name, fn in scenarios:
        try:
            fn()
            print(f"\n  ✅ PASSED: {name}")
            passed += 1
        except Exception:
            print(f"\n  ❌ FAILED: {name}")
            traceback.print_exc()
            failed += 1

    print("\n" + "═" * 60)
    total = passed + failed
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
    else:
        print("  — all good.")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    run_all()
