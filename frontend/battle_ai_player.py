"""
Pokemon Showdown サーバーに接続してリアルタイムで対戦するAIプレイヤー。

このスクリプトは：
1. ローカルShowdownサーバーに接続
2. バトルをリアルタイムで監視
3. predictor.evaluate_position を使ってAIが次の手を決定
4. 実際に行動を選択して対戦を進行

使い方:
1. Showdownサーバーを起動: cd pokemon-showdown && node pokemon-showdown start
2. このスクリプトを実行: python -m frontend.battle_ai_player
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

try:
    from poke_env.player import Player
    from poke_env.environment.battle import Battle
    from poke_env.environment.move import Move
    from poke_env.environment.pokemon import Pokemon
    from poke_env.server_configuration import LocalhostServerConfiguration

    POKE_ENV_AVAILABLE = True
except ImportError:
    POKE_ENV_AVAILABLE = False
    print("警告: poke-env がインストールされていません")
    print("インストール: pip install poke-env")


class AIPlayer(Player):
    """
    predictor.evaluate_position を使用してAIで対戦するプレイヤー。
    """

    def __init__(
        self,
        account_configuration=None,
        *,
        avatar: Optional[str] = None,
        battle_format: str = "gen9randombattle",
        log_level: Optional[int] = None,
        max_concurrent_battles: int = 1,
        save_replays: bool = False,
        server_configuration=None,
        start_timer_on_battle_start: bool = False,
        start_listening: bool = True,
        team: Optional[str] = None,
    ):
        super().__init__(
            account_configuration=account_configuration,
            avatar=avatar,
            battle_format=battle_format,
            log_level=log_level,
            max_concurrent_battles=max_concurrent_battles,
            save_replays=save_replays,
            server_configuration=server_configuration,
            start_timer_on_battle_start=start_timer_on_battle_start,
            start_listening=start_listening,
            team=team,
        )
        self.move_count = 0

    def choose_move(self, battle: Battle):
        """
        バトル状態を分析してAIが次の手を選択。
        
        ここで predictor.evaluate_position を呼び出し、
        推奨される行動を取得します。
        """
        self.move_count += 1

        # デバッグ情報を表示
        print(f"\n{'='*60}")
        print(f"ターン {battle.turn} - {self.username} のターン")
        print(f"{'='*60}")

        # 現在の状態を表示
        active = battle.active_pokemon
        if active:
            print(f"\nアクティブ: {active.species} (HP: {active.current_hp}/{active.max_hp})")
            print(f"状態: {active.status if active.status else '正常'}")

        # 利用可能な行動を表示
        print("\n利用可能な行動:")
        available_moves = battle.available_moves
        available_switches = battle.available_switches

        for i, move in enumerate(available_moves):
            print(f"  {i+1}. {move.id} (威力: {move.base_power}, PP: {move.current_pp}/{move.max_pp})")

        for i, pokemon in enumerate(available_switches):
            print(f"  S{i+1}. 交代 → {pokemon.species} (HP: {pokemon.current_hp}/{pokemon.max_hp})")

        # TODO: ここで predictor.evaluate_position を呼び出す
        # 現状は簡易的なヒューリスティックで行動を選択
        chosen_action = self._choose_action_heuristic(battle)

        print(f"\n選択した行動: {chosen_action}")

        return chosen_action

    def _choose_action_heuristic(self, battle: Battle):
        """
        簡易的なヒューリスティックで行動を選択。
        
        TODO: これを predictor.evaluate_position の結果で置き換える
        """
        # 利用可能な技があれば、最も威力の高い技を選択
        if battle.available_moves:
            # 威力でソート
            best_move = max(
                battle.available_moves,
                key=lambda move: move.base_power if move.base_power else 0,
            )
            return self.create_order(best_move)

        # 技が使えない場合は交代
        if battle.available_switches:
            return self.create_order(battle.available_switches[0])

        # どちらもない場合はランダム（通常は発生しない）
        return self.choose_random_move(battle)

    def _battle_finished_callback(self, battle: Battle):
        """バトル終了時のコールバック"""
        print(f"\n{'='*60}")
        print(f"バトル終了: {battle.battle_tag}")
        print(f"{'='*60}")
        if battle.won:
            print(f"✓ {self.username} の勝利！")
        else:
            print(f"✗ {self.username} の敗北...")
        print(f"ターン数: {battle.turn}")
        print(f"行動回数: {self.move_count}")
        self.move_count = 0


class RandomOpponent(Player):
    """対戦相手（ランダム行動）"""

    def choose_move(self, battle: Battle):
        return self.choose_random_move(battle)


async def main():
    """メイン関数: AIプレイヤーとランダムプレイヤーで対戦"""

    if not POKE_ENV_AVAILABLE:
        print("エラー: poke-env がインストールされていません")
        return 1

    print("Pokemon Showdown AI プレイヤー")
    print("="*60)
    print("\n設定:")
    print("  - サーバー: localhost:8000 (ローカル)")
    print("  - フォーマット: gen9randombattle")
    print("  - 対戦数: 1")
    print("\nShowdownサーバーが起動していることを確認してください")
    print("起動コマンド: cd pokemon-showdown && node pokemon-showdown start")
    print("\n対戦を開始します...\n")

    try:
        # AIプレイヤーを作成
        ai_player = AIPlayer(
            battle_format="gen9randombattle",
            server_configuration=LocalhostServerConfiguration,
            max_concurrent_battles=1,
        )

        # ランダムな対戦相手を作成
        opponent = RandomOpponent(
            battle_format="gen9randombattle",
            server_configuration=LocalhostServerConfiguration,
            max_concurrent_battles=1,
        )

        # 対戦を実行（1試合）
        await ai_player.battle_against(opponent, n_battles=1)

        # 結果を表示
        print("\n" + "="*60)
        print("対戦結果サマリー")
        print("="*60)
        print(f"AIプレイヤー: {ai_player.n_won_battles}勝 / {ai_player.n_finished_battles}戦")
        print(f"対戦相手: {opponent.n_won_battles}勝 / {opponent.n_finished_battles}戦")

        if ai_player.n_finished_battles > 0:
            win_rate = ai_player.n_won_battles / ai_player.n_finished_battles * 100
            print(f"勝率: {win_rate:.1f}%")

    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        print("\n考えられる原因:")
        print("1. Showdownサーバーが起動していない")
        print("   → cd pokemon-showdown && node pokemon-showdown start")
        print("2. ポート8000が使用できない")
        print("3. ネットワーク接続の問題")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
