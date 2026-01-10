"""
RiskAwareSolver - リスク考慮型の意思決定

cona氏の思考法をAI意思決定に落とし込む:
  1. 勝ってる時は低確率の負け筋を切って、太い最善を押す（Secure Mode）
  2. 負けてる時はアウト（上振れ筋）に寄せる（Gamble Mode）
  3. 「読み」はリスク/リターン/やってきそう の3要件で打つ（ReadAnalyzer）

概念:
  Secure Mode（有利時）:
    選択基準 = E[value] - λ * Risk（リスク回避）
    → 確実な行動を優先、読みは控える
    → 「負け筋を引かない」に重点

  Gamble Mode（不利時）:
    選択基準 = E[value] + κ * Upside（上振れ狙い）
    → ハイリスク・ハイリターンを許容
    → 「運勝ち筋」「一点読み」も検討

References:
  - cona氏コーチング動画「根拠を持ってプレイしろ」
  - cona氏解説動画「"読み"とは何か」「逆転のテクニック」
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


# ============================================================================
# モード定義
# ============================================================================

class RiskMode(Enum):
    """リスク管理モード"""
    SECURE = "secure"    # 有利時: リスク回避
    NEUTRAL = "neutral"  # 互角: 標準
    GAMBLE = "gamble"    # 不利時: 上振れ狙い


# ============================================================================
# 設定
# ============================================================================

@dataclass
class RiskAwareConfig:
    """リスク管理の設定"""
    
    # Secure Mode のリスク回避係数
    # 高いほど「負け筋を避ける」
    lambda_secure: float = 0.5
    
    # Gamble Mode の上振れ係数
    # 高いほど「ワンチャンを狙う」
    kappa_gamble: float = 0.3
    
    # モード切り替えの閾値
    advantage_threshold: float = 0.55   # この勝率以上なら Secure
    disadvantage_threshold: float = 0.45  # この勝率以下なら Gamble
    
    # 読みの3要件の閾値
    read_risk_threshold: float = 0.7     # これ以上のリスクなら読まない
    read_reward_threshold: float = 0.3   # これ以下のリターンなら読まない
    read_likelihood_threshold: float = 0.3  # これ以下の確率なら読まない


# ============================================================================
# 読みの判断結果
# ============================================================================

@dataclass
class ReadDecision:
    """読みの判断結果"""
    should_read: bool           # 読むべきか
    reason: str                 # 判断理由
    risk: float                 # 外した時の損失（0-1）
    reward: float               # 当たった時の得（0-1）
    likelihood: float           # やってきそうか（0-1）
    confidence: float = 0.0     # 判断の確信度（デバッグ用）
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "should_read": self.should_read,
            "reason": self.reason,
            "risk": self.risk,
            "reward": self.reward,
            "likelihood": self.likelihood,
            "confidence": self.confidence,
        }
    
    def __str__(self) -> str:
        emoji = "✅" if self.should_read else "❌"
        return (
            f"{emoji} 読み判定: {self.reason}\n"
            f"   リスク: {self.risk:.0%} / リターン: {self.reward:.0%} / 確率: {self.likelihood:.0%}"
        )


# ============================================================================
# ReadAnalyzer - 読みの3要件
# ============================================================================

class ReadAnalyzer:
    """
    cona思考「読みの3要件」を判定
    
    3要件:
      1. リスク（外した時の被害）
      2. リターン（当たった時の得）
      3. やってきそうか（相手の確率）
    
    例: ガチグマ(根性) vs クレセリア
      - ガチグマは「守る＋火炎玉発動」をしてきそう（確率高）
      - リスク評価: ガチグマ無視して隣を攻撃 → 空元気で大ダメージ（リスク大）
      - リターン評価: 守る読みでクレセリアを攻撃 → 硬くて倒せない（リターン小）
      - 結論: 「やってきそう」でも、リスク大・リターン小なので「読まない」
    """
    
    def __init__(self, config: Optional[RiskAwareConfig] = None):
        self.config = config or RiskAwareConfig()
    
    def analyze(
        self,
        standard_value: float,       # 安定行動の期待値
        read_value_if_hit: float,    # 読みが当たった時の期待値
        read_value_if_miss: float,   # 読みが外れた時の期待値
        opponent_action_prob: float, # 相手がその行動をとる確率
    ) -> ReadDecision:
        """
        読むべきかどうかを3要件で判定
        
        Args:
            standard_value: 安定行動（普通に殴る等）の期待値（0-1）
            read_value_if_hit: 読みが当たった時の期待値（0-1）
            read_value_if_miss: 読みが外れた時の期待値（0-1）
            opponent_action_prob: 相手がその行動をとる確率（0-1）
        
        Returns:
            ReadDecision: 読みの判断結果
        """
        # 1. リスク評価
        #    「読みを外して素直に動かれたら、安定行動より何%悪くなるか」
        risk = max(0, standard_value - read_value_if_miss)
        
        # 2. リターン評価
        #    「読みが当たったら、安定行動より何%良くなるか」
        reward = max(0, read_value_if_hit - standard_value)
        
        # 3. やってきそうか
        likelihood = opponent_action_prob
        
        # === 判定ロジック ===
        
        # Check 1: リスクが高すぎる → 読まない
        if risk > self.config.read_risk_threshold:
            return ReadDecision(
                should_read=False,
                reason=f"リスク大({risk:.0%}): 外すと致命的",
                risk=risk,
                reward=reward,
                likelihood=likelihood,
                confidence=0.9,
            )
        
        # Check 2: リターンが低すぎる → 読まない
        if reward < self.config.read_reward_threshold:
            return ReadDecision(
                should_read=False,
                reason=f"リターン小({reward:.0%}): 当たっても微差",
                risk=risk,
                reward=reward,
                likelihood=likelihood,
                confidence=0.85,
            )
        
        # Check 3: やってきそうにない → 読まない
        if likelihood < self.config.read_likelihood_threshold:
            return ReadDecision(
                should_read=False,
                reason=f"確率低({likelihood:.0%}): やってきそうにない",
                risk=risk,
                reward=reward,
                likelihood=likelihood,
                confidence=0.8,
            )
        
        # 全チェック通過 → 読む価値あり
        # 期待値計算
        read_ev = likelihood * read_value_if_hit + (1 - likelihood) * read_value_if_miss
        
        # 読みのEVが安定行動より高ければ読む
        if read_ev > standard_value:
            confidence = min(0.95, (reward - risk) * likelihood + 0.5)
            return ReadDecision(
                should_read=True,
                reason=f"3要件クリア: EV={read_ev:.0%} > 安定={standard_value:.0%}",
                risk=risk,
                reward=reward,
                likelihood=likelihood,
                confidence=confidence,
            )
        else:
            return ReadDecision(
                should_read=False,
                reason=f"EV負け: 読みEV={read_ev:.0%} < 安定={standard_value:.0%}",
                risk=risk,
                reward=reward,
                likelihood=likelihood,
                confidence=0.7,
            )


# ============================================================================
# RiskAwareSolver
# ============================================================================

@dataclass
class ScoredCandidate:
    """スコアリング済み候補"""
    action: Any                    # JointAction など
    expected_value: float          # 期待値
    variance: float = 0.0          # 分散（リスク）
    max_value: float = 0.0         # 最大値（上振れ）
    min_value: float = 0.0         # 最小値（下振れ）
    adjusted_score: float = 0.0    # モード調整後スコア
    tags: List[str] = field(default_factory=list)


class RiskAwareSolver:
    """
    リスク考慮型の意思決定
    
    GameSolver.solve() の最終選択で呼ばれ、
    Quantal Response の分布を状況に応じて調整する。
    """
    
    def __init__(self, config: Optional[RiskAwareConfig] = None):
        self.config = config or RiskAwareConfig()
        self.read_analyzer = ReadAnalyzer(config)
    
    def determine_mode(self, win_prob: float) -> RiskMode:
        """
        現在の勝率からモードを決定
        
        Args:
            win_prob: 現在の期待勝率（0-1）
        
        Returns:
            RiskMode
        """
        if win_prob >= self.config.advantage_threshold:
            return RiskMode.SECURE
        elif win_prob <= self.config.disadvantage_threshold:
            return RiskMode.GAMBLE
        else:
            return RiskMode.NEUTRAL
    
    def adjust_candidates(
        self,
        candidates: List[ScoredCandidate],
        win_prob: float
    ) -> List[ScoredCandidate]:
        """
        状況に応じて候補のスコアを調整
        
        Args:
            candidates: スコアリング済み候補リスト
            win_prob: 現在の期待勝率
        
        Returns:
            adjusted_score が設定された候補リスト
        """
        mode = self.determine_mode(win_prob)
        
        for cand in candidates:
            if mode == RiskMode.SECURE:
                # リスクを嫌う
                # Score = E[value] - λ * Variance
                cand.adjusted_score = (
                    cand.expected_value 
                    - self.config.lambda_secure * cand.variance
                )
                cand.tags.append("secure_adjusted")
            
            elif mode == RiskMode.GAMBLE:
                # 上振れを狙う
                # Score = E[value] + κ * Upside
                upside = max(0, cand.max_value - cand.expected_value)
                cand.adjusted_score = (
                    cand.expected_value 
                    + self.config.kappa_gamble * upside
                )
                cand.tags.append("gamble_adjusted")
            
            else:  # NEUTRAL
                cand.adjusted_score = cand.expected_value
        
        # スコアでソート
        candidates.sort(key=lambda c: c.adjusted_score, reverse=True)
        
        return candidates
    
    def select_best(
        self,
        candidates: List[ScoredCandidate],
        win_prob: float
    ) -> ScoredCandidate:
        """
        最良の行動を選択
        
        Args:
            candidates: スコアリング済み候補リスト
            win_prob: 現在の期待勝率
        
        Returns:
            選択された候補
        """
        adjusted = self.adjust_candidates(candidates, win_prob)
        return adjusted[0] if adjusted else None
    
    def get_mode_description(self, win_prob: float) -> str:
        """デバッグ用のモード説明"""
        mode = self.determine_mode(win_prob)
        
        if mode == RiskMode.SECURE:
            return f"🛡️ Secure Mode (勝率{win_prob:.0%} ≥ {self.config.advantage_threshold:.0%}): リスク回避優先"
        elif mode == RiskMode.GAMBLE:
            return f"🎲 Gamble Mode (勝率{win_prob:.0%} ≤ {self.config.disadvantage_threshold:.0%}): 上振れ狙い"
        else:
            return f"⚖️ Neutral Mode (勝率{win_prob:.0%}): 標準判断"


# ============================================================================
# シングルトン
# ============================================================================

_risk_aware_solver: Optional[RiskAwareSolver] = None

def get_risk_aware_solver() -> RiskAwareSolver:
    """RiskAwareSolver のシングルトンを取得"""
    global _risk_aware_solver
    if _risk_aware_solver is None:
        _risk_aware_solver = RiskAwareSolver()
    return _risk_aware_solver
