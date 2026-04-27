# hybrid-AR-board-game-frontend

A hybrid vision-based board game inspired by Chinese chess.

## About the Project

Xiangqi Arena is a two-player board game that combines a real Chinese chess board, physical pieces with markers, and a digital rule system.

Players move real pieces on the board, and an overhead camera tracks their positions. The system then updates the digital board state, checks whether actions are valid, resolves attacks and event effects, and decides when the game ends.

The idea behind the project is simple: keep the physical and social experience of a tabletop game, but let the computer handle the parts that are usually slow or easy to get wrong, such as tracking positions, managing HP, and applying special rules.

## Why We Made It

In many physical board games, players have to manage rules and game state by themselves. That works for simple games, but it becomes inconvenient when the game includes more complex combat, temporary effects, or position-based mechanics.

This project explores a different approach. By using marker recognition and a digital game model, the system can understand where pieces are, how they relate to each other on the board, and what should happen next. This makes the gameplay more dynamic while still keeping the real board as the main way to play.

## The Game

Xiangqi Arena is based on the structure of Chinese chess, but it is not a traditional Xiangqi game.

It keeps the board layout, sides, river, palace, and piece identities, but changes the gameplay into a tactical combat system with HP, ATK, event points, and digital rule resolution.

There are two players:
- HumanSide
- OrcSide

Each side has 7 pieces:
- HumanSide: GeneralHuman, ArcherHuman, LancerHuman, WizardHuman, Soldier1Human, Soldier2Human, Soldier3Human
- OrcSide: GeneralOrc, ArcherSkeleton, RiderOrc, Slime Orc, Soldier1Orc, Soldier2Skeleton, Soldier3Skeleton

The goal is to defeat the opposing GeneralHuman or GeneralOrc by reducing its HP to 0 or below. Once that happens, the game ends immediately.

## How It Works

A normal turn works like this:
1. The current player is shown on screen.
2. The player moves one piece on the physical board, or skips movement.
3. The system scans the board and updates the digital state.
4. If needed, the system checks movement legality and resolves event effects.
5. The player chooses whether to attack.
6. The system resolves damage, death, and victory conditions.
7. The turn ends and switches to the other player.

So even though the interaction starts from the physical board, the game flow is supported by the digital system all the way through.

## Board Rules

The game uses the intersections of the Chinese chess board as valid positions, not the square cells.

- Board size: 10 × 9
- OrcSide starts from x = 0
- HumanSide starts from x = 9
- The river lies between x = 4 and x = 5
- GeneralHuman and GeneralOrc can only stay inside their own palaces

Some mechanics also depend on spatial relationships such as adjacency, local neighborhood, and board zones. These are important for things like palace protection, soldier movement after crossing the river, and soldier attack bonuses when allies are nearby.

## Piece Attributes

| Piece | HP | Max HP | ATK |
| --- | --- | --- | --- |
| GeneralHuman / GeneralOrc | 6 | 6 | 1 |
| ArcherHuman / ArcherSkeleton | 5 | 5 | 2 |
| LancerHuman / RiderOrc | 4 | 4 | 3 |
| WizardHuman / Slime Orc | 5 | 5 | 2 |
| Soldier roles | 3 | 3 | 1 |

Healing cannot go above max HP, and attack buffs can stack.

## Special Mechanics

### Digital Combat

This game does not use traditional Xiangqi capture rules. Pieces do not defeat enemies by moving onto them. Instead, combat is handled by the digital system after movement and attack selection.

### Wizard Attack

The Wizard has a special attack pattern. It attacks a target exactly three nodes away in one orthogonal direction, and the attack affects a cross-shaped area around that target.

### Soldier Bonus

A Soldier can gain a temporary attack bonus if another friendly piece is nearby in its local 3×3 neighborhood before attacking.

### Event Points

The system can generate temporary event points on empty nodes:
- Ammunition Point: permanent ATK +1
- Medical Point: HP +1
- Trap Point: HP -1

These points exist only in the digital interface and activate when a piece steps onto them.

## System Responsibilities

The digital system is responsible for:
- tracking the current player
- maintaining the board state
- updating piece states
- generating and removing event points
- showing attack prompts
- resolving damage, healing, and death
- checking victory conditions

## Project Structure

The project is organized into separate modules so that the game logic, recognition, state management, input, and UI do not get mixed together.

Main parts of the project include:
- `core/`
- `models/`
- `state/`
- `rules/`
- `flow/`
- `modification/`
- `recognition/`
- `input_control/`
- `ui/`

This structure helps keep the project easier to build and maintain, especially when different team members are working on different parts.

## In Short

Xiangqi Arena is a hybrid board game project that uses computer vision and digital rule handling to extend the tabletop experience. It keeps the physical board game feeling, while using the system to manage state, rules, and interaction more smoothly.