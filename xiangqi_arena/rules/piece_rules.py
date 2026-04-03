"""
Unified access point for piece-specific rules.

Design intent (Guide v2):
main flow should query legality/options through this module rather than spreading
piece-specific logic across many call sites.

Typical responsibilities:
- dispatch by piece type
- return legal movement options
- return legal attack options
"""

