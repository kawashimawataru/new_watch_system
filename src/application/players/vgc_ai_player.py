"""
VGC AI Player - VGCダブルバトル対応AIプレイヤー

人間がブラウザからチャレンジして対戦できるAIプレイヤー。
gen9vgc2025regf (VGC 2025 Regulation F) 対応。

使い方:
1. Showdownサーバー起動: cd pokemon-showdown && node pokemon-showdown start
2. python scripts/run_vgc_ai.py
3. ブラウザで localhost:8000 にアクセス
4. 自分のチームをインポート → AIにチャレンジ
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from poke_env.player import Player
from poke_env.battle import DoubleBattle
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration

from src.application.strategists.hybrid_strategist import HybridStrategist
from src.domain.models.battle_state import (
    BattleState,
    PlayerState,
    PokemonBattleState,
    ActionCandidate
)


class VGCAIPlayer(Player):
    """
    VGCダブルバトル対応AIプレイヤー
    
    - チャレンジを受け付けて対戦
    - HybridStrategist で行動選択
    - 2体同時の行動選択に対応
    
    strategy:
        - "heuristic": 最高威力技を選択（デフォルト）
        - "mcts": MCTSで最適行動を探索
    """

    def __init__(
        self,
        account_configuration=None,
        *,
        avatar: Optional[str] = None,
        battle_format: str = "gen9vgc2025regf",
        log_level: Optional[int] = None,
        max_concurrent_battles: int = 1,
        save_replays: bool = False,
        server_configuration=None,
        start_timer_on_battle_start: bool = False,
        start_listening: bool = True,
        team: Optional[str] = None,
        accept_open_team_sheet: bool = True,
        strategy: str = "heuristic",  # "heuristic" or "mcts"
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
            accept_open_team_sheet=accept_open_team_sheet,
        )
        self.move_count = 0
        self.strategy = strategy
        
        # HybridStrategistの初期化
        self.strategist = HybridStrategist(
            fast_model_path="models/fast_lane.pkl",
            mcts_rollouts=300,  # VGCでは応答速度重視
            mcts_max_turns=15
        )
        print(f"🎮 VGC AI Player 起動")
        print(f"   フォーマット: {battle_format}")
        print(f"   戦略: {strategy}")
        print(f"   チャレンジを待機中...")

    def _handle_message(self, message: str) -> None:
        """全メッセージをログ出力"""
        # チャレンジ関連のメッセージを強調表示
        if "challenge" in message.lower() or "|pm|" in message or "|updatechallenges|" in message:
            print(f"\n🔔 重要メッセージ: {message}")
        
        # 親クラスの処理を呼び出す
        super()._handle_message(message)

    def teampreview(self, battle: DoubleBattle):
        """
        チームプレビュー時の選出を決定する
        先頭4匹を選出（順番はそのまま）
        """
        print(f"\n{'='*60}")
        print(f"🎯 チームプレビュー")
        print(f"{'='*60}")
        
        # 先頭4匹を選出
        return "/team 1234"

    def choose_move(self, battle: DoubleBattle):
        """
        ダブルバトルの行動選択
        2体のポケモンの行動を同時に選択する
        """
        self.move_count += 1
        
        print(f"\n{'='*60}")
        print(f"ターン {battle.turn} - {self.username} の思考中... [{self.strategy}]")
        print(f"{'='*60}")
        
        # 現在のアクティブポケモンを表示
        for i, pokemon in enumerate(battle.active_pokemon):
            if pokemon:
                hp_pct = pokemon.current_hp_fraction * 100
                print(f"  [{i}] {pokemon.species}: HP {hp_pct:.0f}%")
        
        # 相手のポケモンを表示
        print("  相手:")
        for i, pokemon in enumerate(battle.opponent_active_pokemon):
            if pokemon:
                hp_pct = pokemon.current_hp_fraction * 100
                print(f"  [{i}] {pokemon.species}: HP {hp_pct:.0f}%")
        
        # BattleStateに変換して予測
        try:
            battle_state = self._convert_battle_to_state(battle)
            _, slow_result = self.strategist.predict_both(battle_state)
            
            print(f"\n🤖 勝率予測: {slow_result.p1_win_rate:.1%}")
            if slow_result.explanation:
                print(f"   {slow_result.explanation}")
        except Exception as e:
            print(f"⚠️ 予測エラー: {e}")
        
        # 戦略に基づいて行動選択
        if self.strategy == "mcts":
            orders = self._choose_mcts_action(battle)
        else:
            orders = self._choose_heuristic_action(battle)
        
        # BattleOrderのリストをjoinして返す
        if not orders:
            # デフォルトの行動を返す
            return self.choose_random_doubles_move(battle)
        
        return orders[0] if len(orders) == 1 else orders

    def _choose_mcts_action(self, battle: DoubleBattle):
        """
        MCTSで行動を選択（HybridStrategistを使用）
        """
        try:
            battle_state = self._convert_battle_to_state(battle)
            _, slow_result = self.strategist.predict_both(battle_state)
            
            # slow_resultから推奨アクションを抽出
            if slow_result.best_action:
                print(f"  🎯 MCTS推奨: {slow_result.best_action}")
                # best_actionは文字列で返ってくる（例: "move thunderbolt"）
                # ここでは利用可能な技からマッチするものを探す
                for i, pokemon in enumerate(battle.active_pokemon):
                    if pokemon is None or pokemon.fainted:
                        continue
                    
                    available_moves = battle.available_moves[i] if i < len(battle.available_moves) else []
                    for move in available_moves:
                        if move.id in slow_result.best_action.lower():
                            target = None
                            if move.target in ["normal", "any"]:
                                for j, opp in enumerate(battle.opponent_active_pokemon):
                                    if opp and not opp.fainted:
                                        target = j + 1
                                        break
                            return [self.create_order(move, move_target=target)]
        except Exception as e:
            print(f"  ⚠️ MCTSエラー: {e}")
        
        # MCTSが失敗した場合はヒューリスティックにフォールバック
        print("  ↩️ フォールバック: ヒューリスティック")
        return self._choose_heuristic_action(battle)

    def _choose_heuristic_action(self, battle: DoubleBattle):
        """
        ダブルバトル用のヒューリスティック行動選択
        BattleOrderのリストを返す
        """
        orders = []
        
        for i, pokemon in enumerate(battle.active_pokemon):
            if pokemon is None or pokemon.fainted:
                continue
            
            # 利用可能な技
            available_moves = battle.available_moves[i] if i < len(battle.available_moves) else []
            # 利用可能な交代先
            available_switches = battle.available_switches[i] if i < len(battle.available_switches) else []
            
            if available_moves:
                # 最も威力の高い技を選択
                best_move = max(
                    available_moves,
                    key=lambda m: m.base_power if m.base_power else 0
                )
                
                # ターゲット選択
                target = None
                if best_move.target in ["normal", "any"]:
                    # 相手を狙う
                    for j, opp in enumerate(battle.opponent_active_pokemon):
                        if opp and not opp.fainted:
                            target = j + 1  # 1=相手左, 2=相手右
                            break
                
                order = self.create_order(best_move, move_target=target)
                orders.append(order)
                print(f"  行動[{i}]: {best_move.id} -> target={target}")
                
            elif available_switches:
                # 技がない場合は交代
                switch_target = available_switches[0]
                order = self.create_order(switch_target)
                orders.append(order)
                print(f"  行動[{i}]: 交代 → {switch_target.species}")
        
        # 強制交代の場合
        if battle.force_switch:
            orders = []
            for i, force in enumerate(battle.force_switch):
                if force:
                    available_switches = battle.available_switches[i] if i < len(battle.available_switches) else []
                    if available_switches:
                        switch_target = available_switches[0]
                        order = self.create_order(switch_target)
                        orders.append(order)
                        print(f"  強制交代[{i}]: → {switch_target.species}")
                else:
                    # 交代不要な場合はpassだが、ダブルバトルでは片方だけ交代の場合がある
                    pass
        
        return orders

    def _convert_battle_to_state(self, battle: DoubleBattle) -> BattleState:
        """DoubleBattle -> BattleState 変換"""
        
        # Player A (自分)
        active_a = []
        for i, pokemon in enumerate(battle.active_pokemon):
            if pokemon:
                active_a.append(PokemonBattleState(
                    name=pokemon.species,
                    hp_fraction=pokemon.current_hp_fraction,
                    status=pokemon.status.name if pokemon.status else None,
                    species=pokemon.species,
                    slot=i,
                    moves=list(pokemon.moves.keys()) if pokemon.moves else [],
                    item=pokemon.item,
                    ability=pokemon.ability
                ))
        
        player_a = PlayerState(
            name=self.username,
            active=active_a,
            reserves=[p.species for p in battle.available_switches[0]] if battle.available_switches else []
        )
        
        # Player B (相手)
        active_b = []
        for i, pokemon in enumerate(battle.opponent_active_pokemon):
            if pokemon:
                active_b.append(PokemonBattleState(
                    name=pokemon.species,
                    hp_fraction=pokemon.current_hp_fraction,
                    status=pokemon.status.name if pokemon.status else None,
                    species=pokemon.species,
                    slot=i
                ))
        
        player_b = PlayerState(
            name=battle.opponent_username or "Opponent",
            active=active_b,
            reserves=[]
        )
        
        # Legal Actions
        candidates = []
        for i, moves in enumerate(battle.available_moves):
            for move in moves:
                candidates.append(ActionCandidate(
                    actor=battle.active_pokemon[i].species if battle.active_pokemon[i] else "Unknown",
                    slot=i,
                    move=move.id,
                    target=None
                ))
        
        return BattleState(
            player_a=player_a,
            player_b=player_b,
            turn=battle.turn,
            legal_actions={"A": candidates, "B": []}
        )

    def _battle_finished_callback(self, battle: DoubleBattle):
        """バトル終了時のコールバック"""
        print(f"\n{'='*60}")
        print(f"🏁 バトル終了: {battle.battle_tag}")
        print(f"{'='*60}")
        if battle.won:
            print(f"✓ {self.username} の勝利！")
        elif battle.lost:
            print(f"✗ {self.username} の敗北...")
        else:
            print("引き分け")
        print(f"ターン数: {battle.turn}")
        self.move_count = 0
