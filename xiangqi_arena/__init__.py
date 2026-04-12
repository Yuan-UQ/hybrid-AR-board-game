"""
Xiangqi Arena (MVP scaffold).

This package follows a layered architecture:
- state/: single source of truth (GameState)
- rules/: validation & calculation only (no state mutation)
- modification/: apply confirmed changes into GameState
- flow/: round/turn/phase progression
- ui/: presentation only
- input_control/: input interpretation only
- recognition/: external recognition integration
"""

__all__ = [
    "__version__",
]

__version__ = "0.1.0"

