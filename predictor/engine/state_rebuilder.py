"""
Utilities that rebuild the current battle state from a Showdown-style log.

The real implementation is expected to leverage poke-env to roll the battle
forward.  For P1 we provide a lightweight log-driven snapshot so the rest of
the pipeline can be validated without the simulator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from predictor.core.models import (
    ActionCandidate,
    BattleState,
    PlayerState,
    PokemonBattleState,
)


@dataclass
class StateRebuilder:
    """Recreate a battle state from logs or a running simulator."""

    showdown_adapter: Any = None
    team_metadata: Dict[str, Dict[str, Any]] = None

    def rebuild(self, battle_log: Dict[str, Any], ev_estimates: Optional[Dict[str, Dict[str, Any]]] = None) -> BattleState:
        """
        Produce a BattleState snapshot.

        When a showdown adapter is configured we would spin up the simulator and
        replay turns.  That hook is left for P2 because it requires the actual
        Showdown process.  Until then we rely on rich logs.
        """

        if self.showdown_adapter:
            raise NotImplementedError(
                "Showdown replay integration not wired yet. "
                "Use log-driven rebuild for the P1 milestone."
            )
        return self._from_log(battle_log, ev_estimates or {})

    def _from_log(self, battle_log: Dict[str, Any], ev_estimates: Dict[str, Dict[str, Any]]) -> BattleState:
        state_payload = battle_log.get("state", {})
        player_a = self._extract_player_state(state_payload.get("A") or {}, "A")
        player_b = self._extract_player_state(state_payload.get("B") or {}, "B")
        turn = battle_log.get("currentTurn") or len(battle_log.get("turns", [])) + 1

        field = state_payload.get("field", {})
        legal_actions = self._extract_actions(battle_log.get("legalActions") or {})

        return BattleState(
            player_a=player_a,
            player_b=player_b,
            turn=turn,
            weather=field.get("weather"),
            terrain=field.get("terrain"),
            room=field.get("room"),
            raw_log=battle_log,
            legal_actions=legal_actions,
            ev_estimates=ev_estimates,
        )

    def _extract_player_state(self, payload: Dict[str, Any], player_label: str) -> PlayerState:
        name = payload.get("name") or payload.get("id") or "Unknown"
        active_payload = payload.get("active") or []
        active = []
        for idx, poke in enumerate(active_payload):
            metadata = (self.team_metadata or {}).get(player_label, {}).get(poke.get("name"))
            active.append(
                PokemonBattleState(
                    name=poke.get("name", f"Slot{idx+1}"),
                    hp_fraction=self._normalize_hp(poke.get("hp", 100)),
                    status=poke.get("status"),
                    boosts=poke.get("boosts") or {},
                    tera_type=poke.get("teraType"),
                    item=poke.get("item"),
                    moves=poke.get("moves") or [],
                    slot=idx,
                    nature=(metadata or {}).get("nature"),
                    ability=(metadata or {}).get("ability"),
                    species=(metadata or {}).get("species"),
                )
            )
        reserves = payload.get("reserves") or []
        return PlayerState(name=name, active=active, reserves=reserves)

    @staticmethod
    def _normalize_hp(value: Any) -> float:
        if isinstance(value, (int, float)):
            if value > 1:
                return max(0.0, min(1.0, value / 100.0))
            return max(0.0, min(1.0, float(value)))
        if isinstance(value, str) and value.endswith("%"):
            try:
                numeric = float(value.rstrip("%"))
                return max(0.0, min(1.0, numeric / 100.0))
            except ValueError:
                pass
        return 1.0

    def _extract_actions(
        self, legal_payload: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[ActionCandidate]]:
        formatted: Dict[str, List[ActionCandidate]] = {}
        for label, action_list in legal_payload.items():
            formatted[label] = []
            for raw in action_list:
                formatted[label].append(
                    ActionCandidate(
                        actor=raw.get("pokemon") or raw.get("actor") or f"{label}_slot{raw.get('slot', 0)}",
                        slot=raw.get("slot", 0),
                        move=raw.get("move", "Struggle"),
                        target=raw.get("target"),
                        priority=raw.get("priority", 0),
                        tags=raw.get("tags") or [],
                        metadata={
                            key: val
                            for key, val in raw.items()
                            if key
                            not in {"pokemon", "actor", "slot", "move", "target", "priority", "tags"}
                        },
                    )
                )
        return formatted
