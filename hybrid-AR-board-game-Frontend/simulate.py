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
    apply_wizard_attack,
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
# Scenario 1: Full first turn — HumanSide moves archer, skips attack
# ===========================================================================

@scenario("Full turn: move + skip attack")
def scenario_move_skip_attack():
    gs = build_default_state()
    section("Scenario 1 — HumanSide: move archer, skip attack")

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
    archer = gs.pieces["ArcherHuman"]   # (9, 0) after coordinate update
    moves = legal_moves(archer, gs)
    step(f"ArcherHuman legal moves: {sorted(moves)}")
    # Archer is at (9,0); (8,0) should be in its legal moves (left one column)
    assert (8, 0) in moves, f"Expected (8,0) in moves, got {moves}"
    apply_move("ArcherHuman", (8, 0), gs)
    assert archer.pos == (8, 0)
    assert gs.board.get_piece_id_at(8, 0) == "ArcherHuman"
    ok("Archer moved (9,0) → (8,0)")
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
    attacks = legal_attack_targets(archer, gs)
    step(f"ArcherHuman legal attacks: {attacks}")
    apply_skip_attack(gs)
    ok("Attack skipped")
    advance_phase(gs)

    # ── Phase RESOLVE ─────────────────────────────────────────────────────
    _run_phase(gs, Phase.RESOLVE, lambda: None)
    assert check_victory(gs) is VictoryState.ONGOING
    ok("Victory check: ONGOING")

    # end_turn switches to OrcSide
    end_turn(gs)
    assert gs.active_faction is Faction.OrcSide
    assert gs.current_phase is Phase.START
    assert gs.round_number == 1   # still round 1 (OrcSide hasn't gone yet)
    ok(f"Turn ended → {gs.active_faction.value.upper()}'s turn, round {gs.round_number}")


# ===========================================================================
# Scenario 2: HumanSide attacks and kills a piece
# ===========================================================================

@scenario("Attack: archer kills soldier")
def scenario_attack_kill():
    gs = build_default_state()
    section("Scenario 2 — HumanSide archer kills OrcSide soldier")

    # Place OrcSide soldier within archer range: archer is now at (9,0)
    _place(gs, "Soldier1Orc", 6, 0)   # 3 nodes directly left of archer (9,0)
    step("Soldier1Orc placed at (6,0)")

    # Fast-forward to ATTACK phase manually for this scenario
    gs.current_phase = Phase.ATTACK

    attacks = legal_attack_targets(gs.pieces["ArcherHuman"], gs)
    step(f"ArcherHuman attack targets: {attacks}")
    assert (6, 0) in attacks

    apply_attack("ArcherHuman", (6, 0), gs)
    bp = gs.pieces["Soldier1Orc"]
    step(f"Soldier1Orc HP after hit: {bp.hp}/{bp.max_hp}")
    assert bp.hp == 1, f"Expected 1 HP, got {bp.hp}"   # ATK=2, HP=3 → 1
    ok("First hit: soldier survives with 1 HP")

    # Hit again (new turn for test: reset action context)
    gs.action.reset()
    gs.current_phase = Phase.ATTACK
    apply_attack("ArcherHuman", (6, 0), gs)
    step(f"Soldier1Orc HP after second hit: {bp.hp}")
    assert bp.is_dead
    assert gs.board.is_empty(6, 0)
    ok("Second hit: soldier killed and removed from board")
    assert check_victory(gs) is VictoryState.ONGOING
    ok("Game still ongoing (no leader killed)")


# ===========================================================================
# Scenario 3: Kill Leader → immediate victory
# ===========================================================================

@scenario("Kill Leader → victory")
def scenario_kill_leader():
    gs = build_default_state()
    section("Scenario 3 — HumanSide lancer kills OrcSide Leader")

    # Weaken OrcSide leader to 1 HP
    bg = gs.pieces["GeneralOrc"]   # (0, 4) — in OrcSide palace
    bg.hp = 1
    step(f"GeneralOrc HP set to 1 (pos: {bg.pos})")

    # Place HumanSide lancer where it can reach (0, 4).
    # From (1,6): leg (1,5) free -> L-shape to (0,4).
    _place(gs, "LancerHuman", 1, 6)
    step("LancerHuman placed at (1,6)")

    gs.current_phase = Phase.ATTACK
    attacks = legal_attack_targets(gs.pieces["LancerHuman"], gs)
    step(f"LancerHuman attack targets: {attacks}")
    assert (0, 4) in attacks, f"Expected (0,4) in {attacks}"

    apply_attack("LancerHuman", (0, 4), gs)
    step(f"GeneralOrc HP after hit: {bg.hp}")
    assert bg.is_dead
    assert gs.board.is_empty(0, 4)
    assert gs.victory_state is VictoryState.HumanSide_WIN
    ok(f"ORCSIDE GENERAL KILLED → victory_state = {gs.victory_state.value}")


# ===========================================================================
# Scenario 4: Wizard AOE attack
# ===========================================================================

@scenario("Wizard AOE attack")
def scenario_wizard_aoe():
    gs = build_default_state()
    section("Scenario 4 — HumanSide Wizard cross AOE")

    # Wizard at (9,5), aim left, center (6,5)
    _place(gs, "WizardHuman", 9, 5)
    _place(gs, "Soldier1Orc", 6, 5)   # center
    _place(gs, "Soldier2Skeleton", 5, 5)   # 1 left of center
    _place(gs, "Soldier3Skeleton", 7, 5)   # 1 right of center
    # (6,4) and (6,6) are empty/default-friendly-free after setup
    step("WizardHuman at (9,5); OrcSide soldiers at (5,5),(6,5),(7,5)")

    gs.current_phase = Phase.ATTACK
    wizard = gs.pieces["WizardHuman"]
    attacks = legal_attack_targets(wizard, gs)
    step(f"Wizard valid center(s): {attacks}")
    assert (6, 5) in attacks

    apply_wizard_attack("WizardHuman", (6, 5), gs)
    wizard_atk = gs.pieces["WizardHuman"].atk   # 2 after stats adjustment
    for pid in ("Soldier1Orc", "Soldier2Skeleton", "Soldier3Skeleton"):
        p = gs.pieces[pid]
        step(f"  {pid} HP: {p.hp}/{p.max_hp} (pos {p.pos})")
        expected = max(0, p.max_hp - wizard_atk)
        assert p.hp == expected or p.is_dead, \
            f"{pid} expected hp={expected}, got {p.hp}"
    ok(f"All 3 cross-AOE targets hit for {wizard_atk} damage each")


# ===========================================================================
# Scenario 5: Soldier nearby-ally attack bonus
# ===========================================================================

@scenario("Soldier nearby-ally ATK bonus")
def scenario_soldier_bonus():
    gs = build_default_state()
    section("Scenario 5 — Soldier gets +1 ATK from nearby ally")

    # Soldier at (5,4) — still on HumanSide's side. Place ally adjacent (5,5).
    soldier = gs.pieces["Soldier2Human"]   # default (6,4)
    _place(gs, "Soldier2Human", 5, 4)   # on river boundary

    # Place a friendly piece next to soldier to trigger bonus
    _place(gs, "Soldier1Human", 5, 5)   # adjacent → inside 3×3 of (5,4)
    step(f"Soldier2Human at (5,4), Soldier1Human at (5,5) — ally in 3×3 neighbourhood")

    # Place an enemy directly in front of soldier
    bp = gs.pieces["Soldier3Skeleton"]
    _place(gs, "Soldier3Skeleton", 4, 4)
    step(f"Soldier3Skeleton placed at (4,4) — directly ahead of soldier")

    gs.current_phase = Phase.ATTACK
    attacks = legal_attack_targets(soldier, gs)
    step(f"Soldier2Human attack targets: {attacks}")
    assert (4, 4) in attacks

    apply_attack("Soldier2Human", (4, 4), gs)
    # Soldier ATK=1, ally bonus +1 = 2 total, no palace reduction → damage=2
    step(f"Soldier3Skeleton HP after hit: {bp.hp}")
    assert bp.hp == 1, f"Expected 1, got {bp.hp}"   # 3 - 2 = 1
    ok("Soldier bonus applied: soldier dealt 2 damage (base 1 + ally +1)")


# ===========================================================================
# Scenario 6: Full round — HumanSide + OrcSide each complete a turn → round advances
# ===========================================================================

@scenario("Full round: both players take a turn")
def scenario_full_round():
    gs = build_default_state()
    section("Scenario 6 — Full round (HumanSide + OrcSide), event point spawning rule")

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

    # Round 1, HumanSide's turn: spawn occurs (odd round AND HumanSide's turn)
    assert gs.round_number == 1 and gs.active_faction is Faction.HumanSide
    assert should_spawn_event_point(gs), "Expected spawn on round 1 HumanSide's turn"
    take_minimal_turn("HUMANSIDE")
    assert len(gs.event_points) > 0 and all(ep.is_valid for ep in gs.event_points), \
        "Event point(s) should persist after HumanSide's turn"
    ok(f"Round 1 HumanSide: {len(gs.event_points)} event point(s) spawned and still valid")

    # Round 1, OrcSide's turn: NO spawn (same round, OrcSide's turn)
    assert gs.round_number == 1 and gs.active_faction is Faction.OrcSide
    assert not should_spawn_event_point(gs), \
        "Should NOT spawn again during OrcSide's turn in same round"
    take_minimal_turn("ORCSIDE")
    ok("Round 1 OrcSide: no new spawn, event point(s) persist through OrcSide's turn")

    # Round 2 starts: even round → no spawn; event points from round 1 still active
    assert gs.round_number == 2 and gs.active_faction is Faction.HumanSide
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
    soldier = gs.pieces["Soldier1Human"]   # (6,6)
    soldier.hp = 2
    step(f"Soldier1Human HP set to 2 (max={soldier.max_hp})")
    med_ep = EventPoint(EventPointType.MEDICAL, (6, 6), 1)
    gs.event_points = [med_ep]
    apply_event_trigger("Soldier1Human", med_ep, gs)
    assert soldier.hp == 3 and len(gs.event_points) == 0
    ok(f"MEDICAL: HP healed back to {soldier.hp}/{soldier.max_hp}")

    # TRAP kill: HP at 1, trap reduces to 0 → dead
    gs2 = build_default_state()
    soldier2 = gs2.pieces["Soldier1Human"]
    soldier2.hp = 1
    step("Soldier1Human HP set to 1 — will be killed by trap")
    trap_ep = EventPoint(EventPointType.TRAP, (6, 6), 1)
    gs2.event_points = [trap_ep]
    apply_event_trigger("Soldier1Human", trap_ep, gs2)
    assert soldier2.is_dead
    assert gs2.board.is_empty(6, 6)
    ok("TRAP: soldier killed (HP 1 → 0), removed from board")

    # AMMUNITION permanent buff stacks (each trigger now gives +2)
    gs3 = build_default_state()
    wizard = gs3.pieces["WizardHuman"]
    base_atk = wizard.atk   # 2 (after constants change)
    _place(gs3, "WizardHuman", 7, 6)
    for i in range(3):
        ammo_ep = EventPoint(EventPointType.AMMUNITION, (7, 6), i + 1)
        gs3.event_points = [ammo_ep]
        apply_event_trigger("WizardHuman", ammo_ep, gs3)
    expected_atk = base_atk + 3 * 2   # base + three +2 stacks
    assert wizard.atk == expected_atk, f"Expected {expected_atk}, got {wizard.atk}"
    ok(f"AMMUNITION stacks: wizard ATK = {wizard.atk} (base {base_atk} + 3×2 buffs)")


# ===========================================================================
# Scenario 8: Soldier movement — pre/post river
# ===========================================================================

@scenario("Soldier movement: pre/post river")
def scenario_soldier_movement():
    gs = build_default_state()
    section("Scenario 8 — Soldier pre/post river movement options")

    soldier = gs.pieces["Soldier2Human"]   # (6,4) — before river (x>4)
    step(f"Soldier at {soldier.pos} — before river")
    pre_moves = legal_moves(soldier, gs)
    assert pre_moves == [(5, 4)], f"Expected [(5,4)], got {pre_moves}"
    ok(f"Pre-river: only forward → {pre_moves}")

    # Move soldier to x=4 (crossed river).
    # Soldier2Skeleton sits at (3,4) in the default setup — move it out of the way
    # so we can test lateral movement without an accidental blocker ahead.
    _place(gs, "Soldier2Skeleton", 3, 0)
    _place(gs, "Soldier2Human", 4, 4)
    step(f"Soldier moved to {soldier.pos} — after river (x<=4 for HumanSide)")
    post_moves = legal_moves(soldier, gs)
    step(f"Post-river moves: {sorted(post_moves)}")
    assert (3, 4) in post_moves   # forward
    assert (4, 3) in post_moves   # down
    assert (4, 5) in post_moves   # up
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
