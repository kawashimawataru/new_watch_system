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
        use_damage_calc: bool = False  # Phase 1: ダメージ計算は簡易版
    ):
        """
        Args:
            n_rollouts: シミュレーション試行回数 (推奨: 500-1000)
            max_turns: 1試合の最大ターン数 (無限ループ防止)
            use_heuristic: ヒューリスティック評価を使用するか
            random_seed: 再現性のための乱数シード
            use_damage_calc: smogon_calc_wrapper を使用するか (Phase 2以降)
        """
        self.n_rollouts = n_rollouts
        self.max_turns = max_turns
        self.use_heuristic = use_heuristic
        self.use_damage_calc = use_damage_calc
        
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
        
        # バトルが終了するまでランダムな手を打ち続ける
        while turns < self.max_turns:
            # バトル終了判定
            winner = self._check_winner(current_state)
            if winner is not None:
                return winner, turns
            
            # ランダムな行動を選択
            legal_actions = self._get_legal_actions(current_state)
            if not legal_actions:
                # 合法手がない = 引き分け (稀)
                return "player_a" if random.random() < 0.5 else "player_b", turns
            
            random_action = random.choice(legal_actions)
            current_state = self._apply_action(current_state, random_action)
            turns += 1
        
        # 最大ターン数に達した場合、ヒューリスティック評価で勝者を決定
        if self.use_heuristic:
            heuristic_score = self._evaluate_heuristic(current_state)
            winner = "player_a" if heuristic_score > 0 else "player_b"
        else:
            winner = "player_a" if random.random() < 0.5 else "player_b"
        
        return winner, turns
    
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
    
    def _parse_target(self, target: Optional[str]) -> int:
        """対象を slot 番号に変換"""
        if target is None:
            return 2  # デフォルトで相手の左側
        # TODO: 実際のターゲット解析
        return 2
    
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
        
        Phase 2以降:
        - smogon_calc_wrapper を使った正確なダメージ計算
        - 速度判定
        - 状態異常
        - 天候・フィールド効果
        """
        new_state = copy.deepcopy(state)
        
        # Player Aの行動を適用
        for act in action.player_a_actions:
            if act.type == "move" and act.target_slot is not None:
                # 簡易ダメージ: 10-30%のランダムダメージ
                damage = random.uniform(0.1, 0.3)
                self._apply_damage(new_state, act.target_slot, damage)
        
        # Player Bの行動を適用
        for act in action.player_b_actions:
            if act.type == "move" and act.target_slot is not None:
                damage = random.uniform(0.1, 0.3)
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
