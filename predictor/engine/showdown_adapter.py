"""
Thin wrapper around poke-env that hides networking details from the evaluator.

The real connection to a locally running Pokémon Showdown server lives in this
module so the rest of the codebase can be unit tested without needing the
simulator.  For the P1 milestone only the interface skeleton is provided.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ShowdownAdapterConfig:
    server_host: str = "localhost"
    server_port: int = 8000
    format_id: str = "gen9vgc2024regg"
    use_ssl: bool = False


class ShowdownAdapter:
    """Bridge between local poke-env agents and the running Showdown server."""

    def __init__(self, config: Optional[ShowdownAdapterConfig] = None):
        self.config = config or ShowdownAdapterConfig()
        self.client = None

    def connect(self) -> None:
        """
        Lazily initialize the poke-env client.

        poke-env expects a Showdown server to be running locally.  That setup is
        environment-specific, so we defer the actual import to runtime to avoid
        forcing the dependency during unit tests.
        """

        if self.client:
            return
        try:
            from poke_env.player_configuration import PlayerConfiguration
            from poke_env.server_configuration import ShowdownServerConfiguration
            from poke_env.player import Player
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "poke-env is required to use the Showdown adapter. "
                "Install it via `pip install poke-env`."
            ) from exc

        server_config = ShowdownServerConfiguration(
            self.config.server_host,
            self.config.server_port,
            is_secure=self.config.use_ssl,
        )
        player_config = PlayerConfiguration("predictor-bot", None)

        class _AdapterPlayer(Player):  # pylint: disable=too-few-public-methods
            pass

        self.client = _AdapterPlayer(player_configuration=player_config, server_configuration=server_config)

    def create_battle(self, team_a: str, team_b: str) -> Any:
        """Spin up a private battle using the provided teams."""

        if not self.client:
            self.connect()
        # poke-env currently instantiates battles asynchronously.  The full
        # wiring requires hooking into the player ladder or challenge APIs,
        # which is outside the scope of the scaffold.
        raise NotImplementedError("Battle creation will be implemented in P2.")

    def fast_forward(self, battle: Any, battle_log: Dict[str, Any]) -> Any:
        """Replay a battle log on top of an initialized poke-env battle."""

        raise NotImplementedError("fast_forward requires poke-env battle plumbing.")
