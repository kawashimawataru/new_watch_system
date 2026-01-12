"""
Type Calculator - LLM用タイプ相性マトリクス生成

BattleStateから全ての攻撃・防御の組み合わせを計算し、
LLMが理解しやすい形式で出力する。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from src.domain.models.type_chart import (
    get_type_effectiveness, 
    get_effectiveness_label,
    TYPE_CHART,
    TYPE_NAMES_JP,
)


@dataclass
class TypeMatchup:
    """個別のタイプ相性情報"""
    attacker: str           # 攻撃側ポケモン名
    move_type: str          # 技のタイプ
    defender: str           # 防御側ポケモン名
    effectiveness: float    # 倍率 (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
    label: str              # "無効", "いまひとつ", "等倍", "効果ばつぐん"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "attacker": self.attacker,
            "move_type": self.move_type,
            "defender": self.defender,
            "effectiveness": self.effectiveness,
            "label": self.label,
        }


@dataclass
class TypeMatchupMatrix:
    """全体のタイプ相性マトリクス"""
    player_attacks: List[TypeMatchup] = field(default_factory=list)
    opponent_attacks: List[TypeMatchup] = field(default_factory=list)
    key_interactions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_attacks": [m.to_dict() for m in self.player_attacks],
            "opponent_attacks": [m.to_dict() for m in self.opponent_attacks],
            "key_interactions": self.key_interactions,
        }
    
    def to_summary_text(self) -> str:
        """LLM用のサマリーテキスト"""
        lines = []
        
        # Player攻撃
        lines.append("【自分の攻撃】")
        for m in self.player_attacks:
            if m.effectiveness >= 2.0:
                lines.append(f"  ✅ {m.attacker}の{m.move_type} → {m.defender}: {m.label} (x{m.effectiveness})")
            elif m.effectiveness == 0.0:
                lines.append(f"  ❌ {m.attacker}の{m.move_type} → {m.defender}: {m.label}")
            elif m.effectiveness < 1.0:
                lines.append(f"  ⚠️ {m.attacker}の{m.move_type} → {m.defender}: {m.label} (x{m.effectiveness})")
        
        # Opponent攻撃
        lines.append("【相手の攻撃】")
        for m in self.opponent_attacks:
            if m.effectiveness >= 2.0:
                lines.append(f"  🔴 {m.attacker}の{m.move_type} → {m.defender}: {m.label} (x{m.effectiveness})")
            elif m.effectiveness == 0.0:
                lines.append(f"  🛡️ {m.attacker}の{m.move_type} → {m.defender}: {m.label}")
            elif m.effectiveness < 1.0:
                lines.append(f"  ✅ {m.attacker}の{m.move_type} → {m.defender}: {m.label} (x{m.effectiveness})")
        
        # Key Interactions
        if self.key_interactions:
            lines.append("【重要な相性】")
            for interaction in self.key_interactions:
                lines.append(f"  • {interaction}")
        
        return "\n".join(lines)


class TypeCalculator:
    """
    LLM用のタイプ相性計算サービス
    
    BattleStateの全ポケモン・技のタイプ相性をマトリクス化する。
    """
    
    # 既知の技タイプマッピング (よく使う技)
    COMMON_MOVE_TYPES: Dict[str, str] = {
        "protect": "Normal",
        "fakeout": "Normal",
        "extremespeed": "Normal",
        "drainpunch": "Fighting",
        "closecombat": "Fighting",
        "infernape": "Fire",        # これは技じゃない、削除対象
        "flareblitz": "Fire",
        "heatwave": "Fire",
        "overheat": "Fire",
        "hydropump": "Water",
        "surf": "Water",
        "muddywater": "Water",
        "surgingstrikes": "Water",
        "thunderbolt": "Electric",
        "voltswitch": "Electric",
        "leafblade": "Grass",
        "energyball": "Grass",
        "iceshard": "Ice",
        "iciclecrash": "Ice",
        "blizzard": "Ice",
        "earthquake": "Ground",
        "earthpower": "Ground",
        "highhorsepower": "Ground",
        "bravebird": "Flying",
        "hurricane": "Flying",
        "psychic": "Psychic",
        "expandingforce": "Psychic",
        "pollenpuff": "Bug",
        "uturn": "Bug",
        "rockslide": "Rock",
        "stoneedge": "Rock",
        "shadowball": "Ghost",
        "astralbarrage": "Ghost",
        "dracometeor": "Dragon",
        "dragonpulse": "Dragon",
        "darkpulse": "Dark",
        "knockoff": "Dark",
        "suckerpunch": "Dark",
        "ironhead": "Steel",
        "flashcannon": "Steel",
        "moonblast": "Fairy",
        "playrough": "Fairy",
        "dazzlinggleam": "Fairy",
    }
    
    @classmethod
    def _get_effectiveness_label(cls, eff: float) -> str:
        if eff == 0.0:
            return "無効"
        elif eff < 1.0:
            return "いまひとつ"
        elif eff == 1.0:
            return "等倍"
        else:
            return "効果抜群"
    
    @classmethod
    def calculate_matchup(
        cls,
        attacker_name: str,
        move_type: str,
        defender_name: str,
        defender_types: List[str]
    ) -> TypeMatchup:
        """
        単一の攻撃に対するタイプ相性を計算
        """
        eff = get_type_effectiveness(move_type, defender_types)
        label = cls._get_effectiveness_label(eff)
        
        return TypeMatchup(
            attacker=attacker_name,
            move_type=move_type,
            defender=defender_name,
            effectiveness=eff,
            label=label,
        )
    
    @classmethod
    def build_matrix_from_state(
        cls,
        player_pokemon: List[Dict[str, Any]],
        opponent_pokemon: List[Dict[str, Any]],
    ) -> TypeMatchupMatrix:
        """
        BattleStateからタイプ相性マトリクスを構築
        
        Args:
            player_pokemon: 自分のポケモンリスト (name, types, moves)
            opponent_pokemon: 相手のポケモンリスト  
        
        Returns:
            TypeMatchupMatrix
        """
        matrix = TypeMatchupMatrix()
        
        # 自分の攻撃 → 相手
        for attacker in player_pokemon:
            attacker_name = attacker.get("name", "Unknown")
            moves = attacker.get("moves", [])
            
            for move in moves:
                move_name = move.get("name", "").lower().replace(" ", "").replace("-", "")
                move_type = move.get("type") or cls.COMMON_MOVE_TYPES.get(move_name, "Normal")
                
                for defender in opponent_pokemon:
                    defender_name = defender.get("name", "Unknown")
                    defender_types = defender.get("types", ["Normal"])
                    
                    matchup = cls.calculate_matchup(
                        attacker_name, move_type, defender_name, defender_types
                    )
                    
                    # 重要なもののみ記録 (効果抜群 or 無効)
                    if matchup.effectiveness >= 2.0 or matchup.effectiveness == 0.0:
                        matrix.player_attacks.append(matchup)
        
        # 相手の攻撃 → 自分
        for attacker in opponent_pokemon:
            attacker_name = attacker.get("name", "Unknown")
            moves = attacker.get("moves", [])
            
            for move in moves:
                move_name = move.get("name", "").lower().replace(" ", "").replace("-", "")
                move_type = move.get("type") or cls.COMMON_MOVE_TYPES.get(move_name, "Normal")
                
                for defender in player_pokemon:
                    defender_name = defender.get("name", "Unknown")
                    defender_types = defender.get("types", ["Normal"])
                    
                    matchup = cls.calculate_matchup(
                        attacker_name, move_type, defender_name, defender_types
                    )
                    
                    if matchup.effectiveness >= 2.0 or matchup.effectiveness == 0.0:
                        matrix.opponent_attacks.append(matchup)
        
        # Key Interactions を抽出
        matrix.key_interactions = cls._extract_key_interactions(matrix)
        
        return matrix
    
    @classmethod
    def _extract_key_interactions(cls, matrix: TypeMatchupMatrix) -> List[str]:
        """重要な相性関係を自然言語で抽出"""
        interactions = []
        
        # 4倍弱点
        for m in matrix.opponent_attacks:
            if m.effectiveness >= 4.0:
                interactions.append(f"{m.defender}は{m.attacker}の{m.move_type}技で4倍弱点を突かれる")
        
        # 無効化
        for m in matrix.player_attacks:
            if m.effectiveness == 0.0:
                interactions.append(f"{m.defender}は{m.move_type}を無効化する")
        
        for m in matrix.opponent_attacks:
            if m.effectiveness == 0.0:
                interactions.append(f"{m.defender}は{m.attacker}の{m.move_type}を無効化できる")
        
        return interactions[:5]  # 最大5件


# Singleton
_type_calculator = None

def get_type_calculator() -> TypeCalculator:
    global _type_calculator
    if _type_calculator is None:
        _type_calculator = TypeCalculator()
    return _type_calculator
