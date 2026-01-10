"""
TacticalMixer - 戦術テンプレートの混合管理

VGC-Bench では、Fictitious Play (FP) や Double Oracle (DO) がベースラインとして整理されている。
このモジュールは重い学習をせずに、複数の戦術テンプレを用意し、
相手に応じて混合比を調整することで運用改善を行う軽量版。

概念:
  戦術テンプレ:
    - TailwindRush: 追い風から高速で押し切る
    - TrickRoom: トリルで低速エースを通す
    - Bulky: 耐久寄りで受けながら削る
    - HyperOffense: 交代読み・集中で押し切る

  試合ごとに:
    1. 相手チーム構成を見て初期比率を決定
    2. 試合中に結果をフィードバック
    3. 次の試合で比率を更新（多腕バンディット的）

References:
  - VGC-Bench: https://arxiv.org/abs/2506.10326
  - UCB (Upper Confidence Bound) for multi-armed bandits
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any


# ============================================================================
# 戦術テンプレート
# ============================================================================

@dataclass
class TacticalTemplate:
    """
    戦術テンプレート
    
    VGCでよく使われる戦術パターンを抽象化したもの。
    """
    name: str
    description: str
    
    # 優先する技カテゴリ
    priority_moves: Set[str] = field(default_factory=set)
    
    # 行動傾向
    protect_rate: float = 0.15      # Protect頻度
    switch_rate: float = 0.10       # 交代頻度
    focus_rate: float = 0.30        # 集中攻撃頻度
    
    # S操作
    speed_control: str = "none"     # "tailwind", "trickroom", "paralysis", "icywind", "none"
    
    # 積み技傾向
    setup_priority: float = 0.0     # 積み技優先度 (0-1)
    
    # 耐久重視度
    bulk_priority: float = 0.0      # 耐久重視度 (0-1)
    
    # 対応する相手傾向（これらがいると有効）
    good_against: Set[str] = field(default_factory=set)
    
    # 苦手な相手傾向
    bad_against: Set[str] = field(default_factory=set)
    
    def get_priority_score(self, move: str) -> float:
        """技の優先度スコアを取得"""
        move_lower = move.lower()
        if move_lower in self.priority_moves:
            return 1.5
        return 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "protect_rate": self.protect_rate,
            "switch_rate": self.switch_rate,
            "focus_rate": self.focus_rate,
            "speed_control": self.speed_control,
        }


# ============================================================================
# デフォルトテンプレート
# ============================================================================

DEFAULT_TEMPLATES = {
    "tailwind_rush": TacticalTemplate(
        name="TailwindRush",
        description="追い風から高速で押し切る",
        priority_moves={"tailwind", "icywind", "protect"},
        protect_rate=0.10,
        switch_rate=0.05,
        focus_rate=0.40,
        speed_control="tailwind",
        setup_priority=0.3,
        good_against={"trickroom", "slow"},
        bad_against={"prankster", "fake_out"},
    ),
    
    "trick_room": TacticalTemplate(
        name="TrickRoom",
        description="トリルで低速エースを通す",
        priority_moves={"trickroom", "protect", "imprison"},
        protect_rate=0.20,
        switch_rate=0.10,
        focus_rate=0.30,
        speed_control="trickroom",
        setup_priority=0.5,
        bulk_priority=0.3,
        good_against={"tailwind", "fast"},
        bad_against={"taunt", "imprison"},
    ),
    
    "bulky_offense": TacticalTemplate(
        name="BulkyOffense",
        description="耐久寄りで受けながら削る",
        priority_moves={"protect", "recover", "leechseed"},
        protect_rate=0.25,
        switch_rate=0.15,
        focus_rate=0.20,
        speed_control="none",
        bulk_priority=0.6,
        good_against={"hyper_offense", "glass_cannon"},
        bad_against={"setup", "trick_room"},
    ),
    
    "hyper_offense": TacticalTemplate(
        name="HyperOffense",
        description="交代読み・集中で圧倒",
        priority_moves={"fakeout", "extremespeed", "suckerpunch"},
        protect_rate=0.05,
        switch_rate=0.05,
        focus_rate=0.50,
        speed_control="none",
        setup_priority=0.1,
        good_against={"setup", "passive"},
        bad_against={"bulky", "intimidate"},
    ),
    
    "weather_control": TacticalTemplate(
        name="WeatherControl",
        description="天候を制して有利を取る",
        priority_moves={"sunnyday", "raindance", "sandstorm", "snowscape", "protect"},
        protect_rate=0.15,
        switch_rate=0.20,
        focus_rate=0.25,
        speed_control="none",
        good_against={"no_weather"},
        bad_against={"weather_setter"},
    ),
    
    "terrain_control": TacticalTemplate(
        name="TerrainControl",
        description="フィールドを制して有利を取る",
        priority_moves={"psychicterrain", "electricterrain", "grassyterrain", "mistyterrain"},
        protect_rate=0.15,
        switch_rate=0.15,
        focus_rate=0.30,
        speed_control="none",
        good_against={"priority"},
        bad_against={"terrain_setter"},
    ),
}


# ============================================================================
# 戦術統計
# ============================================================================

@dataclass
class TacticalStats:
    """戦術の使用統計"""
    name: str
    wins: int = 0
    losses: int = 0
    total: int = 0
    
    @property
    def win_rate(self) -> float:
        if self.total == 0:
            return 0.5  # 未使用は50%とみなす
        return self.wins / self.total
    
    def ucb_score(self, total_trials: int, c: float = 1.414) -> float:
        """
        UCB (Upper Confidence Bound) スコア
        
        探索と活用のバランスを取る。
        c は探索係数（大きい = 未知を優先）
        """
        if self.total == 0:
            return float('inf')  # 未使用は優先
        
        exploitation = self.win_rate
        exploration = c * math.sqrt(math.log(total_trials + 1) / self.total)
        
        return exploitation + exploration


# ============================================================================
# TacticalMixer
# ============================================================================

class TacticalMixer:
    """
    戦術テンプレートの混合管理
    
    多腕バンディット的アプローチで、試合結果から最適な戦術を学習する。
    """
    
    def __init__(
        self, 
        templates: Optional[Dict[str, TacticalTemplate]] = None,
        exploration_rate: float = 0.2
    ):
        """
        Args:
            templates: 戦術テンプレート辞書
            exploration_rate: 探索率（ε-greedy 用）
        """
        self.templates = templates or dict(DEFAULT_TEMPLATES)
        self.exploration_rate = exploration_rate
        
        # 各テンプレの統計
        self.stats: Dict[str, TacticalStats] = {
            name: TacticalStats(name=name) 
            for name in self.templates
        }
        
        # 現在選択中のテンプレ
        self.current_template: Optional[str] = None
    
    def select_template(
        self, 
        opponent_team: Optional[List[str]] = None,
        use_ucb: bool = True
    ) -> TacticalTemplate:
        """
        相手チームに応じてテンプレートを選択
        
        Args:
            opponent_team: 相手チームのポケモン名リスト
            use_ucb: UCBアルゴリズムを使うか（False = ε-greedy）
        
        Returns:
            選択されたテンプレート
        """
        # 相手チームから傾向を推定
        opponent_traits = self._analyze_opponent(opponent_team) if opponent_team else set()
        
        # スコアを計算
        scores: Dict[str, float] = {}
        total_trials = sum(s.total for s in self.stats.values())
        
        for name, template in self.templates.items():
            base_score = 1.0
            
            # 相手との相性を考慮
            for trait in opponent_traits:
                if trait in template.good_against:
                    base_score += 0.3
                if trait in template.bad_against:
                    base_score -= 0.2
            
            if use_ucb:
                # UCBスコア
                ucb = self.stats[name].ucb_score(total_trials)
                scores[name] = base_score * (0.5 + ucb)
            else:
                # ε-greedy
                scores[name] = base_score * (self.stats[name].win_rate + 0.5)
        
        # 探索 or 活用
        if random.random() < self.exploration_rate:
            # 探索: ランダム選択
            selected = random.choice(list(self.templates.keys()))
        else:
            # 活用: 最高スコア
            selected = max(scores.keys(), key=lambda k: scores[k])
        
        self.current_template = selected
        print(f"  🎯 戦術テンプレ選択: {self.templates[selected].name}")
        print(f"     {self.templates[selected].description}")
        
        return self.templates[selected]
    
    def record_result(self, won: bool):
        """
        試合結果を記録
        
        Args:
            won: 勝ったかどうか
        """
        if self.current_template is None:
            return
        
        stats = self.stats[self.current_template]
        stats.total += 1
        if won:
            stats.wins += 1
        else:
            stats.losses += 1
        
        print(f"  📊 戦術結果記録: {self.current_template} {'勝利' if won else '敗北'}")
        print(f"     勝率: {stats.win_rate:.0%} ({stats.wins}勝{stats.losses}敗)")
    
    def get_best_template(self) -> Tuple[str, float]:
        """最も勝率の高いテンプレートを取得"""
        best = max(self.stats.values(), key=lambda s: s.win_rate)
        return (best.name, best.win_rate)
    
    def get_adjusted_priors(self) -> Dict[str, float]:
        """
        OpponentModel 用に調整された prior を取得
        
        現在のテンプレートに基づいて行動傾向を返す。
        """
        if self.current_template is None:
            return {}
        
        template = self.templates[self.current_template]
        return {
            "protect_prior": template.protect_rate,
            "switch_prior": template.switch_rate,
            "focus_prior": template.focus_rate,
        }
    
    def _analyze_opponent(self, opponent_team: List[str]) -> Set[str]:
        """相手チームから傾向を推定"""
        traits = set()
        
        # よくあるポケモンから傾向を推定
        fast_pokemon = {"miraidon", "fluttermane", "ironbundle", "regieleki"}
        slow_pokemon = {"torkoal", "dondozo", "cresselia", "amoonguss"}
        trickroom_setters = {"cresselia", "farigiraf", "porygon2", "dusclops"}
        weather_setters = {"torkoal", "pelipper", "tyranitar", "abomasnow", "politoed"}
        
        team_lower = [p.lower().replace(" ", "").replace("-", "") for p in opponent_team]
        
        for pokemon in team_lower:
            if pokemon in fast_pokemon:
                traits.add("fast")
            if pokemon in slow_pokemon:
                traits.add("slow")
            if pokemon in trickroom_setters:
                traits.add("trickroom")
            if pokemon in weather_setters:
                traits.add("weather_setter")
        
        return traits
    
    def to_summary(self) -> str:
        """統計サマリー"""
        lines = ["=== TacticalMixer Summary ==="]
        
        for name, stats in sorted(self.stats.items(), key=lambda x: -x[1].win_rate):
            template = self.templates[name]
            current = "→" if name == self.current_template else " "
            lines.append(
                f"{current} {template.name}: {stats.win_rate:.0%} "
                f"({stats.wins}W/{stats.losses}L/{stats.total}G)"
            )
        
        return "\n".join(lines)


# ============================================================================
# シングルトン
# ============================================================================

_tactical_mixer: Optional[TacticalMixer] = None

def get_tactical_mixer() -> TacticalMixer:
    """TacticalMixer のシングルトンを取得"""
    global _tactical_mixer
    if _tactical_mixer is None:
        _tactical_mixer = TacticalMixer()
    return _tactical_mixer

def reset_tactical_mixer():
    """新しいセッション開始時にリセット"""
    global _tactical_mixer
    _tactical_mixer = TacticalMixer()
