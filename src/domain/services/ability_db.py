"""
Ability Database - 特性データベース

VGCで重要な特性の効果を定義。
ダメージ計算・行動順序・戦術判断に使用。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class AbilityInfo:
    """特性情報"""
    name: str                   # 英語名
    japanese_name: str          # 日本語名
    effect: str                 # 効果の簡潔な説明
    
    # 戦闘への影響
    speed_modifier: Optional[str] = None  # "double_in_sun", "double_in_rain", etc.
    damage_modifier: float = 1.0          # ダメージ倍率 (Huge Power等)
    priority_modifier: int = 0            # 優先度修正 (Prankster等)
    
    # 耐性・免疫
    immune_types: List[str] = None        # 無効化するタイプ
    immune_effects: List[str] = None      # 無効化する効果 (怯み等)
    
    # 天候・フィールド
    sets_weather: Optional[str] = None    # 発動する天候
    sets_terrain: Optional[str] = None    # 発動するフィールド
    
    # その他
    key_notes: List[str] = None
    
    def __post_init__(self):
        if self.immune_types is None:
            self.immune_types = []
        if self.immune_effects is None:
            self.immune_effects = []
        if self.key_notes is None:
            self.key_notes = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "japanese_name": self.japanese_name,
            "effect": self.effect,
            "speed_modifier": self.speed_modifier,
            "damage_modifier": self.damage_modifier,
            "priority_modifier": self.priority_modifier,
            "immune_types": self.immune_types,
            "immune_effects": self.immune_effects,
        }


# VGCで重要な特性のデータベース
ABILITY_DATABASE: Dict[str, AbilityInfo] = {
    # --- 天候特性 ---
    "drought": AbilityInfo(
        name="drought", japanese_name="ひでり", 
        effect="場に出ると5ターン晴れになる",
        sets_weather="sun"
    ),
    "drizzle": AbilityInfo(
        name="drizzle", japanese_name="あめふらし",
        effect="場に出ると5ターン雨になる", 
        sets_weather="rain"
    ),
    "sandstream": AbilityInfo(
        name="sandstream", japanese_name="すなおこし",
        effect="場に出ると5ターン砂嵐になる",
        sets_weather="sand"
    ),
    "snowwarning": AbilityInfo(
        name="snowwarning", japanese_name="ゆきふらし",
        effect="場に出ると5ターン雪になる",
        sets_weather="snow"
    ),
    "orichalcumpulse": AbilityInfo(
        name="orichalcumpulse", japanese_name="ひひいろのこどう",
        effect="場に出ると晴れ、晴れ時に攻撃1.33倍",
        sets_weather="sun", damage_modifier=1.33
    ),
    "hadronengine": AbilityInfo(
        name="hadronengine", japanese_name="ハドロンエンジン",
        effect="場に出るとエレキフィールド、フィールド時に特攻1.33倍",
        sets_terrain="electric", damage_modifier=1.33
    ),
    
    # --- 素早さ関連 ---
    "swiftswim": AbilityInfo(
        name="swiftswim", japanese_name="すいすい",
        effect="雨のとき素早さ2倍",
        speed_modifier="double_in_rain"
    ),
    "chlorophyll": AbilityInfo(
        name="chlorophyll", japanese_name="ようりょくそ",
        effect="晴れのとき素早さ2倍",
        speed_modifier="double_in_sun"
    ),
    "sandrush": AbilityInfo(
        name="sandrush", japanese_name="すなかき",
        effect="砂嵐のとき素早さ2倍",
        speed_modifier="double_in_sand"
    ),
    "slushrush": AbilityInfo(
        name="slushrush", japanese_name="ゆきかき",
        effect="雪のとき素早さ2倍",
        speed_modifier="double_in_snow"
    ),
    "unburden": AbilityInfo(
        name="unburden", japanese_name="かるわざ",
        effect="持ち物がなくなると素早さ2倍",
        speed_modifier="double_on_item_loss"
    ),
    
    # --- 優先度関連 ---
    "prankster": AbilityInfo(
        name="prankster", japanese_name="いたずらごころ",
        effect="変化技の優先度+1。あくタイプには効かない",
        priority_modifier=1,
        key_notes=["あくタイプに変化技が当たらない"]
    ),
    "galewings": AbilityInfo(
        name="galewings", japanese_name="はやてのつばさ",
        effect="HP満タン時、ひこう技の優先度+1",
        priority_modifier=1,
        key_notes=["HP満タン時のみ"]
    ),
    
    # --- 火力アップ ---
    "hugepower": AbilityInfo(
        name="hugepower", japanese_name="ちからもち",
        effect="攻撃が2倍になる",
        damage_modifier=2.0
    ),
    "purepower": AbilityInfo(
        name="purepower", japanese_name="ヨガパワー",
        effect="攻撃が2倍になる",
        damage_modifier=2.0
    ),
    "adaptability": AbilityInfo(
        name="adaptability", japanese_name="てきおうりょく",
        effect="タイプ一致ボーナスが1.5倍→2倍になる",
        damage_modifier=1.33  # STAB 2.0/1.5
    ),
    "transistor": AbilityInfo(
        name="transistor", japanese_name="トランジスタ",
        effect="でんき技の威力1.5倍",
        damage_modifier=1.5,
        key_notes=["レジエレキ専用"]
    ),
    "dragonsmaw": AbilityInfo(
        name="dragonsmaw", japanese_name="りゅうのあぎと",
        effect="ドラゴン技の威力1.5倍",
        damage_modifier=1.5,
        key_notes=["レジドラゴ専用"]
    ),
    "gorillatactics": AbilityInfo(
        name="gorillatactics", japanese_name="ごりむちゅう",
        effect="攻撃1.5倍だが同じ技しか出せない",
        damage_modifier=1.5,
        key_notes=["こだわりハチマキと同効果"]
    ),
    
    # --- 耐性・免疫 ---
    "levitate": AbilityInfo(
        name="levitate", japanese_name="ふゆう",
        effect="じめん技を無効化",
        immune_types=["Ground"]
    ),
    "flashfire": AbilityInfo(
        name="flashfire", japanese_name="もらいび",
        effect="ほのお技を受けると無効化し、自分のほのお技威力1.5倍",
        immune_types=["Fire"]
    ),
    "waterabsorb": AbilityInfo(
        name="waterabsorb", japanese_name="ちょすい",
        effect="みず技を受けるとHPを1/4回復",
        immune_types=["Water"]
    ),
    "stormdrain": AbilityInfo(
        name="stormdrain", japanese_name="よびみず",
        effect="みず技を引き寄せ、特攻+1",
        immune_types=["Water"]
    ),
    "lightningrod": AbilityInfo(
        name="lightningrod", japanese_name="ひらいしん",
        effect="でんき技を引き寄せ、特攻+1",
        immune_types=["Electric"]
    ),
    "sapsipper": AbilityInfo(
        name="sapsipper", japanese_name="そうしょく",
        effect="くさ技を受けると無効化し、攻撃+1",
        immune_types=["Grass"]
    ),
    "innerfocus": AbilityInfo(
        name="innerfocus", japanese_name="せいしんりょく",
        effect="怯まない、いかくを受けない",
        immune_effects=["flinch", "intimidate"]
    ),
    "oblivious": AbilityInfo(
        name="oblivious", japanese_name="どんかん",
        effect="メロメロ・ちょうはつ無効、いかくを受けない",
        immune_effects=["attract", "taunt", "intimidate"]
    ),
    
    # --- いかく・威嚇対策 ---
    "intimidate": AbilityInfo(
        name="intimidate", japanese_name="いかく",
        effect="場に出ると相手全員の攻撃-1",
        key_notes=["VGC最重要特性の一つ"]
    ),
    "defiant": AbilityInfo(
        name="defiant", japanese_name="まけんき",
        effect="能力を下げられると攻撃+2",
        key_notes=["いかく対策"]
    ),
    "competitive": AbilityInfo(
        name="competitive", japanese_name="かちき",
        effect="能力を下げられると特攻+2",
        key_notes=["いかく対策"]
    ),
    "mirrorarmor": AbilityInfo(
        name="mirrorarmor", japanese_name="ミラーアーマー",
        effect="能力ダウンを跳ね返す",
        key_notes=["いかくを跳ね返す"]  
    ),
    "clearamulet": AbilityInfo(
        name="clearamulet", japanese_name="クリアチャーム",
        effect="能力を下げられない",
        immune_effects=["stat_drop"]
    ),
    
    # --- サポート ---
    "friendguard": AbilityInfo(
        name="friendguard", japanese_name="フレンドガード",
        effect="味方が受けるダメージを25%軽減",
        key_notes=["自分以外"]
    ),
    "telepathy": AbilityInfo(
        name="telepathy", japanese_name="テレパシー",
        effect="味方の攻撃を受けない",
        immune_effects=["ally_attack"]
    ),
    
    # --- 特殊 ---
    "asone": AbilityInfo(
        name="asone", japanese_name="じんばいったい",
        effect="きんちょうかん+グリムニャイト/くろのいななき",
        key_notes=["バドレックス専用"]
    ),
    "grimneigh": AbilityInfo(
        name="grimneigh", japanese_name="くろのいななき",
        effect="倒すと特攻+1",
        key_notes=["黒馬バドレックス"]
    ),
    "chillingneigh": AbilityInfo(
        name="chillingneigh", japanese_name="しろのいななき",
        effect="倒すと攻撃+1",
        key_notes=["白馬バドレックス"]
    ),
    "unseenfist": AbilityInfo(
        name="unseenfist", japanese_name="ふかしのこぶし",
        effect="接触技がまもる状態を貫通",
        key_notes=["ウーラオス専用"]
    ),
}


class AbilityDB:
    """特性データベースサービス"""
    
    @classmethod
    def get_ability_info(cls, ability_name: str) -> Optional[AbilityInfo]:
        """特性名から情報を取得"""
        if not ability_name:
            return None
        key = ability_name.lower().replace(" ", "").replace("-", "")
        return ABILITY_DATABASE.get(key)
    
    @classmethod
    def get_speed_modifier(cls, ability: str, weather: str = None) -> float:
        """天候に基づく素早さ倍率を取得"""
        info = cls.get_ability_info(ability)
        if not info or not info.speed_modifier:
            return 1.0
        
        if info.speed_modifier == "double_in_sun" and weather == "sun":
            return 2.0
        if info.speed_modifier == "double_in_rain" and weather == "rain":
            return 2.0
        if info.speed_modifier == "double_in_sand" and weather == "sand":
            return 2.0
        if info.speed_modifier == "double_in_snow" and weather == "snow":
            return 2.0
        
        return 1.0
    
    @classmethod
    def get_damage_modifier(cls, ability: str) -> float:
        """ダメージ倍率を取得"""
        info = cls.get_ability_info(ability)
        return info.damage_modifier if info else 1.0
    
    @classmethod
    def is_immune_to_type(cls, ability: str, move_type: str) -> bool:
        """タイプ免疫があるかチェック"""
        info = cls.get_ability_info(ability)
        if not info:
            return False
        return move_type in info.immune_types


# Singleton
_ability_db = None

def get_ability_db() -> AbilityDB:
    global _ability_db
    if _ability_db is None:
        _ability_db = AbilityDB()
    return _ability_db
