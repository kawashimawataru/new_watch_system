"""Shared dataclasses used across the predictor package."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

StatDict = Dict[str, int]


@dataclass
class PokemonBattleState:
    """Minimal information we need for each active Pokémon."""

    name: str
    hp_fraction: float = 1.0
    status: Optional[str] = None
    boosts: Dict[str, int] = field(default_factory=dict)
    tera_type: Optional[str] = None
    item: Optional[str] = None
    moves: Sequence[str] = field(default_factory=list)
    is_active: bool = True
    slot: int = 0
    nature: Optional[str] = None
    ability: Optional[str] = None
    species: Optional[str] = None


@dataclass
class ActionCandidate:
    """Represents a single move or switch option a Pokémon can take."""

    actor: str
    slot: int
    move: str
    target: Optional[str] = None
    priority: int = 0
    tags: Sequence[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlayerState:
    """Battle snapshot for one side."""

    name: str
    active: List[PokemonBattleState]
    reserves: List[str] = field(default_factory=list)
    score_bias: float = 0.0


@dataclass
class BattleState:
    """Current battle snapshot derived from logs or the simulator."""

    player_a: PlayerState
    player_b: PlayerState
    turn: int
    weather: Optional[str] = None
    terrain: Optional[str] = None
    room: Optional[str] = None
    raw_log: Dict[str, Any] = field(default_factory=dict)
    legal_actions: Dict[str, List[ActionCandidate]] = field(default_factory=dict)
    ev_estimates: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ActionScore:
    """Normalized score per action."""

    move: str
    target: Optional[str]
    score: float


@dataclass
class PokemonRecommendation:
    """Recommendation for one Pokémon."""

    name: str
    suggested_moves: List[ActionScore]


@dataclass
class PlayerEvaluation:
    """Final view for each player."""

    win_rate: float
    active: List[PokemonRecommendation]


@dataclass
class EvaluationResult:
    """High-level return object for evaluate_position."""

    player_a: PlayerEvaluation
    player_b: PlayerEvaluation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to the response schema expected by downstream consumers."""

        def serialize_player(label: str, player: PlayerEvaluation) -> Dict[str, Any]:
            return {
                label: {
                    "winRate": player.win_rate,
                    "active": [
                        {
                            "name": rec.name,
                            "suggestedMoves": [
                                {
                                    "move": action.move,
                                    "target": action.target,
                                    "score": action.score,
                                }
                                for action in rec.suggested_moves
                            ],
                        }
                        for rec in player.active
                    ],
                }
            }

        payload: Dict[str, Any] = {}
        payload.update(serialize_player("playerA", self.player_a))
        payload.update(serialize_player("playerB", self.player_b))
        return payload
