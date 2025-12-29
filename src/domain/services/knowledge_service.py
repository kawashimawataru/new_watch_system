"""
KnowledgeService: 外部知識を活用した判断支援

PokeLLMon の Knowledge-Augmented Generation (KAG) を参考に、
タイプ相性や技の特性などの知識をAIの判断に活用する。
"""

from typing import Dict, List, Optional, Tuple
from src.domain.models import get_type_effectiveness
from src.domain.models.move import Move


class KnowledgeService:
    """
    ポケモンバトルの知識を提供するサービス
    
    機能:
    1. タイプ相性アドバイス
    2. 先制技の判定
    3. 危険な特性の警告
    4. 天候・フィールド効果の知識
    """
    
    # 危険な特性リスト（対策が必要）
    DANGEROUS_ABILITIES = {
        "intimidate": "攻撃1段階↓",
        "drizzle": "雨を降らせる",
        "drought": "晴れにする",
        "sandstream": "砂嵐を起こす",
        "snowwarning": "雪を降らせる",
        "electricsurge": "エレキフィールド",
        "psychicsurge": "サイコフィールド",
        "grassysurge": "グラスフィールド",
        "mistysurge": "ミストフィールド",
        "prankster": "変化技優先度+1",
        "protean": "技タイプに変化",
        "libero": "技タイプに変化",
        "wonderguard": "効果抜群のみ有効",
        "sturdy": "一撃で倒れない",
        "levitate": "地面無効",
        "flashfire": "炎無効・強化",
        "lightningrod": "電気吸収",
        "stormdrain": "水吸収",
        "sapsipper": "草吸収",
        "motordrive": "電気吸収→素早さ↑",
        "voltabsorb": "電気吸収→回復",
        "waterabsorb": "水吸収→回復",
    }
    
    # 先制技リスト（優先度順）
    PRIORITY_MOVES = {
        # +5
        "helpinghand": 5,
        # +4
        "protect": 4,
        "detect": 4,
        "endure": 4,
        "spikyshield": 4,
        "banefulbunker": 4,
        "silktrap": 4,
        # +3
        "fakeout": 3,
        # +2
        "extremespeed": 2,
        "firstimpression": 2,
        # +1
        "machpunch": 1,
        "bulletpunch": 1,
        "quickattack": 1,
        "shadowsneak": 1,
        "aquajet": 1,
        "iceshard": 1,
        "accelerock": 1,
        "grapplingthrow": 1,
        "ragingbolt": 1,
        "thunderclap": 1,
    }
    
    def get_type_matchup_advice(
        self, 
        move_type: str, 
        defender_types: List[str]
    ) -> Tuple[float, str]:
        """
        タイプ相性のアドバイスを提供
        
        Returns:
            (倍率, アドバイス文)
        """
        effectiveness = 1.0
        for def_type in defender_types:
            effectiveness *= get_type_effectiveness(move_type, def_type)
        
        if effectiveness >= 4.0:
            return effectiveness, "超効果的！4倍ダメージ"
        elif effectiveness >= 2.0:
            return effectiveness, "効果抜群！2倍ダメージ"
        elif effectiveness == 0.0:
            return effectiveness, "無効（タイプ相性）"
        elif effectiveness <= 0.25:
            return effectiveness, "ほとんど効かない（1/4倍）"
        elif effectiveness <= 0.5:
            return effectiveness, "いまひとつ（1/2倍）"
        else:
            return effectiveness, "等倍ダメージ"
    
    def get_priority_level(self, move_name: str) -> int:
        """
        技の優先度を取得
        
        Returns:
            優先度（通常技は0）
        """
        move_id = move_name.lower().replace(" ", "").replace("-", "")
        
        # 既知の先制技
        if move_id in self.PRIORITY_MOVES:
            return self.PRIORITY_MOVES[move_id]
        
        # Move データから取得
        try:
            move = Move(move_id)
            return move.priority
        except:
            return 0
    
    def is_priority_move(self, move_name: str) -> bool:
        """先制技かどうか"""
        return self.get_priority_level(move_name) > 0
    
    def get_ability_warning(self, ability: str) -> Optional[str]:
        """
        危険な特性の警告を取得
        
        Returns:
            警告メッセージ（該当しない場合はNone）
        """
        ability_id = ability.lower().replace(" ", "").replace("-", "")
        return self.DANGEROUS_ABILITIES.get(ability_id)
    
    def get_immunity_types(self, ability: str) -> List[str]:
        """
        特性による無効タイプを取得
        """
        ability_id = ability.lower().replace(" ", "").replace("-", "")
        
        immunities = {
            "levitate": ["Ground"],
            "flashfire": ["Fire"],
            "lightningrod": ["Electric"],
            "stormdrain": ["Water"],
            "sapsipper": ["Grass"],
            "motordrive": ["Electric"],
            "voltabsorb": ["Electric"],
            "waterabsorb": ["Water"],
            "dryskin": ["Water"],
            "eartheater": ["Ground"],
        }
        
        return immunities.get(ability_id, [])
    
    def should_avoid_move(
        self, 
        move_type: str, 
        defender_types: List[str],
        defender_ability: Optional[str]
    ) -> Tuple[bool, str]:
        """
        この技を避けるべきかどうかを判定
        
        タイプ相性や特性による無効化を考慮。
        """
        # タイプ相性チェック
        effectiveness, _ = self.get_type_matchup_advice(move_type, defender_types)
        if effectiveness == 0.0:
            return True, "タイプ相性で無効"
        
        # 特性による無効化チェック
        if defender_ability:
            immunities = self.get_immunity_types(defender_ability)
            if move_type in immunities:
                return True, f"特性 {defender_ability} で無効化"
        
        return False, ""


# シングルトンインスタンス
_knowledge_service: Optional[KnowledgeService] = None

def get_knowledge_service() -> KnowledgeService:
    """KnowledgeService のシングルトンを取得"""
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
