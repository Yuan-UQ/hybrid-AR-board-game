from dataclasses import dataclass


@dataclass(slots=True)
class GameConfig:
    random_seed: int = 7
