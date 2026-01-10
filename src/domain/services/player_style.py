"""
PlayerStyle - 相手のプレイスタイル推定

同じポケモン・同じ盤面でも、プレイヤーによって行動傾向が異なる。
試合中に「この相手はProtect多い」と気づいたら、それを予測に反映させる。

概念:
  試合開始時: prior（一般的な確率）を使用

  試合中: 観測から posterior を更新
    - 相手が2回連続Protectした → Protect prior を上げる
    - 相手が不利対面でも交代しなかった → 交代 prior を下げる

References:
  - Individualized Competitive Behavior: ScienceDirect
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict


# ============================================================================
# PlayerStyle
# ============================================================================

@dataclass
class PlayerStyle:
    """
    相手プレイヤーのスタイル（試合中に推定）
    
    ベイズ的に観測から更新される。
    """
    
    # ============= Protect傾向 =============
    protect_prior: float = 0.15      # 初期確率
    protect_alpha: float = 1.5       # Beta分布の α（成功）
    protect_beta: float = 8.5        # Beta分布の β（失敗）
    protect_observations: int = 0    # 観測回数
    protect_count: int = 0           # Protect使用回数
    
    # ============= 交代傾向 =============
    switch_prior: float = 0.10
    switch_alpha: float = 1.0
    switch_beta: float = 9.0
    switch_observations: int = 0
    switch_count: int = 0
    
    # ============= 集中傾向（同じ相手に2体で攻撃）=============
    focus_prior: float = 0.30
    focus_alpha: float = 3.0
    focus_beta: float = 7.0
    focus_observations: int = 0
    focus_count: int = 0
    
    # ============= 積み/展開傾向（セットアップ技） =============
    setup_prior: float = 0.20
    setup_alpha: float = 2.0
    setup_beta: float = 8.0
    setup_observations: int = 0
    setup_count: int = 0
    
    # ============= ターン履歴 =============
    action_history: List[str] = field(default_factory=list)
    
    def get_protect_prob(self) -> float:
        """
        ベイズ更新後のProtect確率
        
        Beta分布の期待値 = α / (α + β)
        """
        effective_alpha = self.protect_alpha + self.protect_count
        effective_beta = self.protect_beta + (self.protect_observations - self.protect_count)
        
        posterior = effective_alpha / (effective_alpha + effective_beta)
        
        # 範囲を制限（極端な値を避ける）
        return min(0.40, max(0.05, posterior))
    
    def get_switch_prob(self) -> float:
        """ベイズ更新後の交代確率"""
        effective_alpha = self.switch_alpha + self.switch_count
        effective_beta = self.switch_beta + (self.switch_observations - self.switch_count)
        
        posterior = effective_alpha / (effective_alpha + effective_beta)
        return min(0.30, max(0.02, posterior))
    
    def get_focus_prob(self) -> float:
        """ベイズ更新後の集中確率"""
        effective_alpha = self.focus_alpha + self.focus_count
        effective_beta = self.focus_beta + (self.focus_observations - self.focus_count)
        
        posterior = effective_alpha / (effective_alpha + effective_beta)
        return min(0.60, max(0.10, posterior))
    
    def observe_protect(self, did_protect: bool):
        """Protect観測を記録"""
        self.protect_observations += 1
        if did_protect:
            self.protect_count += 1
            self.action_history.append("protect")
        else:
            self.action_history.append("no_protect")
    
    def observe_switch(self, did_switch: bool):
        """交代観測を記録"""
        self.switch_observations += 1
        if did_switch:
            self.switch_count += 1
            self.action_history.append("switch")
        else:
            self.action_history.append("no_switch")
    
    def observe_focus(self, did_focus: bool):
        """集中攻撃観測を記録"""
        self.focus_observations += 1
        if did_focus:
            self.focus_count += 1
            self.action_history.append("focus")
        else:
            self.action_history.append("spread")
    
    def observe_setup(self, did_setup: bool):
        """セットアップ技観測を記録"""
        self.setup_observations += 1
        if did_setup:
            self.setup_count += 1
            self.action_history.append("setup")
    
    def get_style_summary(self) -> str:
        """スタイルのサマリーを取得"""
        protect = self.get_protect_prob()
        switch = self.get_switch_prob()
        focus = self.get_focus_prob()
        
        # スタイル判定
        style_tags = []
        
        if protect > 0.25:
            style_tags.append("慎重派")
        elif protect < 0.10:
            style_tags.append("攻撃的")
        
        if switch > 0.15:
            style_tags.append("サイクル志向")
        elif switch < 0.05:
            style_tags.append("居座り志向")
        
        if focus > 0.45:
            style_tags.append("集中狙い")
        elif focus < 0.20:
            style_tags.append("分散攻撃")
        
        if not style_tags:
            style_tags.append("標準")
        
        return f"スタイル: {', '.join(style_tags)} (P:{protect:.0%} S:{switch:.0%} F:{focus:.0%})"
    
    def to_dict(self) -> Dict[str, float]:
        """辞書形式で取得"""
        return {
            "protect_prob": self.get_protect_prob(),
            "switch_prob": self.get_switch_prob(),
            "focus_prob": self.get_focus_prob(),
            "observations": self.protect_observations + self.switch_observations,
        }


# ============================================================================
# StyleUpdater
# ============================================================================

class StyleUpdater:
    """
    試合中にプレイヤースタイルを更新
    
    BattleMemory と連携し、ターンログからスタイルを推定する。
    """
    
    def __init__(self):
        self.style = PlayerStyle()
    
    def update_from_turn_log(self, turn_log: str):
        """
        ターンログからスタイルを更新
        
        Args:
            turn_log: ターンのログ文字列
        
        ログの例:
          "Miraidon used Protect!"
          "Opponent withdrew Miraidon!"
          "Flutter Mane used Moonblast!"
        """
        log_lower = turn_log.lower()
        
        # Protect検出
        if "used protect" in log_lower or "used detect" in log_lower:
            self.style.observe_protect(True)
            print(f"  📊 スタイル更新: Protect検出 → {self.style.get_style_summary()}")
        
        # 交代検出
        if "withdrew" in log_lower or "switched" in log_lower:
            self.style.observe_switch(True)
            print(f"  📊 スタイル更新: 交代検出 → {self.style.get_style_summary()}")
        
        # セットアップ技検出
        setup_moves = [
            "swords dance", "nasty plot", "calm mind", "dragon dance",
            "quiver dance", "shell smash", "tailwind", "trick room"
        ]
        for move in setup_moves:
            if f"used {move}" in log_lower:
                self.style.observe_setup(True)
                break
    
    def update_from_actions(
        self, 
        opponent_slot0_action: str, 
        opponent_slot1_action: str
    ):
        """
        相手の行動から直接更新
        
        Args:
            opponent_slot0_action: スロット0の行動（"protect", "switch", "攻撃技名"）
            opponent_slot1_action: スロット1の行動
        """
        for action in [opponent_slot0_action, opponent_slot1_action]:
            if not action:
                continue
            
            action_lower = action.lower()
            
            if action_lower in ["protect", "detect"]:
                self.style.observe_protect(True)
            else:
                self.style.observe_protect(False)
            
            if action_lower == "switch":
                self.style.observe_switch(True)
            else:
                self.style.observe_switch(False)
    
    def update_focus_attack(self, both_attacked_same_target: bool):
        """
        集中攻撃を検出
        
        Args:
            both_attacked_same_target: 2体が同じ相手を攻撃したか
        """
        self.style.observe_focus(both_attacked_same_target)
    
    def get_adjusted_priors(self) -> Dict[str, float]:
        """
        OpponentModel 用に調整された prior を取得
        """
        return {
            "protect_prior": self.style.get_protect_prob(),
            "switch_prior": self.style.get_switch_prob(),
            "focus_prior": self.style.get_focus_prob(),
        }
    
    def reset(self):
        """新しい試合のためにリセット"""
        self.style = PlayerStyle()


# ============================================================================
# シングルトン
# ============================================================================

_style_updater: Optional[StyleUpdater] = None

def get_style_updater() -> StyleUpdater:
    """StyleUpdater のシングルトンを取得"""
    global _style_updater
    if _style_updater is None:
        _style_updater = StyleUpdater()
    return _style_updater

def reset_style_updater():
    """新しいバトル開始時にリセット"""
    global _style_updater
    _style_updater = StyleUpdater()
