"""
VGCPredictor - 統合予測クラス

PokéChamp型 + PokeLLMon流ハイブリッドアーキテクチャの
メインエントリーポイント。

References:
- PokéChamp: https://arxiv.org/abs/2503.04094
- PokeLLMon: https://arxiv.org/abs/2402.01118
- NEW_ARCHITECTURE_SPEC.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from predictor.engine.simulator_adapter import (
    JointAction,
    SimulatorAdapter,
    get_simulator,
)
from predictor.core.candidate_generator import (
    CandidateGenerator,
    CandidateConfig,
    get_candidate_generator,
)
from predictor.core.evaluator import (
    Evaluator,
    EvaluatorConfig,
    get_evaluator,
)
from predictor.core.game_solver import (
    GameSolver,
    SolverConfig,
    SolveResult,
    ActionProbability,
    SwingPoint,
    get_game_solver,
)
from predictor.core.explainer import (
    Explainer,
    ExplanationResult,
    ExplanationAnchor,
    get_explainer,
)

try:
    from poke_env.environment.double_battle import DoubleBattle
except ImportError:
    try:
        from poke_env.battle import DoubleBattle
    except ImportError:
        DoubleBattle = None


# ============================================================================
# 出力データ構造
# ============================================================================

@dataclass
class PredictionResult:
    """予測結果（観戦AI用）"""
    
    # 勝率
    win_prob: float
    
    # 最善手 (JointAction)
    best_action: Optional[JointAction]
    
    # 自分の行動分布（Top 5）
    self_actions: List[Dict[str, Any]]
    
    # 相手の行動分布（Top 5）
    opp_actions: List[Dict[str, Any]]
    
    # 分岐点
    swing_points: List[Dict[str, Any]]
    
    # 説明
    explanation: str
    explanation_anchors: List[Dict[str, Any]]
    
    # 詳細（デバッグ用）
    breakdown: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        return {
            "win_prob": self.win_prob,
            "self_actions": self.self_actions,
            "opp_actions": self.opp_actions,
            "swing_points": self.swing_points,
            "explanation": self.explanation,
            "explanation_anchors": self.explanation_anchors,
            "breakdown": self.breakdown,
        }
    
    def __str__(self) -> str:
        lines = []
        lines.append(f"=== 予測結果 ===")
        lines.append(f"勝率: {self.win_prob:.1%}")
        lines.append("")
        
        lines.append("【自分の行動】")
        for a in self.self_actions[:3]:
            lines.append(f"  {a['action']} ({a['prob']:.1%}) Δ={a.get('delta', 0):+.1%}")
        
        lines.append("")
        lines.append("【相手の予測】")
        for a in self.opp_actions[:3]:
            lines.append(f"  {a['action']} ({a['prob']:.1%})")
        
        if self.swing_points:
            lines.append("")
            lines.append("【分岐点】")
            for sp in self.swing_points[:2]:
                lines.append(f"  {sp['desc']} (影響: {sp['impact']:+.1%})")
        
        lines.append("")
        lines.append(f"【解説】{self.explanation}")
        
        return "\n".join(lines)


# ============================================================================
# VGCPredictor
# ============================================================================

@dataclass
class PredictorConfig:
    """予測器の設定"""
    # Solver設定
    depth: int = 3
    n_samples: int = 12
    top_k: int = 25
    tau: float = 0.25
    tau_self: float = 0.30
    
    # LLM設定
    use_llm: bool = False
    llm_weight: float = 0.4
    
    # 出力設定
    explain_language: str = "ja"  # "ja" or "en"


class VGCPredictor:
    """
    VGC観戦AI予測システム
    
    毎ターンの処理:
    1. 候補生成（CandidateGenerator）
    2. ゲーム探索（GameSolver）
    3. 説明生成（Explainer）
    4. 結果を返す
    """
    
    def __init__(
        self,
        config: Optional[PredictorConfig] = None,
        llm_client: Optional[Any] = None,
    ):
        self.config = config or PredictorConfig()
        self.llm = llm_client
        
        # モジュール初期化
        self.simulator = get_simulator()
        self.generator = get_candidate_generator()
        self.evaluator = get_evaluator()
        
        # TurnAdvisor 統合
        self.turn_advisor = None
        if llm_client:
            try:
                from predictor.core.turn_advisor import TurnAdvisor
                self.turn_advisor = TurnAdvisor(llm_client=llm_client)
            except ImportError:
                pass
        
        # Solver設定
        solver_config = SolverConfig(
            depth=self.config.depth,
            n_samples=self.config.n_samples,
            top_k_self=self.config.top_k,
            top_k_opp=self.config.top_k,
            tau=self.config.tau,
            tau_self=self.config.tau_self,
            llm_weight=self.config.llm_weight,
            use_llm=self.config.use_llm,
        )
        self.solver = GameSolver(
            config=solver_config,
            simulator=self.simulator,
            generator=self.generator,
            evaluator=self.evaluator,
            llm_client=self.llm,
        )
        
        self.explainer = Explainer(llm_client=self.llm)
        
        # GamePlan 参照用（外部から設定される）
        self.game_plan = None
        
        print(f"🎮 VGCPredictor 初期化完了")
        print(f"  - 探索深さ: {self.config.depth}")
        print(f"  - 候補数: {self.config.top_k}")
        print(f"  - LLM: {'有効' if self.config.use_llm else '無効'}")
        if self.turn_advisor:
            print(f"  - TurnAdvisor: 有効（MCTS候補制限）")
    
    def predict(self, battle: DoubleBattle) -> PredictionResult:
        """
        予測を実行
        
        Args:
            battle: poke-envのDoubleBattleオブジェクト
            
        Returns:
            PredictionResult
        """
        # ============= TurnAdvisor 候補フィルタリング =============
        # Phase 10: TurnAdvisor は合理的ベスト5を選出し、MCTSでボーナス加算して評価
        turn_recommendation = None
        recommended_moves = None
        if self.turn_advisor and self.llm:
            try:
                turn_recommendation = self.turn_advisor.advise(battle, self.game_plan)
                if turn_recommendation:
                    # 推奨技をSolverに渡す（ボーナス加算用）
                    recommended_moves = {
                        0: set(m.lower() for m in turn_recommendation.slot0_moves),
                        1: set(m.lower() for m in turn_recommendation.slot1_moves),
                    }
                    print(f"  🎯 TurnAdvisor 推奨 ({turn_recommendation.thought_process[:50]}...):")
                    print(f"     slot0={turn_recommendation.slot0_moves}")
                    print(f"     slot1={turn_recommendation.slot1_moves}")
            except Exception as e:
                print(f"  ⚠️ TurnAdvisor エラー: {e}")
        
        # 1. ゲーム探索（Phase 10: recommended_moves をボーナスとして渡す）
        solve_result = self.solver.solve(battle, recommended_moves=recommended_moves)
        
        # 2. 説明生成
        explanation = self.explainer.explain(battle, solve_result)
        
        # 3. 相手ポケモン名の取得（表示用）
        opp_names = []
        for p in battle.opponent_active_pokemon:
            if p and not p.fainted:
                opp_names.append(p.species.capitalize())
            else:
                opp_names.append("???")
        
        # 自分ポケモン名の取得
        self_names = []
        for p in battle.active_pokemon:
            if p and not p.fainted:
                self_names.append(p.species.capitalize())
            else:
                self_names.append("???")
        
        # 4. 結果を整形
        self_actions = []
        for ap in solve_result.self_dist:
            action_str = self._format_joint_action(ap.action, self_names, opp_names)
            self_actions.append({
                "action": action_str,
                "prob": ap.probability,
                "delta": ap.delta or 0.0,
                "tags": ap.tags,
            })
        
        opp_actions = []
        for ap in solve_result.opp_dist:
            action_str = self._format_joint_action(ap.action, opp_names, self_names)
            opp_actions.append({
                "action": action_str,
                "prob": ap.probability,
                "tags": ap.tags,
            })
        
        swing_points = []
        for sp in solve_result.swing_points:
            swing_points.append({
                "desc": sp.description,
                "impact": sp.impact,
            })
        
        anchors = []
        for a in explanation.anchors:
            anchors.append({
                "category": a.category,
                "fact": a.fact,
                "impact": a.impact,
            })
        
        return PredictionResult(
            win_prob=solve_result.win_prob,
            best_action=solve_result.self_dist[0].action if solve_result.self_dist else None,
            self_actions=self_actions,
            opp_actions=opp_actions,
            swing_points=swing_points,
            explanation=explanation.short,
            explanation_anchors=anchors,
            breakdown=solve_result.breakdown,
        )
    
    def _format_joint_action(
        self, 
        action: JointAction, 
        user_names: List[str], 
        target_names: List[str]
    ) -> str:
        """JointActionを読みやすい形式に変換"""
        from predictor.engine.simulator_adapter import ActionType
        
        parts = []
        for i, order in enumerate([action.slot0, action.slot1]):
            if i < len(user_names):
                user = user_names[i]
            else:
                user = f"Slot{i}"
            
            if order.action_type == ActionType.PASS:
                parts.append(f"{user}: pass")
            elif order.action_type == ActionType.SWITCH:
                parts.append(f"{user}: 交代")
            elif order.action_type in (ActionType.MOVE, ActionType.TERA_MOVE):
                move_name = order.move_id or "???"
                
                # 技のターゲットタイプを取得
                is_spread_move = self._is_spread_move(move_name)
                
                # ターゲット表示（単体技のみ）
                target_str = ""
                if not is_spread_move:
                    if order.target is not None and order.target < 0:
                        # 相手への攻撃
                        target_idx = (-order.target) - 1
                        if target_idx < len(target_names):
                            target_str = f"→{target_names[target_idx]}"
                    elif order.target is not None and order.target > 0:
                        # 味方への技
                        target_str = f"→味方"
                
                tera = "テラス+" if order.action_type == ActionType.TERA_MOVE else ""
                parts.append(f"{user}: {tera}{move_name}{target_str}")
            else:
                parts.append(f"{user}: ???")
        
        return " / ".join(parts)
    
    def _is_spread_move(self, move_id: str) -> bool:
        """
        技が「ターゲット表示不要」かどうかを判定
        - 全体技（相手全体、自分以外全体）
        - 自己対象技（まもる、つるぎのまい等）
        - 味方サイド技（おいかぜ等）
        - 相手サイド技（ステロ等）
        """
        if not move_id:
            return False
        
        move_lower = move_id.lower()
        
        # ターゲット表示不要な技リスト
        NO_TARGET_MOVES = {
            # === 相手全体技 ===
            "icywind", "electroweb", "heatwave", "dazzlinggleam", "hypervoice",
            "makeitrain", "snarl", "rockslide", "bleakwindstorm", "discharge",
            "blizzard", "surf", "earthquake", "bulldoze", "mudshot",
            "razorleaf", "swift", "petalblizzard", "glaciate", "eruption",
            "waterspout", "dragonenergy", "synchronoise", "struggle",
            
            # === 自分以外全体技 ===
            "boomburst", "explosion", "selfdestruct", "mindblown",
            
            # === 自己対象技（まもる系） ===
            "protect", "detect", "spikyshield", "kingsshield", "banefulbunker",
            "silktrap", "obstruct", "endure", "wideguard", "quickguard",
            
            # === 自己対象技（積み技） ===
            "nastyplot", "swordsdance", "calmmind", "dragondance", "quiverdance",
            "shellsmash", "coil", "bulkup", "irondefense", "amnesia",
            "agility", "autotomize", "rockpolish", "workup", "growth",
            "curse", "bellydrum", "substitute", "minimize", "rest",
            
            # === 自己対象技（フォルムチェンジ等） ===
            "transform", "geomancy",
            
            # === 味方サイド技 ===
            "tailwind", "trickroom", "reflect", "lightscreen", "auroraveil",
            "safeguard", "mist", "luckychant", "matblock", "craftyshield",
            
            # === 相手サイド技 ===
            "stealthrock", "spikes", "toxicspikes", "stickyweb",
            
            # === 味方引き寄せ技（自分に使う） ===
            "followme", "ragepowder", "spotlight",
            
            # === 天候・フィールド技 ===
            "sunnyday", "raindance", "sandstorm", "snowscape", "hail",
            "electricterrain", "grassyterrain", "mistyterrain", "psychicterrain",
            
            # === その他補助技（ターゲット不要） ===
            "taunt", "encore", "disable", "torment", "imprison", "trick",
            "switcheroo", "skillswap", "roar", "whirlwind", "yawn", "perishsong",
        }
        
        return move_lower in NO_TARGET_MOVES
    
    def get_best_action(self, battle: DoubleBattle) -> Optional[JointAction]:
        """最善手を取得"""
        result = self.predict(battle)
        
        if result.self_actions:
            # JointAction に戻す（文字列からの復元は困難なので、再計算）
            solve_result = self.solver.solve(battle)
            if solve_result.self_dist:
                return solve_result.self_dist[0].action
        
        return None
    
    def explain_turn(self, battle: DoubleBattle) -> str:
        """ターンの説明を取得（簡易版）"""
        result = self.predict(battle)
        return str(result)


# ============================================================================
# シングルトン
# ============================================================================

_predictor: Optional[VGCPredictor] = None

def get_predictor() -> VGCPredictor:
    """VGCPredictorのシングルトンを取得"""
    global _predictor
    if _predictor is None:
        _predictor = VGCPredictor()
    return _predictor
