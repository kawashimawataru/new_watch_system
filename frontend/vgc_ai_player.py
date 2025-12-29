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

from predictor.player.hybrid_strategist import HybridStrategist
from predictor.core.models import (
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
        slow_result = None
        try:
            battle_state = self._convert_battle_to_state(battle)
            _, slow_result = self.strategist.predict_both(battle_state)
            
            ai_win_rate = slow_result.p1_win_rate
            opponent_win_rate = 1.0 - ai_win_rate
            
            print(f"\n{'─'*40}")
            print(f"📊 ターン {battle.turn} 勝率予測")
            print(f"{'─'*40}")
            print(f"  🤖 AI (P1):     {ai_win_rate:>6.1%}  {'█' * int(ai_win_rate * 20)}")
            print(f"  👤 相手 (P2):   {opponent_win_rate:>6.1%}  {'█' * int(opponent_win_rate * 20)}")
            print(f"{'─'*40}")
            
            if slow_result.explanation:
                print(f"  💡 {slow_result.explanation}")
            
            # === 予測行動の表示 ===
            self._display_action_predictions(battle, slow_result.alternatives)
        except Exception as e:
            print(f"⚠️ 予測エラー: {e}")
        
        # 行動選択 - MCTSの結果を優先
        orders = None
        
        # MCTSの結果がある場合はそれを使う
        if slow_result and slow_result.alternatives:
            best_alt = max(slow_result.alternatives, key=lambda x: x.get("win_rate", 0))
            best_desc = best_alt.get("description", "")
            best_win_rate = best_alt.get("win_rate", 0)
            print(f"  🎯 MCTS推奨: {best_desc} (勝率: {best_win_rate:.1%})")
            orders = self._parse_action_description(battle, best_desc)
        elif slow_result and slow_result.best_action:
            print(f"  🎯 推奨: {slow_result.best_action}")
            orders = self._parse_action_description(battle, slow_result.best_action)
        
        # MCTSの結果がない場合はヒューリスティック
        if not orders:
            print("  ↩️ ヒューリスティックで行動選択")
            orders = self._choose_heuristic_action(battle)
        
        # BattleOrderを返す
        from poke_env.player.battle_order import DoubleBattleOrder
        
        # ordersが既にDoubleBattleOrderの場合はそのまま返す（強制交代時）
        if isinstance(orders, DoubleBattleOrder):
            return orders
        
        if not orders:
            # デフォルトの行動を返す
            return self.choose_random_doubles_move(battle)
        
        # ダブルバトルでは DoubleBattleOrder を使う
        first_order = orders[0] if len(orders) >= 1 else None
        second_order = orders[1] if len(orders) >= 2 else None
        
        return DoubleBattleOrder(first_order=first_order, second_order=second_order)

    def _choose_mcts_action(self, battle: DoubleBattle):
        """
        MCTSで行動を選択（HybridStrategistを使用）
        alternativesから最も勝率の高い行動を選択
        """
        try:
            battle_state = self._convert_battle_to_state(battle)
            _, slow_result = self.strategist.predict_both(battle_state)
            
            # alternativesから最も勝率の高い行動を探す
            if slow_result.alternatives:
                best_alt = max(slow_result.alternatives, key=lambda x: x.get("win_rate", 0))
                best_desc = best_alt.get("description", "")
                best_win_rate = best_alt.get("win_rate", 0)
                print(f"  🎯 MCTS推奨: {best_desc} (勝率: {best_win_rate:.1%})")
                
                # descriptionから各スロットの行動を抽出してBattleOrderを作成
                return self._parse_action_description(battle, best_desc)
            
            # best_actionがある場合はそれを使用
            if slow_result.best_action:
                print(f"  🎯 MCTS推奨: {slow_result.best_action}")
                return self._parse_action_description(battle, slow_result.best_action)
                
        except Exception as e:
            print(f"  ⚠️ MCTSエラー: {e}")
            import traceback
            traceback.print_exc()
        
        # MCTSが失敗した場合はヒューリスティックにフォールバック
        print("  ↩️ フォールバック: ヒューリスティック")
        return self._choose_heuristic_action(battle)
    
    def _parse_action_description(self, battle: DoubleBattle, description: str):
        """
        MCTSのdescriptionからBattleOrderを生成
        例: "thunderbolt (slot 0->1), protect (slot 1)"
        """
        orders = []
        description_lower = description.lower()
        
        for i, pokemon in enumerate(battle.active_pokemon):
            if pokemon is None or pokemon.fainted:
                continue
            
            available_moves = battle.available_moves[i] if i < len(battle.available_moves) else []
            
            # このスロットに対応する行動を探す
            best_move = None
            for move in available_moves:
                if move.id.lower() in description_lower:
                    best_move = move
                    break
            
            if best_move:
                # 単体技の場合はターゲットを指定 (MoveTarget enumを文字列化して比較)
                target_str = str(best_move.target).lower()
                needs_target = "normal" in target_str or "any" in target_str
                
                if needs_target:
                    # poke-envでは正の値が相手を指す: 1=相手左, 2=相手右
                    target = 1  # デフォルトは相手の1番目
                    for j, opp in enumerate(battle.opponent_active_pokemon):
                        if opp and not opp.fainted:
                            target = j + 1  # 1 or 2
                            break
                    orders.append(self.create_order(best_move, move_target=target))
                    print(f"  行動[{i}]: {best_move.id} -> 相手{target}")
                else:
                    # 全体技など、ターゲット不要
                    orders.append(self.create_order(best_move))
                    print(f"  行動[{i}]: {best_move.id}")
            elif available_moves:
                # マッチしなければ最高威力技を選択
                best_move = max(available_moves, key=lambda m: m.base_power if m.base_power else 0)
                target_str = str(best_move.target).lower()
                needs_target = "normal" in target_str or "any" in target_str
                
                if needs_target:
                    target = 1
                    for j, opp in enumerate(battle.opponent_active_pokemon):
                        if opp and not opp.fainted:
                            target = j + 1
                            break
                    orders.append(self.create_order(best_move, move_target=target))
                    print(f"  行動[{i}]: {best_move.id} -> 相手{target} (フォールバック)")
                else:
                    orders.append(self.create_order(best_move))
                    print(f"  行動[{i}]: {best_move.id} (フォールバック)")
        
        return orders if orders else None

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
                
                # ターゲット選択: poke-envでは正の値が相手を指す
                # 1 = 相手スロット1, 2 = 相手スロット2
                target_str = str(best_move.target).lower()
                needs_target = "normal" in target_str or "any" in target_str
                
                if needs_target:
                    # 相手を狙う (生きている相手の最初のスロット)
                    target = 1
                    for j, opp in enumerate(battle.opponent_active_pokemon):
                        if opp and not opp.fainted:
                            target = j + 1  # 1 or 2
                            break
                    order = self.create_order(best_move, move_target=target)
                    print(f"  行動[{i}]: {best_move.id} -> 相手{target}")
                else:
                    # 全体技等、ターゲット不要
                    order = self.create_order(best_move)
                    print(f"  行動[{i}]: {best_move.id}")
                orders.append(order)
                
            elif available_switches:
                # 技がない場合は交代
                switch_target = available_switches[0]
                order = self.create_order(switch_target)
                orders.append(order)
                print(f"  行動[{i}]: 交代 → {switch_target.species}")
        
        # 強制交代の場合
        if battle.force_switch:
            orders = []
            used_switches = set()  # 既に選択したポケモンを追跡
            
            # 両方のスロットについて順番に処理（順序が重要）
            for i, force in enumerate(battle.force_switch):
                if force:
                    available_switches = battle.available_switches[i] if i < len(battle.available_switches) else []
                    # まだ選択されていないポケモンを選ぶ
                    found = False
                    for sw in available_switches:
                        if sw.species not in used_switches:
                            switch_target = sw
                            used_switches.add(sw.species)
                            order = self.create_order(switch_target)
                            orders.append(order)
                            print(f"  強制交代[{i}]: → {switch_target.species}")
                            found = True
                            break
                    if not found and available_switches:
                        # 重複しても仕方なく選ぶ
                        order = self.create_order(available_switches[0])
                        orders.append(order)
                        print(f"  強制交代[{i}]: → {available_switches[0].species} (重複)")
                else:
                    # 交代不要な場合はpassを追加（順序維持のため）
                    # poke-envでは None を渡す
                    orders.append(None)
                    print(f"  強制交代[{i}]: pass (交代不要)")
            
            # Noneを含む場合はDoubleBattleOrderで返す
            from poke_env.player.battle_order import DoubleBattleOrder
            first_order = orders[0] if len(orders) >= 1 else None
            second_order = orders[1] if len(orders) >= 2 else None
            return DoubleBattleOrder(first_order=first_order, second_order=second_order)
        
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

    def _display_action_predictions(self, battle: DoubleBattle, alternatives: list):
        """
        ダブルバトル形式で各ポケモンの予測行動を表示
        - 技 + ターゲット（単体技の場合）
        - 交代先
        - 勝率
        """
        print(f"\n{'╔' + '═'*62 + '╗'}")
        print(f"{'║'} 🎯 行動予測 (ダブルバトル)                                   {'║'}")
        print(f"{'╠' + '═'*62 + '╣'}")
        
        # P1 (AI側) の行動予測
        print(f"{'║'} \033[1;34mP1 ({self.username})\033[0m                                            {'║'}")
        print(f"{'╟' + '─'*62 + '╢'}")
        
        # 自分の各ポケモンの行動予測を計算
        p1_predictions = self._analyze_action_probabilities_with_targets(battle, alternatives, is_p1=True)
        
        for pokemon_name, actions in p1_predictions.items():
            print(f"{'║'}   \033[1;33m{pokemon_name:<20}\033[0m                                   {'║'}")
            # 上位3つの行動を表示
            top_actions = sorted(actions.items(), key=lambda x: x[1], reverse=True)[:3]
            for action_desc, prob in top_actions:
                bar_len = int(prob * 20)
                bar = "█" * bar_len
                # 行動説明を22文字に制限
                action_short = action_desc[:22] if len(action_desc) > 22 else action_desc
                print(f"{'║'}     {action_short:<22} {prob:>5.0%}  {bar:<16} {'║'}")
        
        print(f"{'╟' + '─'*62 + '╢'}")
        
        # P2 (相手側) の予測行動
        print(f"{'║'} \033[1;31mP2 (相手)\033[0m                                                 {'║'}")
        print(f"{'╟' + '─'*62 + '╢'}")
        
        p2_predictions = self._predict_opponent_actions_with_targets(battle)
        
        for pokemon_name, actions in p2_predictions.items():
            print(f"{'║'}   \033[1;33m{pokemon_name:<20}\033[0m                                   {'║'}")
            top_actions = sorted(actions.items(), key=lambda x: x[1], reverse=True)[:3]
            for action_desc, prob in top_actions:
                bar_len = int(prob * 20)
                bar = "█" * bar_len
                action_short = action_desc[:22] if len(action_desc) > 22 else action_desc
                print(f"{'║'}     {action_short:<22} {prob:>5.0%}  {bar:<16} {'║'}")
        
        print(f"{'╚' + '═'*62 + '╝'}")
    
    def _analyze_action_probabilities(self, battle: DoubleBattle, alternatives: list, is_p1: bool) -> dict:
        """
        各ポケモンの行動確率を計算
        
        MCTSの結果を優先し、なければ威力ベースのヒューリスティックを使用
        
        Returns:
            {
                "Ogerpon": {"Ivy Cudgel": 0.6, "Follow Me": 0.3, "Protect": 0.1},
                "Flutter Mane": {"Moonblast": 0.7, "Icy Wind": 0.2, "Protect": 0.1}
            }
        """
        predictions = {}
        
        # 自分のアクティブポケモン
        active_pokemon = battle.active_pokemon if is_p1 else battle.opponent_active_pokemon
        available_moves_list = battle.available_moves if is_p1 else None
        
        for i, pokemon in enumerate(active_pokemon):
            if pokemon is None or pokemon.fainted:
                continue
            
            poke_name = pokemon.species.capitalize()
            predictions[poke_name] = {}
            
            # 利用可能な技を取得
            # 1. まずavailable_movesから取得を試みる
            # 2. なければポケモン自身の技リスト(pokemon.moves)を使用
            moves = []
            if available_moves_list and i < len(available_moves_list):
                moves = available_moves_list[i]
            
            # available_movesが空の場合はポケモンの既知技を使用
            if not moves and pokemon.moves:
                moves = list(pokemon.moves.values())
            
            if not moves:
                continue
            
            # まずMCTSのalternativesから確率を抽出
            move_probs = {}
            total_weight = 0
            
            for alt in alternatives:
                desc = alt.get("description", "")
                win_rate = alt.get("win_rate", 0)
                
                # descriptionからスロットiの行動を解析
                # alternativesにslot情報がない場合も技名でマッチ
                for move in moves:
                    move_id = move.id if hasattr(move, 'id') else str(move)
                    if move_id.lower() in desc.lower():
                        if move_id not in move_probs:
                            move_probs[move_id] = 0
                        move_probs[move_id] += win_rate
                        total_weight += win_rate
            
            # MCTSの結果がある場合
            if total_weight > 0:
                for move_id, weight in move_probs.items():
                    move_display = move_id.replace("_", " ").title()
                    predictions[poke_name][move_display] = weight / total_weight
            else:
                # MCTSの結果がない場合は威力ベースのヒューリスティック
                move_scores = {}
                total_score = 0
                
                for move in moves:
                    move_id = move.id if hasattr(move, 'id') else str(move)
                    # ベーススコア = 威力（なければ50）
                    base_power = move.base_power if hasattr(move, 'base_power') and move.base_power else 50
                    
                    # 技タイプによるボーナス/ペナルティ
                    score = base_power
                    
                    # Protectは低確率（10%程度）
                    if move_id in ["protect", "detect", "spikyshield", "silktrap", "obstruct", "banefulbunker"]:
                        score = 30
                    # 補助技は中程度
                    elif hasattr(move, 'category') and move.category.name == "STATUS":
                        score = 70
                    # 全体技は若干ボーナス
                    elif hasattr(move, 'target') and move.target in ["allAdjacentFoes", "allAdjacent"]:
                        score = int(base_power * 1.1)
                    
                    move_scores[move_id] = score
                    total_score += score
                
                # 正規化
                if total_score > 0:
                    for move_id, score in move_scores.items():
                        move_display = move_id.replace("_", " ").title()
                        predictions[poke_name][move_display] = score / total_score
        
        return predictions
    
    def _predict_opponent_actions(self, battle: DoubleBattle) -> dict:
        """
        相手のポケモンの予測行動
        - OTS (Open Team Sheet) データから技を取得
        - 既知の技からヒューリスティックに予測
        - 高威力技ほど使用確率が高い
        """
        predictions = {}
        
        for i, pokemon in enumerate(battle.opponent_active_pokemon):
            if pokemon is None or pokemon.fainted:
                continue
            
            poke_name = pokemon.species.capitalize()
            predictions[poke_name] = {}
            
            # まず既知の技をチェック
            known_moves = list(pokemon.moves.keys()) if pokemon.moves else []
            
            # OTSから技を取得（Bo3フォーマットでは相手の技が見える）
            # opponent_teamからマッチするポケモンを探す
            ots_moves = []
            if hasattr(battle, 'opponent_team') and battle.opponent_team:
                for team_pokemon in battle.opponent_team.values():
                    if team_pokemon and team_pokemon.species == pokemon.species:
                        if team_pokemon.moves:
                            ots_moves = list(team_pokemon.moves.keys())
                        break
            
            # OTSがあればそれを使用、なければ既知の技
            all_moves = ots_moves if ots_moves else known_moves
            
            if not all_moves:
                # 技が不明の場合は「???」
                predictions[poke_name]["???"] = 1.0
                continue
            
            # 威力ベースで確率を推定
            total_power = 0
            move_powers = {}
            
            for move_id in all_moves:
                move = pokemon.moves.get(move_id)
                if move:
                    power = move.base_power if move.base_power else 50
                else:
                    power = 50  # 未知の技はデフォルト50
                move_powers[move_id] = power
                total_power += power
            
            # 正規化
            if total_power > 0:
                for move_id, power in move_powers.items():
                    move_display = move_id.replace("_", " ").title()
                    predictions[poke_name][move_display] = power / total_power
        
        return predictions
    
    def _analyze_action_probabilities_with_targets(self, battle: DoubleBattle, alternatives: list, is_p1: bool) -> dict:
        """
        各ポケモンの行動確率を計算（ターゲット・交代込み）
        
        Returns:
            {
                "Tornadus": {
                    "Tailwind": 0.3,
                    "Bleakwindstorm → 相手全体": 0.25,
                    "交代 → Ragingbolt": 0.15,
                    ...
                }
            }
        """
        predictions = {}
        
        # 自分のアクティブポケモン
        active_pokemon = battle.active_pokemon if is_p1 else battle.opponent_active_pokemon
        
        for i, pokemon in enumerate(active_pokemon):
            if pokemon is None or pokemon.fainted:
                continue
            
            poke_name = pokemon.species.capitalize()
            predictions[poke_name] = {}
            action_scores = {}
            
            # 利用可能な技を取得
            available_moves = []
            if is_p1 and i < len(battle.available_moves):
                available_moves = battle.available_moves[i]
            
            # ポケモンの既知技も使用
            if not available_moves and pokemon.moves:
                available_moves = list(pokemon.moves.values())
            
            # 相手のポケモン名を取得
            opponent_names = []
            for opp in battle.opponent_active_pokemon:
                if opp and not opp.fainted:
                    opponent_names.append(opp.species.capitalize())
            
            # 技ごとにスコアを計算
            for move in available_moves:
                move_id = move.id if hasattr(move, 'id') else str(move)
                base_power = move.base_power if hasattr(move, 'base_power') and move.base_power else 50
                target_type = str(move.target) if hasattr(move, 'target') else "normal"
                
                # ターゲットタイプに応じて行動を追加
                is_spread_move = "allAdjacentFoes" in target_type or "allAdjacent" in target_type or "ALL" in target_type.upper()
                is_single_target = "normal" in target_type.lower() or "any" in target_type.lower() or "NORMAL" in target_type
                is_self_move = "self" in target_type.lower() or "allySide" in target_type or "SELF" in target_type.upper()
                
                if is_spread_move:
                    # 全体技
                    action_name = f"{move_id.title()}"
                    action_scores[action_name] = base_power * 1.1
                elif is_single_target and opponent_names:
                    # 単体技 - 各ターゲットごとに実際のポケモン名で表示
                    for opp_name in opponent_names:
                        action_name = f"{move_id.title()} → {opp_name}"
                        action_scores[action_name] = base_power
                elif is_self_move:
                    # 自分対象・味方全体
                    action_name = f"{move_id.title()}"
                    # Protectなどは低スコア
                    if move_id in ["protect", "detect", "spikyshield"]:
                        action_scores[action_name] = 30
                    else:
                        action_scores[action_name] = 70
                else:
                    action_name = f"{move_id.title()}"
                    action_scores[action_name] = base_power
            
            # 交代選択肢を追加
            if is_p1 and i < len(battle.available_switches):
                for switch in battle.available_switches[i]:
                    if switch and not switch.fainted:
                        action_name = f"交代 → {switch.species.capitalize()}"
                        # 交代は控えめなスコア
                        action_scores[action_name] = 40
            
            # 正規化
            total_score = sum(action_scores.values())
            if total_score > 0:
                for action, score in action_scores.items():
                    predictions[poke_name][action] = score / total_score
        
        return predictions
    
    def _predict_opponent_actions_with_targets(self, battle: DoubleBattle) -> dict:
        """
        相手のポケモンの予測行動（ターゲット込み）
        """
        predictions = {}
        
        # 味方のポケモン名を取得
        ally_names = []
        for ally in battle.active_pokemon:
            if ally and not ally.fainted:
                ally_names.append(ally.species.capitalize())
        
        for i, pokemon in enumerate(battle.opponent_active_pokemon):
            if pokemon is None or pokemon.fainted:
                continue
            
            poke_name = pokemon.species.capitalize()
            predictions[poke_name] = {}
            action_scores = {}
            
            # 既知の技
            known_moves = list(pokemon.moves.values()) if pokemon.moves else []
            
            # OTSから技を取得
            if hasattr(battle, 'opponent_team') and battle.opponent_team:
                for team_pokemon in battle.opponent_team.values():
                    if team_pokemon and team_pokemon.species == pokemon.species:
                        if team_pokemon.moves:
                            known_moves = list(team_pokemon.moves.values())
                        break
            
            if not known_moves:
                predictions[poke_name]["???"] = 1.0
                continue
            
            # 技ごとにスコアを計算
            for move in known_moves:
                move_id = move.id if hasattr(move, 'id') else str(move)
                base_power = move.base_power if hasattr(move, 'base_power') and move.base_power else 50
                target_type = str(move.target) if hasattr(move, 'target') else "normal"
                
                is_spread_move = "allAdjacentFoes" in target_type or "allAdjacent" in target_type or "ALL" in target_type.upper()
                is_single_target = "normal" in target_type.lower() or "any" in target_type.lower() or "NORMAL" in target_type
                is_self_move = "self" in target_type.lower() or "allySide" in target_type or "SELF" in target_type.upper()
                
                if is_spread_move:
                    action_name = f"{move_id.title()}"
                    action_scores[action_name] = base_power * 1.1
                elif is_single_target and ally_names:
                    # 相手の単体攻撃技はこちらを狙う - ポケモン名で表示
                    for ally_name in ally_names:
                        action_name = f"{move_id.title()} → {ally_name}"
                        action_scores[action_name] = base_power
                elif is_self_move:
                    action_name = f"{move_id.title()}"
                    if move_id in ["protect", "detect"]:
                        action_scores[action_name] = 30
                    else:
                        action_scores[action_name] = 70
                else:
                    action_name = f"{move_id.title()}"
                    action_scores[action_name] = base_power
            
            # 正規化
            total_score = sum(action_scores.values())
            if total_score > 0:
                for action, score in action_scores.items():
                    predictions[poke_name][action] = score / total_score
        
        return predictions
