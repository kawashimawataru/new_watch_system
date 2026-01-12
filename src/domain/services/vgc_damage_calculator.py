"""
VGC Damage Calculator - VGC専用ダメージ計算サービス

Gen 9 VGC (Lv50 ダブルバトル) に完全対応した精密ダメージ計算。

特徴:
- 正確なダメージ計算式 (Gen 5+)
- ダブルバトル全体技0.75倍
- EV/IV/性格から実数値計算
- 16段階乱数によるKO確率
- 2発KO確率、確定数計算
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# =============================================================================
# 定数
# =============================================================================

# VGC固定レベル
VGC_LEVEL = 50

# ランク補正テーブル
STAT_STAGE_MULTIPLIERS = {
    -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
    0: 1.0,
    1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2
}

# ダブルバトル補正
SPREAD_MODIFIER = 0.75  # 全体技が2体以上にhitする場合の補正

# 性格テーブル
NATURE_MODIFIERS = {
    # 攻撃↑
    "adamant": {"atk": 1.1, "spa": 0.9},
    "jolly": {"atk": 1.0, "spe": 1.1, "spa": 0.9},
    "lonely": {"atk": 1.1, "def": 0.9},
    "naughty": {"atk": 1.1, "spd": 0.9},
    "brave": {"atk": 1.1, "spe": 0.9},
    # 特攻↑
    "modest": {"spa": 1.1, "atk": 0.9},
    "timid": {"spa": 1.0, "spe": 1.1, "atk": 0.9},
    "mild": {"spa": 1.1, "def": 0.9},
    "rash": {"spa": 1.1, "spd": 0.9},
    "quiet": {"spa": 1.1, "spe": 0.9},
    # 防御↑
    "bold": {"def": 1.1, "atk": 0.9},
    "impish": {"def": 1.1, "spa": 0.9},
    "relaxed": {"def": 1.1, "spe": 0.9},
    "lax": {"def": 1.1, "spd": 0.9},
    # 特防↑
    "calm": {"spd": 1.1, "atk": 0.9},
    "careful": {"spd": 1.1, "spa": 0.9},
    "sassy": {"spd": 1.1, "spe": 0.9},
    "gentle": {"spd": 1.1, "def": 0.9},
# 素早さ↑
    "hasty": {"spe": 1.1, "def": 0.9},
    "naive": {"spe": 1.1, "spd": 0.9},
    # 無補正
    "hardy": {}, "docile": {}, "serious": {}, "bashful": {}, "quirky": {},
}

# 天候補正
WEATHER_MODIFIERS = {
    "sun": {"Fire": 1.5, "Water": 0.5},
    "rain": {"Water": 1.5, "Fire": 0.5},
    "sand": {},  # SpD上昇は別処理
    "snow": {},  # Def上昇は別処理 (Gen9)
    "hail": {},  # 旧世代
}

# フィールド補正
TERRAIN_MODIFIERS = {
    "electric": {"Electric": 1.3},
    "grassy": {"Grass": 1.3},
    "psychic": {"Psychic": 1.3},
    "misty": {"Dragon": 0.5},
}

# 壁 (リフレクター/ひかりのかべ)
SCREEN_MODIFIER = 0.5  # ダブルでは2/3だが簡易版として0.5

# 急所倍率 (Gen 6+)
CRITICAL_HIT_MULTIPLIER = 1.5

# 急所確率テーブル
CRITICAL_HIT_STAGES = {
    0: 1/24,    # 約4.17%
    1: 1/8,     # 12.5%
    2: 1/2,     # 50%
    3: 1.0,     # 確定急所
}

# 主要アイテム補正
ITEM_MODIFIERS = {
    "choiceband": {"atk_mult": 1.5},
    "choicespecs": {"spa_mult": 1.5},
    "choicescarf": {"spe_mult": 1.5},
    "lifeorb": {"damage_mult": 1.3},
    "expertbelt": {"super_effective_mult": 1.2},
    "assaultvest": {"spd_mult": 1.5},
    "eviolite": {"def_mult": 1.5, "spd_mult": 1.5},
    "focussash": {"survive_ohko": True},
}

# 主要特性補正
ABILITY_MODIFIERS = {
    # 火力上昇
    "hugepower": {"atk_mult": 2.0},
    "purepower": {"atk_mult": 2.0},
    "hustle": {"atk_mult": 1.5},
    "adaptability": {"stab_mult": 2.0},
    "sheerforce": {"damage_mult": 1.3},
    "swordsofruim": {"atk_mult": 1.25},  # わざわいのつるぎ
    "tabletsofruin": {"atk_debuff": 0.75},  # 相手攻撃低下
    "vesselsofruin": {"spa_debuff": 0.75},  # 相手特攻低下
    "beadsofruin": {"spd_debuff": 0.75},  # 相手特防低下
    
    # 天候特性
    "drought": {"weather": "sun"},
    "drizzle": {"weather": "rain"},
    "sandstream": {"weather": "sand"},
    "snowwarning": {"weather": "snow"},
    "orichalcumpulse": {"weather": "sun", "atk_mult": 1.33},  # 晴れ時攻撃1.33倍
    
    # フィールド特性
    "electricsurge": {"terrain": "electric"},
    "psychicsurge": {"terrain": "psychic"},
    "grassysurge": {"terrain": "grassy"},
    "mistysurge": {"terrain": "misty"},
    
    # 急所関連
    "superluck": {"crit_stage": 1},
    "sniper": {"crit_mult": 2.25},  # 急所時2.25倍
}

# 特性による無効化
ABILITY_IMMUNITIES = {
    "levitate": ["Ground"],
    "flashfire": ["Fire"],
    "waterabsorb": ["Water"],
    "voltabsorb": ["Electric"],
    "stormdrain": ["Water"],
    "lightningrod": ["Electric"],
    "sapsipper": ["Grass"],
    "motordrive": ["Electric"],
    "dryskin": ["Water"],
    "eartheater": ["Ground"],
    "wellbakedbody": ["Fire"],
}


# =============================================================================
# データクラス
# =============================================================================

@dataclass
class VGCPokemon:
    """VGCポケモンデータ"""
    name: str
    
    # 種族値
    base_hp: int
    base_atk: int
    base_def: int
    base_spa: int
    base_spd: int
    base_spe: int
    
    # タイプ
    types: List[str] = field(default_factory=list)
    
    # 個体値 (デフォルト: 理想個体)
    iv_hp: int = 31
    iv_atk: int = 31
    iv_def: int = 31
    iv_spa: int = 31
    iv_spd: int = 31
    iv_spe: int = 31
    
    # 努力値
    ev_hp: int = 0
    ev_atk: int = 0
    ev_def: int = 0
    ev_spa: int = 0
    ev_spd: int = 0
    ev_spe: int = 0
    
    # 性格
    nature: str = "hardy"
    
    # 装備・特性
    item: Optional[str] = None
    ability: Optional[str] = None
    
    # 状態
    current_hp_percent: float = 1.0
    atk_boost: int = 0
    def_boost: int = 0
    spa_boost: int = 0
    spd_boost: int = 0
    spe_boost: int = 0
    
    # テラスタル
    is_terastallized: bool = False
    tera_type: Optional[str] = None
    
    def _get_nature_modifier(self, stat: str) -> float:
        """性格補正を取得"""
        nature_data = NATURE_MODIFIERS.get(self.nature.lower(), {})
        return nature_data.get(stat, 1.0)
    
    def calc_hp(self) -> int:
        """HP実数値を計算"""
        base = self.base_hp
        iv = self.iv_hp
        ev = self.ev_hp
        return (base * 2 + iv + ev // 4) * VGC_LEVEL // 100 + VGC_LEVEL + 10
    
    def calc_atk(self) -> int:
        """攻撃実数値を計算"""
        base = self.base_atk
        iv = self.iv_atk
        ev = self.ev_atk
        nature = self._get_nature_modifier("atk")
        raw = (base * 2 + iv + ev // 4) * VGC_LEVEL // 100 + 5
        # アイテム補正
        if self.item and self.item.lower() == "choiceband":
            raw = int(raw * 1.5)
        return int(raw * nature)
    
    def calc_def(self) -> int:
        """防御実数値を計算"""
        base = self.base_def
        iv = self.iv_def
        ev = self.ev_def
        nature = self._get_nature_modifier("def")
        raw = (base * 2 + iv + ev // 4) * VGC_LEVEL // 100 + 5
        return int(raw * nature)
    
    def calc_spa(self) -> int:
        """特攻実数値を計算"""
        base = self.base_spa
        iv = self.iv_spa
        ev = self.ev_spa
        nature = self._get_nature_modifier("spa")
        raw = (base * 2 + iv + ev // 4) * VGC_LEVEL // 100 + 5
        # アイテム補正
        if self.item and self.item.lower() == "choicespecs":
            raw = int(raw * 1.5)
        return int(raw * nature)
    
    def calc_spd(self) -> int:
        """特防実数値を計算"""
        base = self.base_spd
        iv = self.iv_spd
        ev = self.ev_spd
        nature = self._get_nature_modifier("spd")
        raw = (base * 2 + iv + ev // 4) * VGC_LEVEL // 100 + 5
        # アイテム補正
        if self.item and self.item.lower() == "assaultvest":
            raw = int(raw * 1.5)
        return int(raw * nature)
    
    def calc_spe(self) -> int:
        """素早さ実数値を計算"""
        base = self.base_spe
        iv = self.iv_spe
        ev = self.ev_spe
        nature = self._get_nature_modifier("spe")
        raw = (base * 2 + iv + ev // 4) * VGC_LEVEL // 100 + 5
        # アイテム補正
        if self.item and self.item.lower() == "choicescarf":
            raw = int(raw * 1.5)
        return int(raw * nature)
    
    def get_current_hp(self) -> int:
        """現在HPを取得"""
        return int(self.calc_hp() * self.current_hp_percent)
    
    def get_types(self) -> List[str]:
        """タイプを取得 (テラスタル考慮)"""
        if self.is_terastallized and self.tera_type:
            return [self.tera_type]
        return self.types


@dataclass
class VGCMove:
    """VGC技データ"""
    name: str
    type: str
    category: str  # "physical", "special", "status"
    base_power: int
    is_spread: bool = False  # 全体技かどうか
    priority: int = 0


@dataclass
class VGCDamageResult:
    """ダメージ計算結果"""
    # ダメージ値
    min_damage: int
    max_damage: int
    
    # HP%
    min_percent: float
    max_percent: float
    
    # KO確率
    ko_chance: float       # 確1確率
    two_hit_ko: float      # 確2確率
    three_hit_ko: float    # 確3確率
    
    # 確定数
    n_hits_to_ko: int
    
    # その他
    type_effectiveness: float
    is_immune: bool
    
    # デバッグ情報
    attacker_stat: int     # 使用した攻撃ステータス
    defender_stat: int     # 使用した防御ステータス
    defender_hp: int       # 防御側HP実数値
    is_spread: bool        # 全体技か
    atk_boost_used: int    # 攻撃ランク
    def_boost_used: int    # 防御ランク
    
    def describe(self) -> str:
        """日本語での説明を生成"""
        if self.is_immune:
            return "無効"
        
        # 確定1発
        if self.ko_chance >= 1.0:
            return "確定1発"
        # 乱数1発
        elif self.ko_chance > 0:
            return f"乱数1発 ({self.ko_chance*100:.1f}%)"
        # 確定2発
        elif self.two_hit_ko >= 1.0:
            return "確定2発"
        # 乱数2発
        elif self.two_hit_ko > 0:
            return f"乱数2発 ({self.two_hit_ko*100:.1f}%)"
        # 確定3発
        elif self.three_hit_ko >= 1.0:
            return "確定3発"
        # 乱数3発
        elif self.three_hit_ko > 0:
            return f"乱数3発 ({self.three_hit_ko*100:.1f}%)"
        # 確定4発以上
        else:
            return f"確定{self.n_hits_to_ko}発"


# =============================================================================
# ダメージ計算
# =============================================================================

class VGCDamageCalculator:
    """VGC専用ダメージ計算クラス"""
    
    def calculate(
        self,
        attacker: VGCPokemon,
        defender: VGCPokemon,
        move: VGCMove,
        is_doubles: bool = True,
        field_conditions: Optional[Dict[str, Any]] = None,
    ) -> VGCDamageResult:
        """
        ダメージを計算する
        
        Args:
            attacker: 攻撃側ポケモン
            defender: 防御側ポケモン
            move: 使用する技
            is_doubles: ダブルバトルかどうか
            field_conditions: フィールド条件
                - weather: "sun", "rain", "sand", "snow"
                - terrain: "electric", "grassy", "psychic", "misty"
                - reflect: bool (リフレクター)
                - lightscreen: bool (ひかりのかべ)
                - is_critical: bool (急所)
        """
        field_conditions = field_conditions or {}
        weather = field_conditions.get("weather")
        terrain = field_conditions.get("terrain")
        has_reflect = field_conditions.get("reflect", False)
        has_lightscreen = field_conditions.get("lightscreen", False)
        is_critical = field_conditions.get("is_critical", False)
        
        # 変化技は無効
        if move.category == "status":
            return self._immune_result(defender.calc_hp())
        
        # タイプ相性
        from src.domain.models.type_chart import get_type_effectiveness
        defender_types = defender.get_types()
        type_eff = get_type_effectiveness(move.type, defender_types)
        
        # 特性による無効化
        if defender.ability and defender.ability.lower() in ABILITY_IMMUNITIES:
            immune_types = ABILITY_IMMUNITIES[defender.ability.lower()]
            if move.type in immune_types:
                type_eff = 0.0
        
        if type_eff == 0.0:
            return self._immune_result(defender.calc_hp())
        
        # 攻撃・防御ステータス
        if move.category == "physical":
            atk_stat = attacker.calc_atk()
            def_stat = defender.calc_def()
            atk_boost = attacker.atk_boost
            def_boost = defender.def_boost
        else:
            atk_stat = attacker.calc_spa()
            def_stat = defender.calc_spd()
            atk_boost = attacker.spa_boost
            def_boost = defender.spd_boost
        
        # 急所時はランク無視 (有利な方のみ適用)
        if is_critical:
            if atk_boost > 0:
                atk_stat = int(atk_stat * STAT_STAGE_MULTIPLIERS.get(atk_boost, 1.0))
            if def_boost < 0:
                def_stat = int(def_stat * STAT_STAGE_MULTIPLIERS.get(def_boost, 1.0))
        else:
            # 通常時のランク補正
            atk_stat = int(atk_stat * STAT_STAGE_MULTIPLIERS.get(atk_boost, 1.0))
            def_stat = int(def_stat * STAT_STAGE_MULTIPLIERS.get(def_boost, 1.0))
        
        # すなあらしによる特防上昇 (岩タイプのみ)
        if weather == "sand" and "Rock" in defender_types and move.category == "special":
            def_stat = int(def_stat * 1.5)
        
        # 雪による防御上昇 (氷タイプのみ, Gen9)
        if weather == "snow" and "Ice" in defender_types and move.category == "physical":
            def_stat = int(def_stat * 1.5)
        
        # 特性補正 (攻撃側)
        if attacker.ability:
            ability_lower = attacker.ability.lower()
            if ability_lower in ["hugepower", "purepower"]:
                atk_stat = int(atk_stat * 2.0)
            elif ability_lower == "hustle" and move.category == "physical":
                atk_stat = int(atk_stat * 1.5)
        
        # STAB
        attacker_types = attacker.get_types()
        stab = 1.0
        if move.type in attacker_types:
            if attacker.ability and attacker.ability.lower() == "adaptability":
                stab = 2.0
            else:
                stab = 1.5
        
        # 基本ダメージ計算 (Gen 5+ 式)
        base_power = move.base_power
        base_damage = ((2 * VGC_LEVEL / 5 + 2) * base_power * atk_stat / def_stat / 50 + 2)
        
        # 各種補正
        modifier = stab * type_eff
        
        # 天候補正
        if weather and weather in WEATHER_MODIFIERS:
            weather_mult = WEATHER_MODIFIERS[weather].get(move.type, 1.0)
            modifier *= weather_mult
        
        # フィールド補正 (地面についているポケモンのみ、簡易版では常に適用)
        if terrain and terrain in TERRAIN_MODIFIERS:
            terrain_mult = TERRAIN_MODIFIERS[terrain].get(move.type, 1.0)
            modifier *= terrain_mult
        
        # 壁補正
        if move.category == "physical" and has_reflect:
            modifier *= SCREEN_MODIFIER
        if move.category == "special" and has_lightscreen:
            modifier *= SCREEN_MODIFIER
        
        # 急所補正
        if is_critical:
            modifier *= CRITICAL_HIT_MULTIPLIER
        
        # いのちのたま
        if attacker.item and attacker.item.lower() == "lifeorb":
            modifier *= 1.3
        
        # 達人の帯 (効果抜群時)
        if attacker.item and attacker.item.lower() == "expertbelt" and type_eff > 1.0:
            modifier *= 1.2
        
        # 全体技補正 (ダブルバトルで2体以上にhit)
        if is_doubles and move.is_spread:
            modifier *= SPREAD_MODIFIER
        
        # 乱数計算 (0.85 ~ 1.00 の16段階)
        damages = []
        for i in range(16):
            roll = 0.85 + i * 0.01
            dmg = int(base_damage * modifier * roll)
            damages.append(dmg)
        
        min_damage = min(damages)
        max_damage = max(damages)
        
        # HP計算
        defender_max_hp = defender.calc_hp()
        defender_current_hp = int(defender_max_hp * defender.current_hp_percent)
        
        # %計算
        min_percent = min_damage / defender_max_hp * 100
        max_percent = max_damage / defender_max_hp * 100
        
        # KO確率計算
        ko_count = sum(1 for d in damages if d >= defender_current_hp)
        ko_chance = ko_count / 16
        
        # 2発KO確率計算 (全組み合わせ)
        two_hit_ko_count = 0
        for d1 in damages:
            for d2 in damages:
                if d1 + d2 >= defender_current_hp:
                    two_hit_ko_count += 1
        two_hit_ko = two_hit_ko_count / (16 * 16)
        
        # 3発KO確率計算 (全組み合わせ)
        three_hit_ko_count = 0
        for d1 in damages:
            for d2 in damages:
                for d3 in damages:
                    if d1 + d2 + d3 >= defender_current_hp:
                        three_hit_ko_count += 1
        three_hit_ko = three_hit_ko_count / (16 * 16 * 16)
        
        # 確定数計算
        expected_damage = sum(damages) / len(damages)
        if expected_damage <= 0:
            n_hits = 99
        else:
            n_hits = max(1, -(-defender_current_hp // int(expected_damage)))  # 切り上げ
        
        return VGCDamageResult(
            min_damage=min_damage,
            max_damage=max_damage,
            min_percent=min_percent,
            max_percent=max_percent,
            ko_chance=ko_chance,
            two_hit_ko=two_hit_ko,
            three_hit_ko=three_hit_ko,
            n_hits_to_ko=n_hits,
            type_effectiveness=type_eff,
            is_immune=False,
            attacker_stat=atk_stat,
            defender_stat=def_stat,
            defender_hp=defender_max_hp,
            is_spread=move.is_spread,
            atk_boost_used=atk_boost,
            def_boost_used=def_boost,
        )
    
    def _immune_result(self, defender_hp: int) -> VGCDamageResult:
        """無効時の結果を生成"""
        return VGCDamageResult(
            min_damage=0, max_damage=0,
            min_percent=0, max_percent=0,
            ko_chance=0, two_hit_ko=0, three_hit_ko=0,
            n_hits_to_ko=0,
            type_effectiveness=0, is_immune=True,
            attacker_stat=0, defender_stat=0,
            defender_hp=defender_hp, is_spread=False,
            atk_boost_used=0, def_boost_used=0,
        )


# =============================================================================
# 便利関数
# =============================================================================

def create_calyrex_shadow(
    ev_spa: int = 252,
    ev_spe: int = 252,
    ev_hp: int = 4,
    nature: str = "modest",
    item: str = None,
) -> VGCPokemon:
    """バドレックス黒馬を生成"""
    return VGCPokemon(
        name="Calyrex-Shadow",
        base_hp=100, base_atk=85, base_def=80,
        base_spa=165, base_spd=100, base_spe=150,
        types=["Psychic", "Ghost"],
        ev_hp=ev_hp, ev_spa=ev_spa, ev_spe=ev_spe,
        nature=nature,
        ability="asone",
        item=item,
    )


def create_incineroar(
    ev_hp: int = 252,
    ev_def: int = 0,
    ev_spd: int = 0,
    nature: str = "careful",
    item: str = "sitrusberry",
) -> VGCPokemon:
    """ガオガエンを生成"""
    return VGCPokemon(
        name="Incineroar",
        base_hp=95, base_atk=115, base_def=90,
        base_spa=80, base_spd=90, base_spe=60,
        types=["Fire", "Dark"],
        ev_hp=ev_hp, ev_def=ev_def, ev_spd=ev_spd,
        nature=nature,
        ability="intimidate",
        item=item,
    )


def create_astral_barrage() -> VGCMove:
    """アストラルビットを生成"""
    return VGCMove(
        name="Astral Barrage",
        type="Ghost",
        category="special",
        base_power=120,
        is_spread=True,  # 全体技
    )


# シングルトン
_vgc_damage_calc = None

def get_vgc_damage_calculator() -> VGCDamageCalculator:
    global _vgc_damage_calc
    if _vgc_damage_calc is None:
        _vgc_damage_calc = VGCDamageCalculator()
    return _vgc_damage_calc
