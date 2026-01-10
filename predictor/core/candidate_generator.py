"""
CandidateGenerator - Top-K候補生成

PokéChamp型アーキテクチャの候補圧縮モジュール。
ルールベース + LLM補助 で Top-K 候補を生成。

References:
- PokéChamp: https://arxiv.org/abs/2503.04094 (action sampling)
- PokeLLMon: https://arxiv.org/abs/2402.01118 (consistent action)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from predictor.engine.simulator_adapter import (
    ActionOrder,
    ActionType,
    JointAction,
    SimulatorAdapter,
    get_simulator,
)

# Phase A-C: 新しいダメージ計算・履歴・相手モデル
try:
    from src.domain.services.damage_calc_service import (
        DamageCalcService, get_damage_calc_service,
        create_pokemon_from_poke_env, create_move_from_poke_env
    )
    from src.domain.services.battle_memory import get_battle_memory
    from src.domain.services.opponent_model import get_opponent_model
    DAMAGE_CALC_AVAILABLE = True
except ImportError:
    DAMAGE_CALC_AVAILABLE = False

try:
    from poke_env.environment.double_battle import DoubleBattle
    from poke_env.environment.move import Move
    from poke_env.environment.pokemon import Pokemon
except ImportError:
    try:
        from poke_env.battle import DoubleBattle, Move, Pokemon
    except ImportError:
        DoubleBattle = None
        Move = None
        Pokemon = None


# ============================================================================
# データ構造
# ============================================================================

@dataclass
class CandidateScore:
    """候補手とそのスコア"""
    action: JointAction
    score: float
    tags: List[str] = field(default_factory=list)
    
    def __lt__(self, other):
        return self.score < other.score


@dataclass
class CandidateConfig:
    """候補生成の設定"""
    top_k: int = 25                    # 最終的な候補数
    moves_per_slot: int = 4            # スロットあたりの技候補数
    switches_per_slot: int = 2         # スロットあたりの交代候補数
    include_tera: bool = True          # テラスタル候補を含めるか
    use_llm: bool = False              # LLM補助を使うか
    llm_top_m: int = 20                # LLM候補数
    rule_top: int = 10                 # ルールベース候補数
    
    # Progressive Widening パラメータ
    # n回目の呼び出しで候補数 = base_k + floor(n / widening_interval) * widening_step
    progressive_widening: bool = True   # Progressive Widening を有効化
    base_k: int = 15                    # 初期候補数
    widening_interval: int = 5          # 何回ごとに候補を増やすか
    widening_step: int = 5              # 増加する候補数
    max_k: int = 100                    # 最大候補数


# ============================================================================
# スコアリング関数
# ============================================================================

class ActionScorer:
    """行動のスコアリング（Phase A-C 統合版）"""
    
    def __init__(self, use_damage_calc: bool = True, battle_memory=None):
        # 重み
        self.damage_weight = 1.0
        self.speed_weight = 0.8
        self.protection_weight = 0.5
        self.penalty_weight = 0.7
        
        # Phase B: BattleMemory（連続Protect回数取得用）
        self.battle_memory = battle_memory
        
        # Phase A: ダメージ計算API
        self.use_damage_calc = use_damage_calc and DAMAGE_CALC_AVAILABLE
        if self.use_damage_calc:
            self.damage_calc = get_damage_calc_service()
        else:
            self.damage_calc = None
    
    def score_joint_action(
        self,
        action: JointAction,
        battle: DoubleBattle,
        side: Literal["self", "opp"] = "self"
    ) -> Tuple[float, List[str]]:
        """
        JointActionをスコアリング
        
        Returns:
            (score, tags)
        """
        score = 0.0
        tags = []
        
        # 各スロットのスコアを計算
        s0, t0 = self._score_single_action(action.slot0, battle, 0, side)
        s1, t1 = self._score_single_action(action.slot1, battle, 1, side)
        
        score = s0 + s1
        tags.extend(t0)
        tags.extend(t1)
        
        # シナジーボーナス
        synergy, synergy_tags = self._synergy_bonus(action, battle, side)
        score += synergy
        tags.extend(synergy_tags)
        
        # ペナルティ
        penalty, penalty_tags = self._penalty(action, battle, side)
        score -= penalty
        tags.extend(penalty_tags)
        
        return score, tags
    
    def _score_single_action(
        self,
        action: ActionOrder,
        battle: DoubleBattle,
        slot: int,
        side: str
    ) -> Tuple[float, List[str]]:
        """単一アクションのスコア"""
        if action.action_type == ActionType.PASS:
            return 0.0, []
        
        if action.action_type == ActionType.SWITCH:
            return self._score_switch(action, battle, slot, side)
        
        if action.action_type in (ActionType.MOVE, ActionType.TERA_MOVE):
            return self._score_move(action, battle, slot, side)
        
        return 0.0, []
    
    def _score_move(
        self,
        action: ActionOrder,
        battle: DoubleBattle,
        slot: int,
        side: str
    ) -> Tuple[float, List[str]]:
        """
        技のスコア（DamageCalcAPI統合版）
        
        Priority 1: ko_prob / expected でスコアリング
        - 1ターンKOが見えるなら ko_prob を最重視
        - 2ターンKOが見えるなら two_turn_ko_prob
        - それ以外は expected（削り）
        """
        score = 0.0
        tags = []
        
        move_id = action.move_id
        if not move_id:
            return 0.0, []
        
        # 高優先度技（まもる、ねこだまし、追い風、トリル等）
        priority_moves = {
            "protect": (0.6, ["protect"]),
            "detect": (0.6, ["protect"]),
            "spikyshield": (0.6, ["protect"]),
            "fakeout": (0.9, ["fakeout", "priority"]),
            "tailwind": (1.0, ["speed", "tailwind"]),
            "trickroom": (1.0, ["speed", "trickroom"]),
            "followme": (0.8, ["redirection"]),
            "ragepowder": (0.8, ["redirection"]),
            "icywind": (0.7, ["speed", "spread"]),
            "electroweb": (0.7, ["speed", "spread"]),
        }
        
        if move_id in priority_moves:
            bonus, move_tags = priority_moves[move_id]
            score += bonus
            tags.extend(move_tags)
        
        # ポケモンと技を取得
        if side == "self":
            pokemon = battle.active_pokemon[slot] if slot < len(battle.active_pokemon) else None
            targets = battle.opponent_active_pokemon
        else:
            pokemon = battle.opponent_active_pokemon[slot] if slot < len(battle.opponent_active_pokemon) else None
            targets = battle.active_pokemon
        
        if not pokemon or not pokemon.moves or move_id not in pokemon.moves:
            return score, tags
        
        move = pokemon.moves[move_id]
        base_power = getattr(move, 'base_power', 0) or 0
        
        # ============= DamageCalcAPI 統合 =============
        if self.use_damage_calc and self.damage_calc and base_power > 0:
            try:
                best_score = 0.0
                best_tags = []
                
                # 各ターゲットに対してダメージ計算
                for target_idx, target in enumerate(targets):
                    if not target or (hasattr(target, 'fainted') and target.fainted):
                        continue
                    
                    # poke-env → PokemonStats 変換
                    attacker_stats = create_pokemon_from_poke_env(pokemon)
                    defender_stats = create_pokemon_from_poke_env(target)
                    move_data = create_move_from_poke_env(move)
                    
                    result = self.damage_calc.calculate(attacker_stats, defender_stats, move_data)
                    
                    if result.is_immune:
                        continue  # 無効なら次のターゲット
                    
                    # スコアリング
                    target_score = 0.0
                    target_tags = []
                    
                    # 優先度: 確殺 > 高乱数 > 2ターンKO > 削り
                    if result.ko_prob >= 0.9:
                        target_score = 2.0 + result.ko_prob  # 確殺: 2.9~3.0
                        target_tags.append("確殺")
                    elif result.ko_prob >= 0.5:
                        target_score = 1.5 + result.ko_prob * 0.5  # 高乱数: 1.75~2.0
                        target_tags.append("高乱数")
                    elif result.two_turn_ko_prob >= 0.8:
                        target_score = 1.0 + result.two_turn_ko_prob * 0.5  # 確2: 1.4~1.5
                        target_tags.append("確2")
                    else:
                        target_score = result.expected / 100.0  # 削り: 0.0~1.0
                        target_tags.append(f"{result.expected:.0f}%削り")
                    
                    # タイプ相性ボーナス
                    if result.type_effectiveness >= 2.0:
                        target_score *= 1.2
                        target_tags.append("抜群")
                    
                    if target_score > best_score:
                        best_score = target_score
                        best_tags = target_tags
                
                score += best_score * self.damage_weight
                tags.extend(best_tags)
                
            except Exception as e:
                # DamageCalc失敗時はフォールバック
                if base_power > 0:
                    score += base_power / 100.0 * self.damage_weight
                    if base_power >= 100:
                        tags.append("high_power")
        else:
            # DamageCalc無効時は従来の簡易計算
            if base_power > 0:
                score += base_power / 100.0 * self.damage_weight
                if base_power >= 100:
                    tags.append("high_power")
                
                # 全体技ボーナス
                target = getattr(move, 'target', 'normal')
                if target in ('allAdjacentFoes', 'allAdjacent'):
                    score += 0.3
                    tags.append("spread")
        
        # テラスタル使用時のボーナス
        if action.action_type == ActionType.TERA_MOVE:
            score += 0.4
            tags.append("tera")
        
        return score, tags
    
    def _score_switch(
        self,
        action: ActionOrder,
        battle: DoubleBattle,
        slot: int,
        side: str
    ) -> Tuple[float, List[str]]:
        """交代のスコア"""
        score = 0.3  # 交代の基本スコア
        tags = ["switch"]
        
        # 現在のポケモンが瀕死/危険な場合はボーナス
        if side == "self" and slot < len(battle.active_pokemon):
            current = battle.active_pokemon[slot]
            if current and current.current_hp_fraction < 0.3:
                score += 0.4
                tags.append("escape")
        
        return score, tags
    
    def _synergy_bonus(
        self,
        action: JointAction,
        battle: DoubleBattle,
        side: str
    ) -> Tuple[float, List[str]]:
        """2体のシナジーボーナス"""
        bonus = 0.0
        tags = []
        
        a0, a1 = action.slot0, action.slot1
        
        # このゆび + 集中攻撃
        if (a0.move_id in ("followme", "ragepowder") or 
            a1.move_id in ("followme", "ragepowder")):
            # もう一方が攻撃技なら bonus
            other = a1 if a0.move_id in ("followme", "ragepowder") else a0
            if other.action_type == ActionType.MOVE:
                bonus += 0.4
                tags.append("redirection_combo")
        
        # 追い風/トリル + 高速/低速アタッカー
        if a0.move_id in ("tailwind", "trickroom") or a1.move_id in ("tailwind", "trickroom"):
            bonus += 0.3
            tags.append("speed_setup")
        
        # ダブル攻撃（同じ相手に集中）
        if (a0.action_type == ActionType.MOVE and a1.action_type == ActionType.MOVE and
            a0.target == a1.target and a0.target is not None and a0.target < 0):
            bonus += 0.5
            tags.append("double_target")
        
        return bonus, tags
    
    def _penalty(
        self,
        action: JointAction,
        battle: DoubleBattle,
        side: str
    ) -> Tuple[float, List[str]]:
        """ペナルティ（consistent action思想）"""
        penalty = 0.0
        tags = []
        
        a0, a1 = action.slot0, action.slot1
        
        # 守る系技のリスト
        protect_moves = {"protect", "detect", "spikyshield", "banefulbunker", "silktrap", "kingsshield", "obstruct", "burningbulwark"}
        
        # ========================
        # 2連守確率ペナルティ（BattleMemory連動）
        # ========================
        # 連続成功確率: 1回目100% → 2回目33% → 3回目11%
        # 期待値: 2回目は 0.33、3回目は 0.11
        # → 2連守以降は (1 - success_prob) をペナルティとして加算
        
        # 各スロットの連続Protect回数を取得してペナルティ
        for slot_idx, order in enumerate([a0, a1]):
            if order.move_id in protect_moves:
                consecutive = 0
                if self.battle_memory and side == "self":
                    # 自分のポケモン名を取得
                    if slot_idx < len(battle.active_pokemon) and battle.active_pokemon[slot_idx]:
                        species = battle.active_pokemon[slot_idx].species
                        consecutive = self.battle_memory.get_consecutive_protects(species, is_opponent=False)
                
                if consecutive >= 1:
                    # 2連守以降: 成功確率低下に応じたペナルティ
                    success_prob = 1.0 / (3 ** consecutive)  # 33%, 11%, 3.7%...
                    fail_penalty = (1.0 - success_prob) * 3.0  # 強めのペナルティ
                    penalty += fail_penalty
                    tags.append(f"consecutive_protect_{consecutive+1}")
        
        # 両方まもるはさらにペナルティ（守る連打抑制）
        if a0.move_id in protect_moves and a1.move_id in protect_moves:
            penalty += 1.0
            tags.append("double_protect_penalty")
        
        # 意味のない交代（HP満タンで交代）
        if a0.action_type == ActionType.SWITCH:
            if side == "self" and len(battle.active_pokemon) > 0:
                current = battle.active_pokemon[0]
                if current and current.current_hp_fraction > 0.8:
                    penalty += 0.3
                    tags.append("unnecessary_switch")
        
        if a1.action_type == ActionType.SWITCH:
            if side == "self" and len(battle.active_pokemon) > 1:
                current = battle.active_pokemon[1]
                if current and current.current_hp_fraction > 0.8:
                    penalty += 0.3
                    tags.append("unnecessary_switch")
        
        # 味方殴り（基本はペナルティ）
        if a0.action_type == ActionType.MOVE and a0.target and a0.target > 0:
            penalty += 0.8
            tags.append("ally_attack")
        if a1.action_type == ActionType.MOVE and a1.target and a1.target > 0:
            penalty += 0.8
            tags.append("ally_attack")
        
        return penalty, tags


# ============================================================================
# CandidateGenerator
# ============================================================================

class CandidateGenerator:
    """
    Top-K候補生成器
    
    1. SimulatorAdapterで全合法手を列挙
    2. ルールベースでスコアリング
    3. (Optional) LLMで補助
    4. Top-Kに圧縮
    """
    
    def __init__(
        self,
        config: Optional[CandidateConfig] = None,
        llm_client: Optional[Any] = None,
        battle_memory=None,
    ):
        self.config = config or CandidateConfig()
        self.llm = llm_client
        self.simulator = get_simulator()
        self.battle_memory = battle_memory
        self.scorer = ActionScorer(battle_memory=battle_memory)
        
        # Progressive Widening: 呼び出し回数カウンタ
        self._call_count = 0
    
    def generate(
        self,
        battle: DoubleBattle,
        side: Literal["self", "opp"] = "self",
        top_k: Optional[int] = None,
    ) -> List[CandidateScore]:
        """
        Top-K候補を生成（Progressive Widening 対応）
        
        Args:
            battle: 現在のバトル状態
            side: "self" または "opp"
            top_k: 候補数（Noneならconfig値）
            
        Returns:
            スコア降順のCandidateScoreリスト
        """
        # ===== Progressive Widening =====
        # 呼び出し回数に応じて候補数を動的に増加
        self._call_count += 1
        
        if top_k is None:
            if self.config.progressive_widening:
                # 候補数 = base_k + floor(call_count / interval) * step
                additional = (self._call_count // self.config.widening_interval) * self.config.widening_step
                top_k = min(self.config.base_k + additional, self.config.max_k)
            else:
                top_k = self.config.top_k
        
        # 1. 全合法手を列挙
        all_actions = self.simulator.enumerate_legal_joint_actions(battle, side)
        
        if not all_actions:
            return []
        
        # 2. ルールベースでスコアリング
        candidates = []
        for action in all_actions:
            score, tags = self.scorer.score_joint_action(action, battle, side)
            candidates.append(CandidateScore(action, score, tags))
        
        # 3. スコア降順でソート
        candidates.sort(reverse=True)
        
        # 4. Top-Kに圧縮
        top_candidates = candidates[:top_k]
        
        # 5. (Future) LLM補助があればマージ
        if self.config.use_llm and self.llm:
            # TODO: LLM候補生成
            pass
        
        return top_candidates
    
    def generate_for_both(
        self,
        battle: DoubleBattle,
        top_k: Optional[int] = None,
    ) -> Tuple[List[CandidateScore], List[CandidateScore]]:
        """
        自分と相手両方の候補を生成
        
        Returns:
            (self_candidates, opp_candidates)
        """
        self_candidates = self.generate(battle, "self", top_k)
        opp_candidates = self.generate(battle, "opp", top_k)
        return self_candidates, opp_candidates


# ============================================================================
# シングルトン
# ============================================================================

_generator: Optional[CandidateGenerator] = None

def get_candidate_generator(battle_memory=None) -> CandidateGenerator:
    """CandidateGeneratorのシングルトンを取得"""
    global _generator
    if _generator is None:
        _generator = CandidateGenerator(battle_memory=battle_memory)
    elif battle_memory is not None and _generator.battle_memory is None:
        # battle_memory が後から設定された場合、更新
        _generator.battle_memory = battle_memory
        _generator.scorer.battle_memory = battle_memory
    return _generator
