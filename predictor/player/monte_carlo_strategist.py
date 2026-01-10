"""
Monte Carlo Strategist: MCTS-based Win Rate Predictor

現在の盤面から複数回のランダムシミュレーション(rollouts)を実行し、
最も勝率の高い行動を特定する。データ0件で動作可能。

使用方法:
    from predictor.player.monte_carlo_strategist import MonteCarloStrategist
    
    strategist = MonteCarloStrategist(n_rollouts=1000)
    
    result = strategist.predict_win_rate(battle_state)
    # => {
    #     "player_a_win_rate": 0.53,
    #     "player_b_win_rate": 0.47,
    #     "optimal_action": {"type": "move", "move": "Make It Rain", "target": 1},
    #     "optimal_action_win_rate": 0.53,
    #     "action_win_rates": {...}
    # }

実装フェーズ: P1-3-B (Week 1)
優先度: CRITICAL 🔥
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from predictor.core.models import (
    BattleState,
    PlayerState,
    PokemonBattleState,
    ActionCandidate
)
from predictor.core.eval_algorithms.heuristic_eval import HeuristicEvaluator
from predictor.engine.smogon_calc_wrapper import SmogonCalcWrapper
from src.domain.models import get_type_effectiveness
from src.domain.models.item_effects import (
    get_item_effect,
    get_boost_multiplier,
    ItemCategory
)
from src.domain.models.item import Item
from src.domain.models.move import Move


@dataclass
class Action:
    """
    バトル中の行動を表現
    
    VGCはダブルバトルなので、プレイヤーは各ターンに2体分の行動を選択する。
    """
    type: str  # "move", "switch", "terastallize"
    pokemon_slot: int  # 0 or 1 (どちらのポケモンの行動か)
    move_name: Optional[str] = None  # type="move"の場合
    target_slot: Optional[int] = None  # 攻撃対象 (0, 1, 2, 3)
    switch_to: Optional[str] = None  # type="switch"の場合
    tera_type: Optional[str] = None  # type="terastallize"の場合


@dataclass
class TurnAction:
    """1ターンの行動セット (VGCでは2体分)"""
    player_a_actions: List[Action]  # [pokemon_0の行動, pokemon_1の行動]
    player_b_actions: List[Action]


class MonteCarloStrategist:
    """
    Monte Carlo Tree Search (MCTS) による勝率予測エンジン
    
    アルゴリズム:
    1. 現在の盤面から、全ての合法手を列挙
    2. 各行動について n_rollouts / len(actions) 回ずつランダムシミュレーション
    3. シミュレーションごとに、バトルが終了するまでランダムな手を打ち続ける
    4. 最終的な勝敗を記録し、最も勝率の高い行動を「最適手」として返す
    
    評価関数:
    - 既存の PositionEvaluator (heuristic_eval) を活用
    - バトル終了判定に使用
    
    データ依存:
    - 0件 (シミュレーションベースのため学習不要)
    """
    
    def __init__(
        self,
        n_rollouts: int = 1000,
        max_turns: int = 50,
        use_heuristic: bool = True,
        random_seed: Optional[int] = None,
        use_damage_calc: bool = False,  # Phase 1: ダメージ計算は簡易版
        use_opponent_model: bool = True  # Priority 3: 相手行動予測を使用
    ):
        """
        Args:
            n_rollouts: シミュレーション試行回数 (推奨: 500-1000)
            max_turns: 1試合の最大ターン数 (無限ループ防止)
            use_heuristic: ヒューリスティック評価を使用するか
            random_seed: 再現性のための乱数シード
            use_damage_calc: smogon_calc_wrapper を使用するか (Phase 2以降)
            use_opponent_model: 相手行動予測を使用するか (Priority 3)
        """
        self.n_rollouts = n_rollouts
        self.max_turns = max_turns
        self.use_heuristic = use_heuristic
        self.use_damage_calc = use_damage_calc
        self.use_opponent_model = use_opponent_model
        
        if random_seed is not None:
            random.seed(random_seed)
        
        # 評価器を初期化
        self.evaluator = HeuristicEvaluator()
        
        # ダメージ計算器 (Phase 2以降で使用)
        self.damage_calc = None
        if use_damage_calc:
            try:
                self.damage_calc = SmogonCalcWrapper()
            except Exception:
                pass  # Fallback to simple damage
        
        # Priority 3: 相手行動予測モデル
        self.opponent_model = None
        if use_opponent_model:
            try:
                from src.domain.services.opponent_model import get_opponent_model
                self.opponent_model = get_opponent_model()
            except ImportError:
                pass  # OpponentModelが利用不可
        
        # 統計情報
        self.total_simulations = 0
        self.cache_hits = 0
    
    def predict_win_rate(
        self,
        battle_state: BattleState,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        現在の盤面から勝率を予測し、最適手を返す
        
        Args:
            battle_state: 現在のバトル状態
            verbose: 詳細ログを出力するか
        
        Returns:
            {
                "player_a_win_rate": float,      # Player Aの勝率 (0.0-1.0)
                "player_b_win_rate": float,      # Player Bの勝率
                "optimal_action": TurnAction,    # 最適な行動セット
                "optimal_action_win_rate": float,# 最適手の勝率
                "action_win_rates": Dict,        # 各行動の勝率分布
                "total_rollouts": int,           # 実行したrollout数
                "avg_turns_per_rollout": float   # 平均ターン数
            }
        """
        # 合法手を列挙
        legal_actions = self._get_legal_actions(battle_state)
        
        if not legal_actions:
            # 合法手がない場合 (バトル終了済み)
            return self._evaluate_terminal_state(battle_state)
        
        if verbose:
            print(f"🔍 Monte Carlo Search: {len(legal_actions)} legal actions found")
        
        # 各行動の勝利数をカウント
        action_stats = {
            i: {"wins": 0, "total": 0, "avg_turns": 0}
            for i in range(len(legal_actions))
        }
        
        # 各行動について rollouts を実行
        trials_per_action = max(1, self.n_rollouts // len(legal_actions))
        total_turns = 0
        
        for action_idx, action in enumerate(legal_actions):
            if verbose and action_idx % 5 == 0:
                print(f"  Testing action {action_idx + 1}/{len(legal_actions)}...")
            
            for trial in range(trials_per_action):
                # バトルをシミュレーション
                winner, turns_taken = self._simulate_battle(battle_state, action)
                
                action_stats[action_idx]["total"] += 1
                action_stats[action_idx]["avg_turns"] += turns_taken
                total_turns += turns_taken
                
                if winner == "player_a":
                    action_stats[action_idx]["wins"] += 1
                
                self.total_simulations += 1
        
        # 勝率を計算
        action_win_rates = {}
        for action_idx, stats in action_stats.items():
            if stats["total"] > 0:
                win_rate = stats["wins"] / stats["total"]
                action_win_rates[action_idx] = win_rate
                action_stats[action_idx]["avg_turns"] = stats["avg_turns"] / stats["total"]
        
        # 最適手を特定
        best_action_idx = max(action_win_rates, key=action_win_rates.get)
        best_action = legal_actions[best_action_idx]
        best_win_rate = action_win_rates[best_action_idx]
        
        if verbose:
            print(f"✅ Best action: {best_action_idx} with win rate {best_win_rate:.2%}")
        
        return {
            "player_a_win_rate": best_win_rate,
            "player_b_win_rate": 1.0 - best_win_rate,
            "optimal_action": best_action,
            "optimal_action_win_rate": best_win_rate,
            "action_win_rates": action_win_rates,
            "total_rollouts": self.n_rollouts,
            "avg_turns_per_rollout": total_turns / self.n_rollouts if self.n_rollouts > 0 else 0,
            "action_stats": action_stats,
            "legal_actions": legal_actions
        }
    
    def _simulate_battle(
        self,
        initial_state: BattleState,
        first_action: TurnAction
    ) -> Tuple[str, int]:
        """
        バトルを最後までシミュレーション
        
        Args:
            initial_state: 開始時の盤面
            first_action: 最初のターンの行動
        
        Returns:
            (winner, turns_taken)
            winner: "player_a" or "player_b"
            turns_taken: かかったターン数
        """
        # 現在の状態をコピー (元の状態を破壊しない)
        current_state = self._copy_state(initial_state)
        
        # 最初のターンを実行
        current_state = self._apply_action(current_state, first_action)
        turns = 1
        
        # バトルが終了するまで Guided Playouts で手を選ぶ
        while turns < self.max_turns:
            # バトル終了判定
            winner = self._check_winner(current_state)
            if winner is not None:
                return winner, turns
            
            # Guided Playouts: ヒューリスティックに基づく重み付け選択
            legal_actions = self._get_legal_actions(current_state)
            if not legal_actions:
                # 合法手がない = 引き分け (稀)
                return "player_a" if random.random() < 0.5 else "player_b", turns
            
            # ============= Priority 3: OpponentModel による相手行動サンプリング =============
            # 相手の行動を確率的にサンプリング（Protect/交代を現実的な確率で）
            opp_action_modifier = None
            if self.opponent_model and self.use_opponent_model:
                try:
                    opp_action_modifier = self._sample_opponent_action(current_state)
                except Exception:
                    pass  # 失敗時はデフォルト動作
            
            # ActionCandidate リストを作成してスコアリング
            action_candidates = self._convert_to_action_candidates(legal_actions)
            if action_candidates and self.use_heuristic:
                weights = self.evaluator.get_action_weights(current_state, action_candidates)
                if weights and len(weights) == len(legal_actions):
                    # 重み付きランダム選択
                    selected_action = random.choices(legal_actions, weights=weights, k=1)[0]
                else:
                    selected_action = random.choice(legal_actions)
            else:
                selected_action = random.choice(legal_actions)
            
            # 相手行動を OpponentModel の結果で上書き
            if opp_action_modifier:
                selected_action = self._apply_opponent_modifier(selected_action, opp_action_modifier)
            
            current_state = self._apply_action(current_state, selected_action)
            turns += 1
        
        # 最大ターン数に達した場合、ヒューリスティック評価で勝者を決定
        if self.use_heuristic:
            heuristic_score = self._evaluate_heuristic(current_state)
            winner = "player_a" if heuristic_score > 0 else "player_b"
        else:
            winner = "player_a" if random.random() < 0.5 else "player_b"
        
        return winner, turns
    
    def _sample_opponent_action(self, state: BattleState) -> Optional[Dict[str, Any]]:
        """
        OpponentModel を使って相手の行動をサンプリング
        
        Returns:
            {"protect": [False, True], "switch": [False, False]} など
        """
        if not self.opponent_model:
            return None
        
        result = {"protect": [False, False], "switch": [False, False]}
        
        # 各スロットの相手ポケモンについて予測
        for slot, poke in enumerate(state.player_b.active[:2]):
            if not poke or poke.hp_fraction <= 0:
                continue
            
            # Protect確率をサンプリング
            # OpponentModelはpoke-env形式を期待するが、ここでは簡易的に確率だけ使う
            protect_prob = 0.15  # 基本確率
            switch_prob = 0.1
            
            # Protect判定
            if random.random() < protect_prob:
                result["protect"][slot] = True
            
            # 交代判定（Protectしなかった場合のみ）
            if not result["protect"][slot] and random.random() < switch_prob:
                result["switch"][slot] = True
        
        return result
    
    def _apply_opponent_modifier(self, action: TurnAction, modifier: Dict[str, Any]) -> TurnAction:
        """相手行動をOpponentModelの結果で修正"""
        import copy
        modified = copy.deepcopy(action)
        
        # Player B の行動を修正
        for slot, should_protect in enumerate(modifier.get("protect", [])):
            if should_protect and slot < len(modified.player_b_actions):
                modified.player_b_actions[slot] = Action(
                    type="move",
                    pokemon_slot=slot + 2,  # Player Bは2,3
                    move_name="protect",
                    target_slot=None
                )
        
        return modified
    
    def _get_legal_actions(self, state: BattleState) -> List[TurnAction]:
        """
        現在の盤面から合法手を列挙
        
        VGCダブルバトルの場合:
        - 各プレイヤーは2体のポケモンを場に出している
        - 各ターン、2体分の行動を同時に選択
        - 行動: 技を使う、交代する、テラスタルする
        
        Phase 1実装:
        - state.legal_actions から ActionCandidate を取得
        - ActionCandidate を TurnAction に変換
        """
        legal_actions = []
        
        # Player Aの合法手を取得
        player_a_candidates = state.legal_actions.get("A", [])
        
        if not player_a_candidates:
            # Fallback: 場のポケモンの技を列挙
            player_a_candidates = self._generate_fallback_actions(state.player_a)
        
        # 簡略化: 各ポケモンの最初の技のみを考慮 (Phase 1)
        # 本来は全ての技の組み合わせを考慮すべきだが、計算量削減のため
        for candidate in player_a_candidates[:10]:  # 最初の10手のみ
            action = TurnAction(
                player_a_actions=[
                    Action(
                        type="move",
                        pokemon_slot=candidate.slot,
                        move_name=candidate.move,
                        target_slot=self._parse_target(candidate.target)
                    )
                ],
                player_b_actions=[
                    Action(
                        type="move",
                        pokemon_slot=0,
                        move_name="tackle",  # ダミー
                        target_slot=0
                    )
                ]
            )
            legal_actions.append(action)
        
        # 最低1つは返す
        if not legal_actions:
            legal_actions = self._generate_dummy_actions(state)
        
        return legal_actions
    
    def _generate_fallback_actions(self, player: PlayerState) -> List[ActionCandidate]:
        """legal_actions が空の場合のフォールバック"""
        actions = []
        for slot, pokemon in enumerate(player.active):
            if pokemon.moves:
                for move in pokemon.moves[:2]:  # 最初の2つの技
                    actions.append(
                        ActionCandidate(
                            actor=pokemon.name,
                            slot=slot,
                            move=move,
                            target=None
                        )
                    )
        return actions
    
    def _generate_dummy_actions(self, state: BattleState) -> List[TurnAction]:
        """完全フォールバック: ダミー行動を生成"""
        return [
            TurnAction(
                player_a_actions=[
                    Action(type="move", pokemon_slot=0, move_name="tackle", target_slot=2)
                ],
                player_b_actions=[
                    Action(type="move", pokemon_slot=2, move_name="tackle", target_slot=0)
                ]
            )
        ]
    
    def _convert_to_action_candidates(self, turn_actions: List[TurnAction]) -> List[ActionCandidate]:
        """
        TurnAction リストを ActionCandidate リストに変換
        
        Guided Playouts のためのスコアリングで使用。
        Player A の行動のみを抽出してスコアリング用に変換する。
        """
        candidates = []
        for turn_action in turn_actions:
            for act in turn_action.player_a_actions:
                if act.type == "move" and act.move_name:
                    candidates.append(
                        ActionCandidate(
                            actor=f"slot_{act.pokemon_slot}",
                            slot=act.pokemon_slot,
                            move=act.move_name,
                            target=str(act.target_slot) if act.target_slot is not None else None,
                            tags=[],  # 基本タグは空、必要に応じて拡張
                            metadata={}
                        )
                    )
        return candidates
    
    def _parse_target(self, target: Optional[str]) -> int:
        """対象を slot 番号に変換"""
        if target is None:
            return 2  # デフォルトで相手の左側
        # TODO: 実際のターゲット解析
        return 2

    def _calculate_damage(self, attacker: Optional[PokemonBattleState], 
                         defender: Optional[PokemonBattleState], 
                         move_name: str) -> float:
        """
        簡易ダメージ計算 (ダメージ率を返す)
        
        Phase 2実装:
        - ステータスベース
        - タイプ相性
        - アイテム補正
        """
        if not attacker or not defender:
            return 0.1
            
        # 簡易的に物理/特殊を高い方で採用
        # PokemonBattleState は stats 辞書を持つ可能性がある
        atk = 100  # デフォルト
        if hasattr(attacker, 'stats') and attacker.stats:
            atk = max(attacker.stats.get('atk', 100), attacker.stats.get('spa', 100))
        elif hasattr(attacker, 'attack'):
            atk = max(attacker.attack, attacker.special_attack)
        
        # 防御力
        def_stat = 100  # デフォルト
        if hasattr(defender, 'stats') and defender.stats:
            def_stat = min(defender.stats.get('def', 100), defender.stats.get('spd', 100))
        elif hasattr(defender, 'defense'):
            def_stat = min(defender.defense, defender.special_defense)
        if def_stat == 0: def_stat = 1
        
        # Move Data
        move = Move(move_name)
        base_power = move.base_power
        
        # アイテムによる威力補正 (攻撃側)
        if attacker.item:
            item = Item(attacker.item)
            base_power *= item.get_damage_modifier(move.type, move.is_physical) # type: ignore

        # タイプ相性
        # move_name からタイプを推測するのは困難なため、ここでは等倍とする
        # 実際には Move オブジェクトを Action に含める改修が必要 (Phase 2.1)
        effectiveness = 1.0
        if move.type:
             # ここで本当はタイプ相性計算を入れるべきだが、今回はアイテム実装が主。
             # 既存の get_type_effectiveness を使うには defender.types が必要
             pass

        # ダメージ = (威力 * 攻撃 / 防御) * 係数
        # レベル50想定: (22 * 威力 * A / D / 50 + 2) * ...
        damage_pct = (base_power * atk / def_stat / 200.0)
        
        # アイテムによる軽減 (防御側) - 半減実
        if defender.item and effectiveness > 1.0: # 効果抜群の場合のみ
             def_item = Item(defender.item)
             resist_type = def_item.get_resist_berry_type()
             if resist_type and resist_type == move.type:
                 damage_pct *= 0.5
        
        # 乱数 (0.85 ~ 1.0)
        damage_pct *= random.uniform(0.85, 1.0)
        
        # Life Orbの反動などは _apply_action で処理するが、
        # ここでは純粋なダメージ予測のみ
        
        return min(damage_pct, 1.0)

    
    def _apply_action(
        self,
        state: BattleState,
        action: TurnAction
    ) -> BattleState:
        """
        行動を適用し、新しい状態を返す
        
        Phase 1実装:
        - 簡易ダメージ計算 (ランダム10-30%)
        - HPを減らす
        - 倒れたポケモンの処理
        
        Phase 2実装:
        - _calculate_damage によるダメージ計算
        """
        new_state = copy.deepcopy(state)
        
        # Player Aの行動を適用
        for act in action.player_a_actions:
            if act.type == "move" and act.target_slot is not None:
                attacker = None
                if act.pokemon_slot < len(new_state.player_a.active):
                    attacker = new_state.player_a.active[act.pokemon_slot]
                
                defender = None
                if act.target_slot < 2:
                    if act.target_slot < len(new_state.player_a.active):
                        defender = new_state.player_a.active[act.target_slot]
                else:
                    b_slot = act.target_slot - 2
                    if b_slot < len(new_state.player_b.active):
                        defender = new_state.player_b.active[b_slot]

                damage = self._calculate_damage(attacker, defender, act.move_name)
                self._apply_damage(new_state, act.target_slot, damage)
        
        # Player Bの行動を適用
        for act in action.player_b_actions:
            if act.type == "move" and act.target_slot is not None:
                attacker = None
                if act.pokemon_slot < len(new_state.player_b.active):
                    attacker = new_state.player_b.active[act.pokemon_slot]
                
                defender = None
                if act.target_slot < 2:
                    if act.target_slot < len(new_state.player_a.active):
                        defender = new_state.player_a.active[act.target_slot]
                else:
                    b_slot = act.target_slot - 2
                    if b_slot < len(new_state.player_b.active):
                        defender = new_state.player_b.active[b_slot]
                        
                damage = self._calculate_damage(attacker, defender, act.move_name)
                self._apply_damage(new_state, act.target_slot, damage)
        
        # 倒れたポケモンの処理
        self._remove_fainted(new_state)
        
        return new_state
    
    def _apply_damage(self, state: BattleState, target_slot: int, damage_fraction: float):
        """指定したslotのポケモンにダメージを与える"""
        if target_slot < 2:
            # Player Aのポケモン
            if target_slot < len(state.player_a.active):
                pokemon = state.player_a.active[target_slot]
                pokemon.hp_fraction = max(0.0, pokemon.hp_fraction - damage_fraction)
        else:
            # Player Bのポケモン
            b_slot = target_slot - 2
            if b_slot < len(state.player_b.active):
                pokemon = state.player_b.active[b_slot]
                pokemon.hp_fraction = max(0.0, pokemon.hp_fraction - damage_fraction)
    
    def _remove_fainted(self, state: BattleState):
        """倒れたポケモンを場から除外"""
        state.player_a.active = [p for p in state.player_a.active if p.hp_fraction > 0]
        state.player_b.active = [p for p in state.player_b.active if p.hp_fraction > 0]
    
    def _check_winner(self, state: BattleState) -> Optional[str]:
        """
        バトル終了判定
        
        Returns:
            "player_a": Player Aの勝利
            "player_b": Player Bの勝利
            None: バトル継続中
        """
        # Player Aの場のポケモンが全滅
        if not state.player_a.active or all(p.hp_fraction <= 0 for p in state.player_a.active):
            # 控えがいない場合は負け
            if not state.player_a.reserves:
                return "player_b"
        
        # Player Bの場のポケモンが全滅
        if not state.player_b.active or all(p.hp_fraction <= 0 for p in state.player_b.active):
            if not state.player_b.reserves:
                return "player_a"
        
        return None
    
    def _evaluate_heuristic(self, state: BattleState) -> float:
        """
        ヒューリスティック評価
        
        HeuristicEvaluator を使用して、現在の盤面の有利度を評価する。
        
        Returns:
            > 0: Player A有利
            < 0: Player B有利
            = 0: 互角
        """
        try:
            # HeuristicEvaluator で評価
            evaluation = self.evaluator.evaluate(state)
            
            # 勝率から有利度スコアに変換
            # win_rate: 0.0-1.0 → score: -5.0 ~ +5.0
            win_rate_a = evaluation.player_a.win_rate
            score = (win_rate_a - 0.5) * 10  # 0.5 (互角) を 0.0 に、0.0/1.0 を ±5.0 に
            
            return score
        except Exception:
            # フォールバック: HP比較
            hp_a = sum(p.hp_fraction for p in state.player_a.active)
            hp_b = sum(p.hp_fraction for p in state.player_b.active)
            return hp_a - hp_b
    
    def _evaluate_terminal_state(self, state: BattleState) -> Dict[str, Any]:
        """
        終了状態の評価 (合法手がない場合)
        """
        winner = self._check_winner(state)
        
        if winner == "player_a":
            return {
                "player_a_win_rate": 1.0,
                "player_b_win_rate": 0.0,
                "optimal_action": None,
                "optimal_action_win_rate": 1.0,
                "action_win_rates": {},
                "total_rollouts": 0,
                "avg_turns_per_rollout": 0
            }
        elif winner == "player_b":
            return {
                "player_a_win_rate": 0.0,
                "player_b_win_rate": 1.0,
                "optimal_action": None,
                "optimal_action_win_rate": 0.0,
                "action_win_rates": {},
                "total_rollouts": 0,
                "avg_turns_per_rollout": 0
            }
        else:
            # 引き分け (稀)
            return {
                "player_a_win_rate": 0.5,
                "player_b_win_rate": 0.5,
                "optimal_action": None,
                "optimal_action_win_rate": 0.5,
                "action_win_rates": {},
                "total_rollouts": 0,
                "avg_turns_per_rollout": 0
            }
    
    def _copy_state(self, state: BattleState) -> BattleState:
        """
        バトル状態のディープコピー
        """
        return copy.deepcopy(state)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        実行統計を取得
        """
        return {
            "total_simulations": self.total_simulations,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": self.cache_hits / max(1, self.total_simulations)
        }
