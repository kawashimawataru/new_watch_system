"""
Board Evaluator - 盤面評価関数

将棋/チェスの評価関数を参考に、VGCダブルバトルの盤面スコアを計算。

評価項目:
1. HP残量（駒の価値に相当）
2. 数的有利（駒数差）
3. タイプ有利度（盤面支配度）
4. 脅威度（相手からの圧力）
5. ポジション価値（テラスタル残数、追い風など）
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import math

from src.domain.models.type_chart import get_type_effectiveness


@dataclass
class BoardScore:
    """盤面評価スコア"""
    total: float                 # 総合スコア (-1.0 ~ 1.0, 正が自分有利)
    hp_advantage: float          # HP有利度
    count_advantage: float       # 数的有利
    type_advantage: float        # タイプ有利度
    threat_level: float          # 被脅威度（負の値ほど危険）
    position_value: float        # ポジション価値
    details: Dict[str, Any]      # 詳細情報
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": round(self.total, 3),
            "hp_advantage": round(self.hp_advantage, 3),
            "count_advantage": round(self.count_advantage, 3),
            "type_advantage": round(self.type_advantage, 3),
            "threat_level": round(self.threat_level, 3),
            "position_value": round(self.position_value, 3),
            "details": self.details,
        }


class BoardEvaluator:
    """
    盤面評価器
    
    将棋/チェスの評価関数スタイル:
    - 駒の価値(HP) + 駒の配置(タイプ相性) + キングの安全性(被脅威度)
    """
    
    # 重み係数（チューニング可能）
    WEIGHTS = {
        "hp": 0.35,           # HP有利度の重み
        "count": 0.25,        # 数的有利の重み
        "type": 0.20,         # タイプ有利度の重み
        "threat": 0.10,       # 被脅威度の重み
        "position": 0.10,     # ポジション価値の重み
    }
    
    # ポケモンの基礎価値（役割による）
    ROLE_VALUES = {
        "sweeper": 1.2,       # アタッカー
        "tank": 1.0,          # 耐久
        "support": 0.9,       # サポート
        "default": 1.0,
    }
    
    @classmethod
    def evaluate(
        cls,
        player_pokemon: List[Dict[str, Any]],
        opponent_pokemon: List[Dict[str, Any]],
        field_state: Dict[str, Any] = None,
    ) -> BoardScore:
        """
        盤面を評価してスコアを返す
        
        Args:
            player_pokemon: 自分のポケモン (name, hp_fraction, types, moves, etc.)
            opponent_pokemon: 相手のポケモン
            field_state: フィールド状態
        
        Returns:
            BoardScore: -1.0(自分不利) ~ 1.0(自分有利)
        """
        field_state = field_state or {}
        
        # 各評価項目を計算
        hp_adv = cls._evaluate_hp_advantage(player_pokemon, opponent_pokemon)
        count_adv = cls._evaluate_count_advantage(player_pokemon, opponent_pokemon)
        type_adv = cls._evaluate_type_advantage(player_pokemon, opponent_pokemon)
        threat = cls._evaluate_threat_level(player_pokemon, opponent_pokemon)
        position = cls._evaluate_position_value(player_pokemon, opponent_pokemon, field_state)
        
        # 重み付き合計
        total = (
            cls.WEIGHTS["hp"] * hp_adv +
            cls.WEIGHTS["count"] * count_adv +
            cls.WEIGHTS["type"] * type_adv +
            cls.WEIGHTS["threat"] * threat +
            cls.WEIGHTS["position"] * position
        )
        
        # -1.0 ~ 1.0 にクリップ
        total = max(-1.0, min(1.0, total))
        
        return BoardScore(
            total=total,
            hp_advantage=hp_adv,
            count_advantage=count_adv,
            type_advantage=type_adv,
            threat_level=threat,
            position_value=position,
            details={
                "player_total_hp": sum(p.get("hp_fraction", 1.0) for p in player_pokemon),
                "opponent_total_hp": sum(p.get("hp_fraction", 1.0) for p in opponent_pokemon),
            },
        )
    
    @classmethod
    def _evaluate_hp_advantage(
        cls,
        player: List[Dict],
        opponent: List[Dict],
    ) -> float:
        """HP有利度を計算 (-1.0 ~ 1.0)"""
        player_hp = sum(
            p.get("hp_fraction", 1.0) * cls._get_pokemon_value(p)
            for p in player if not p.get("fainted", False)
        )
        opponent_hp = sum(
            p.get("hp_fraction", 1.0) * cls._get_pokemon_value(p)
            for p in opponent if not p.get("fainted", False)
        )
        
        total = player_hp + opponent_hp
        if total == 0:
            return 0.0
        
        # 差分を正規化
        return (player_hp - opponent_hp) / max(total, 1.0)
    
    @classmethod
    def _evaluate_count_advantage(
        cls,
        player: List[Dict],
        opponent: List[Dict],
    ) -> float:
        """数的有利を計算 (-1.0 ~ 1.0)"""
        player_alive = sum(1 for p in player if not p.get("fainted", False))
        opponent_alive = sum(1 for p in opponent if not p.get("fainted", False))
        
        # 最大6匹として正規化
        diff = player_alive - opponent_alive
        return diff / 6.0
    
    @classmethod
    def _evaluate_type_advantage(
        cls,
        player: List[Dict],
        opponent: List[Dict],
    ) -> float:
        """タイプ有利度を計算"""
        player_advantage = 0.0
        opponent_advantage = 0.0
        
        # 自分のポケモンが相手にどれだけ有利か
        for p in player:
            if p.get("fainted", False):
                continue
            for o in opponent:
                if o.get("fainted", False):
                    continue
                # 攻撃側の有利度
                for move in p.get("moves", []):
                    move_type = move.get("type", "Normal")
                    eff = get_type_effectiveness(move_type, o.get("types", ["Normal"]))
                    if eff >= 2.0:
                        player_advantage += 0.2
                    elif eff == 0.0:
                        opponent_advantage += 0.1  # 無効化されるのは不利
        
        # 相手側も同様に計算
        for o in opponent:
            if o.get("fainted", False):
                continue
            for p in player:
                if p.get("fainted", False):
                    continue
                for move in o.get("moves", []):
                    move_type = move.get("type", "Normal")
                    eff = get_type_effectiveness(move_type, p.get("types", ["Normal"]))
                    if eff >= 2.0:
                        opponent_advantage += 0.2
        
        # 正規化
        diff = player_advantage - opponent_advantage
        return max(-1.0, min(1.0, diff))
    
    @classmethod
    def _evaluate_threat_level(
        cls,
        player: List[Dict],
        opponent: List[Dict],
    ) -> float:
        """被脅威度を計算（負ほど危険）"""
        threat = 0.0
        
        for p in player:
            if p.get("fainted", False):
                continue
            hp = p.get("hp_fraction", 1.0)
            
            # HPが低いポケモンは脅威が高い
            if hp <= 0.25:
                threat -= 0.3
            elif hp <= 0.5:
                threat -= 0.1
            
            # 相手から弱点を突かれるか
            for o in opponent:
                if o.get("fainted", False):
                    continue
                for move in o.get("moves", []):
                    eff = get_type_effectiveness(
                        move.get("type", "Normal"),
                        p.get("types", ["Normal"])
                    )
                    if eff >= 2.0:
                        threat -= 0.15
                        break
        
        return max(-1.0, min(0.5, threat))
    
    @classmethod
    def _evaluate_position_value(
        cls,
        player: List[Dict],
        opponent: List[Dict],
        field_state: Dict,
    ) -> float:
        """ポジション価値を計算"""
        value = 0.0
        
        # テラスタル残数
        if field_state.get("player_terastal_available", True):
            value += 0.15
        if field_state.get("opponent_terastal_available", True):
            value -= 0.10
        
        # 追い風
        if field_state.get("tailwind_player", False):
            value += 0.20
        if field_state.get("tailwind_opponent", False):
            value -= 0.15
        
        # トリックルーム（状況による）
        if field_state.get("trick_room", False):
            # 自分が遅いチームなら有利
            player_slow = sum(1 for p in player if p.get("speed", 100) < 80)
            if player_slow >= 2:
                value += 0.15
            else:
                value -= 0.10
        
        return max(-0.5, min(0.5, value))
    
    @classmethod
    def _get_pokemon_value(cls, pokemon: Dict) -> float:
        """ポケモンの価値を取得"""
        role = pokemon.get("role", "default")
        return cls.ROLE_VALUES.get(role, 1.0)


# Singleton
_board_evaluator = None

def get_board_evaluator() -> BoardEvaluator:
    global _board_evaluator
    if _board_evaluator is None:
        _board_evaluator = BoardEvaluator()
    return _board_evaluator
