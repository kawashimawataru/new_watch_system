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


from predictor.player.hybrid_strategist import HybridStrategist
from predictor.core.models import (
    BattleState,
    PlayerState,
    PokemonBattleState,
    ActionCandidate
)

try:
    from poke_env.player import Player
    from poke_env.battle import Battle, Move, Pokemon, SideCondition
    from poke_env.ps_client.server_configuration import LocalhostServerConfiguration

    POKE_ENV_AVAILABLE = True
except ImportError:
    POKE_ENV_AVAILABLE = False
    print("警告: poke-env がインストールされていません")
    import traceback
    traceback.print_exc()
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
        
        # HybridStrategistの初期化
        # モデルパスは適宜調整。存在しない場合はFast-Laneはロードされないが、MCTSは動作する。
        self.strategist = HybridStrategist(
            fast_model_path="models/fast_lane.pkl",
            mcts_rollouts=500,  # 応答速度重視で少し減らす
            mcts_max_turns=20
        )

    def choose_move(self, battle: Battle):
        """
        バトル状態を分析してAIが次の手を選択。
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
        
        # BattleStateに変換
        battle_state = self._convert_battle_to_state(battle)
        
        # HybridStrategistで予測 (同期実行)
        # predict_bothを使うことで、MCTSの結果(説明付き)を取得できる
        _, slow_result = self.strategist.predict_both(battle_state)
        
        # 説明を表示
        print("\n🤖 AIの思考:")
        if slow_result.explanation:
            print(f"  結論: {slow_result.explanation}")
        
        if slow_result.alternatives:
            print("  検討した選択肢:")
            for alt in slow_result.alternatives:
                print(f"    - {alt.get('description', 'Unknown')}: 勝率 {alt.get('win_rate', 0.0):.1%}")

        # 推奨行動を実行
        recommended = slow_result.recommended_action
        if recommended:
            # ActionCandidate を poke-env の Order に変換
            # VGC (ダブル) の場合、recommended は TurnAction (2体分) の可能性があるが、
            # HybridStrategist の戻り値は ActionCandidate (1体分) の場合と TurnAction の場合がある。
            # 今回の改修で MonteCarloStrategist は TurnAction を返すが、
            # HybridStrategist._select_quick_action は ActionCandidate を返す。
            # predict_precise (MCTS) は TurnAction を返す。
            
            # TurnAction (MCTS result) の場合
            if hasattr(recommended, "player_a_actions"):
                # 自分の行動 (player_a) を取得
                # poke-env の choose_move は「次の1手」を返す必要がある。
                # ダブルバトルの場合、poke-env はどう扱う？
                # Gen9 Random Battle はシングルなので、1体分で良いはず。
                # しかし VGC はダブル。
                # ここではフォーマットが gen9randombattle (シングル) なので、
                # TurnAction の最初の行動を採用する。
                
                action = recommended.player_a_actions[0]
                if action.type == "move":
                    # 技を探す
                    for move in battle.available_moves:
                        if move.id == action.move_name or move.entry_name == action.move_name: # IDマッチングは要調整
                            # target 変換
                            return self.create_order(move)
                    # 名前で一致しなければindexで... (危険だが)
                    # 簡易実装: 利用可能な技の中で一番近いもの、あるいはランダム
                    pass
                elif action.type == "switch":
                    for pokemon in battle.available_switches:
                        if pokemon.species == action.switch_to:
                            return self.create_order(pokemon)
            
            # ActionCandidate の場合 (Fast-Lane fallback)
            elif isinstance(recommended, ActionCandidate):
                # ...
                pass

        # フォールバック: ヒューリスティック
        print("⚠️ 推奨行動を実行できませんでした。ヒューリスティックを使用します。")
        return self._choose_action_heuristic(battle)

    def _convert_battle_to_state(self, battle: Battle) -> BattleState:
        """poke-env Battle -> BattleState 変換"""
        
        # Player A (自分)
        player_a = PlayerState(
            name=self.username,
            active=[self._convert_pokemon(battle.active_pokemon, slot=0)], # シングル想定
            reserves=[p.species for p in battle.available_switches]
        )
        
        # Player B (相手)
        player_b = PlayerState(
            name=battle.opponent_username or "Opponent",
            active=[self._convert_pokemon(battle.opponent_active_pokemon, slot=0)],
            reserves=[p.species for p in battle.opponent_team.values() if not p.active] # 情報不完全
        )
        
        # Legal Actions
        # poke-env の available_moves / switches を ActionCandidate に変換
        candidates = []
        for move in battle.available_moves:
            candidates.append(ActionCandidate(
                actor=battle.active_pokemon.species,
                slot=0,
                move=move.id,
                target=None # シングルならNone
            ))
        for pokemon in battle.available_switches:
            candidates.append(ActionCandidate(
                actor=battle.active_pokemon.species,
                slot=0,
                move="switch", # 便宜上
                target=None,
                metadata={"switch_to": pokemon.species}
            ))
            
        legal_actions = {"A": candidates, "B": []} # 相手の行動は不明
        
        return BattleState(
            player_a=player_a,
            player_b=player_b,
            turn=battle.turn,
            legal_actions=legal_actions
        )

    def _convert_pokemon(self, pokemon: Optional[Pokemon], slot: int) -> PokemonBattleState:
        if not pokemon:
            return PokemonBattleState(name="Empty", hp_fraction=0.0)
            
        return PokemonBattleState(
            name=pokemon.species,
            hp_fraction=pokemon.current_hp_fraction,
            status=pokemon.status.name if pokemon.status else None,
            species=pokemon.species,
            slot=slot,
            moves=list(pokemon.moves.keys()),
            item=pokemon.item,
            ability=pokemon.ability
        )


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
            account_configuration=None, # Localhost usually doesn't need auth, but username is set via player_configuration or similar?
            # poke-env doesn't allow setting username easily in constructor without account config for registered servers.
            # For localhost, it might just use what's provided or random.
            # Let's try to set it via a custom method or just rely on the fact that we can print the username.
            battle_format="gen9randombattle",
            server_configuration=LocalhostServerConfiguration,
            max_concurrent_battles=1,
        )
        # Hack to set username if possible, or just print it
        # Actually, let's just print the username after login and use that for spectator.
        
        # ランダムな対戦相手を作成
        opponent = RandomOpponent(
            battle_format="gen9randombattle",
            server_configuration=LocalhostServerConfiguration,
            max_concurrent_battles=1,
        )

        # 対戦を実行（10試合）
        await ai_player.battle_against(opponent, n_battles=10)

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
