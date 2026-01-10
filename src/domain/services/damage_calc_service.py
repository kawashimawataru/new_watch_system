"""
DamageCalcService - ダメージ計算API

Phase A: 精度向上の土台となるダメージ計算サービス

出力:
- ko_prob: このターンで倒せる確率
- min/max: 乱数レンジ
- expected: 期待値
- n_hits_to_ko: 確定数

考慮要素:
- STAB (1.5x)
- タイプ相性 (0.25x ~ 4x)
- ランク補正
- 主要アイテム
- 主要特性
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any
from enum import Enum

from src.domain.models.type_chart import get_type_effectiveness


# =============================================================================
# データクラス
# =============================================================================

@dataclass
class DamageResult:
    """ダメージ計算結果"""
    min_damage: int          # 最小ダメージ
    max_damage: int          # 最大ダメージ
    expected: float          # 期待ダメージ（HP%）
    ko_prob: float           # このターンで倒せる確率 (0.0 ~ 1.0)
    n_hits_to_ko: int        # 確定数（1=確1、2=確2、0=無効）
    two_turn_ko_prob: float  # 2ターンで落とせる確率
    is_immune: bool          # 無効かどうか
    type_effectiveness: float  # タイプ相性倍率


@dataclass
class PokemonStats:
    """計算用ポケモンステータス"""
    species: str
    hp: int                    # 現在HP
    max_hp: int                # 最大HP
    attack: int                # こうげき
    defense: int               # ぼうぎょ
    special_attack: int        # とくこう
    special_defense: int       # とくぼう
    speed: int                 # すばやさ
    types: List[str]           # タイプ
    ability: Optional[str] = None
    item: Optional[str] = None
    terastallized: Optional[str] = None  # テラスタイプ
    
    # ランク補正 (-6 ~ +6)
    atk_boost: int = 0
    def_boost: int = 0
    spa_boost: int = 0
    spd_boost: int = 0
    spe_boost: int = 0


@dataclass
class MoveData:
    """技データ"""
    id: str
    name: str
    type: str
    category: str  # "physical", "special", "status"
    base_power: int
    priority: int = 0
    is_spread: bool = False  # 範囲技かどうか
    

# =============================================================================
# 定数
# =============================================================================

# ランク補正テーブル
STAT_STAGE_MULTIPLIERS = {
    -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
    0: 1.0,
    1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2
}

# 主要アイテム補正
ITEM_MODIFIERS: Dict[str, Dict[str, float]] = {
    # こだわり系
    "choiceband": {"atk": 1.5},
    "choicespecs": {"spa": 1.5},
    "choicescarf": {"spe": 1.5},
    # いのちのたま
    "lifeorb": {"damage": 1.3},
    # タイプ強化
    "expertbelt": {"supereffective": 1.2},
    # その他
    "assaultvest": {"spd": 1.5},
}

# タイプ強化アイテム (プレート、ジュエル等)
TYPE_BOOST_ITEMS: Dict[str, str] = {
    "charcoal": "Fire", "mysticwater": "Water", "magnet": "Electric",
    "miracleseed": "Grass", "nevermeltice": "Ice", "blackbelt": "Fighting",
    "poisonbarb": "Poison", "softsand": "Ground", "sharpbeak": "Flying",
    "twistedspoon": "Psychic", "silverpowder": "Bug", "hardstone": "Rock",
    "spelltag": "Ghost", "dragonfang": "Dragon", "blackglasses": "Dark",
    "metalcoat": "Steel", "fairyfeather": "Fairy",
}

# 主要特性補正
ABILITY_MODIFIERS: Dict[str, Dict[str, Any]] = {
    # 火力上昇
    "adaptability": {"stab": 2.0},  # てきおうりょく: STAB 2.0倍
    "hugepower": {"atk": 2.0},      # ちからもち
    "purepower": {"atk": 2.0},      # ヨガパワー
    "hustle": {"atk": 1.5},         # はりきり
    "sheerforce": {"remove_secondary": True, "damage": 1.3},  # ちからずく
    "protosynthesis": {"highest_stat": 1.3},  # こだいかっせい
    "quarkdrive": {"highest_stat": 1.3},      # クォークチャージ
    # 防御系
    "intimidate": {"opp_atk": 0.67},  # いかく (1段階ダウン)
    "multiscale": {"first_hit": 0.5},  # マルチスケイル
    "fluffy": {"contact": 0.5, "fire": 2.0},
    # タイプ無効
    "levitate": {"immune": ["Ground"]},
    "flashfire": {"immune": ["Fire"], "boost": ["Fire"]},
    "waterabsorb": {"immune": ["Water"]},
    "voltabsorb": {"immune": ["Electric"]},
    "stormdrain": {"immune": ["Water"]},
    "lightningrod": {"immune": ["Electric"]},
    "sapsipper": {"immune": ["Grass"]},
}


# =============================================================================
# DamageCalcService
# =============================================================================

class DamageCalcService:
    """
    ダメージ計算サービス
    
    VGC向けの意思決定に特化したダメージ計算を提供。
    「倒せるか」「何発で倒せるか」が最重要出力。
    """
    
    def __init__(self):
        """初期化"""
        pass
    
    def calculate(
        self,
        attacker: PokemonStats,
        defender: PokemonStats,
        move: MoveData,
        field_conditions: Optional[Dict[str, Any]] = None,
    ) -> DamageResult:
        """
        ダメージを計算する
        
        Args:
            attacker: 攻撃側ポケモン
            defender: 防御側ポケモン
            move: 使用する技
            field_conditions: フィールド状態（天候、フィールド、壁等）
            
        Returns:
            DamageResult: 計算結果
        """
        field_conditions = field_conditions or {}
        
        # 変化技は無効
        if move.category == "status":
            return DamageResult(
                min_damage=0, max_damage=0, expected=0.0,
                ko_prob=0.0, n_hits_to_ko=0, two_turn_ko_prob=0.0,
                is_immune=False, type_effectiveness=1.0
            )
        
        # タイプ相性
        defender_types = defender.types
        if defender.terastallized:
            defender_types = [defender.terastallized]
        
        type_eff = get_type_effectiveness(move.type, defender_types)
        
        # 特性による無効化
        if self._is_immune_by_ability(move, defender):
            type_eff = 0.0
        
        if type_eff == 0.0:
            return DamageResult(
                min_damage=0, max_damage=0, expected=0.0,
                ko_prob=0.0, n_hits_to_ko=0, two_turn_ko_prob=0.0,
                is_immune=True, type_effectiveness=0.0
            )
        
        # 攻撃・防御ステータス取得
        if move.category == "physical":
            atk_stat = self._get_boosted_stat(attacker.attack, attacker.atk_boost)
            def_stat = self._get_boosted_stat(defender.defense, defender.def_boost)
        else:  # special
            atk_stat = self._get_boosted_stat(attacker.special_attack, attacker.spa_boost)
            def_stat = self._get_boosted_stat(defender.special_defense, defender.spd_boost)
        
        # アイテム補正（攻撃側）
        atk_stat = self._apply_item_modifier(atk_stat, attacker.item, move.category)
        
        # 特性補正（攻撃側）
        atk_stat = self._apply_ability_modifier_atk(atk_stat, attacker.ability, attacker)
        
        # STAB
        stab = 1.0
        attacker_types = attacker.types
        if attacker.terastallized:
            attacker_types = [attacker.terastallized]
        
        if move.type.capitalize() in [t.capitalize() for t in attacker_types]:
            if attacker.ability and attacker.ability.lower() == "adaptability":
                stab = 2.0
            else:
                stab = 1.5
        
        # 基本ダメージ計算
        base_power = move.base_power
        
        # タイプ強化アイテム
        if attacker.item and attacker.item.lower() in TYPE_BOOST_ITEMS:
            if TYPE_BOOST_ITEMS[attacker.item.lower()].capitalize() == move.type.capitalize():
                base_power = int(base_power * 1.2)
        
        # ダメージ式 (Gen 5+)
        # ((2 * Level / 5 + 2) * Power * A/D / 50 + 2) * Modifiers
        level = 50  # VGCはLv50固定
        
        base_damage = ((2 * level / 5 + 2) * base_power * atk_stat / def_stat / 50 + 2)
        
        # 各種補正
        modifiers = stab * type_eff
        
        # いのちのたま / ちからずく
        if attacker.item and attacker.item.lower() == "lifeorb":
            modifiers *= 1.3
        if attacker.ability and attacker.ability.lower() == "sheerforce":
            modifiers *= 1.3
        
        # 範囲技補正
        if move.is_spread:
            modifiers *= 0.75
        
        # 壁補正
        if field_conditions.get("reflect") and move.category == "physical":
            modifiers *= 0.5
        if field_conditions.get("lightscreen") and move.category == "special":
            modifiers *= 0.5
        
        # 乱数 (0.85 ~ 1.00)
        min_damage = int(base_damage * modifiers * 0.85)
        max_damage = int(base_damage * modifiers * 1.00)
        
        # 期待値
        expected_damage = (min_damage + max_damage) / 2
        expected_pct = expected_damage / defender.hp * 100
        
        # KO確率計算
        ko_prob = self._calculate_ko_prob(min_damage, max_damage, defender.hp)
        
        # 確定数
        n_hits_to_ko = self._calculate_n_hits_to_ko(expected_damage, defender.hp)
        
        # 2ターンKO確率
        two_turn_ko_prob = self._calculate_two_turn_ko_prob(
            min_damage, max_damage, defender.hp
        )
        
        return DamageResult(
            min_damage=min_damage,
            max_damage=max_damage,
            expected=expected_pct,
            ko_prob=ko_prob,
            n_hits_to_ko=n_hits_to_ko,
            two_turn_ko_prob=two_turn_ko_prob,
            is_immune=False,
            type_effectiveness=type_eff
        )
    
    def calculate_focus_fire(
        self,
        attacker1: PokemonStats,
        attacker2: PokemonStats,
        defender: PokemonStats,
        move1: MoveData,
        move2: MoveData,
        field_conditions: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        集中攻撃（2体で同じ相手を攻撃）のKO確率を計算
        
        Returns:
            float: KO確率 (0.0 ~ 1.0)
        """
        result1 = self.calculate(attacker1, defender, move1, field_conditions)
        result2 = self.calculate(attacker2, defender, move2, field_conditions)
        
        if result1.is_immune and result2.is_immune:
            return 0.0
        
        # 合計ダメージの期待値
        total_min = result1.min_damage + result2.min_damage
        total_max = result1.max_damage + result2.max_damage
        
        return self._calculate_ko_prob(total_min, total_max, defender.hp)
    
    # =========================================================================
    # Private Methods
    # =========================================================================
    
    def _get_boosted_stat(self, base_stat: int, boost: int) -> int:
        """ランク補正を適用したステータスを取得"""
        boost = max(-6, min(6, boost))
        return int(base_stat * STAT_STAGE_MULTIPLIERS[boost])
    
    def _apply_item_modifier(
        self, stat: int, item: Optional[str], category: str
    ) -> int:
        """アイテム補正を適用"""
        if not item:
            return stat
        
        item_lower = item.lower()
        
        if item_lower == "choiceband" and category == "physical":
            return int(stat * 1.5)
        if item_lower == "choicespecs" and category == "special":
            return int(stat * 1.5)
        
        return stat
    
    def _apply_ability_modifier_atk(
        self, stat: int, ability: Optional[str], attacker: PokemonStats
    ) -> int:
        """攻撃側の特性補正を適用"""
        if not ability:
            return stat
        
        ability_lower = ability.lower()
        
        if ability_lower in ["hugepower", "purepower"]:
            return int(stat * 2.0)
        if ability_lower == "hustle":
            return int(stat * 1.5)
        
        return stat
    
    def _is_immune_by_ability(self, move: MoveData, defender: PokemonStats) -> bool:
        """特性による無効化をチェック"""
        if not defender.ability:
            return False
        
        ability_lower = defender.ability.lower()
        move_type = move.type.capitalize()
        
        immune_map = {
            "levitate": "Ground",
            "flashfire": "Fire",
            "waterabsorb": "Water",
            "voltabsorb": "Electric",
            "stormdrain": "Water",
            "lightningrod": "Electric",
            "sapsipper": "Grass",
        }
        
        if ability_lower in immune_map:
            if move_type == immune_map[ability_lower]:
                return True
        
        return False
    
    def _calculate_ko_prob(self, min_dmg: int, max_dmg: int, hp: int) -> float:
        """KO確率を計算（乱数16段階を想定）"""
        if max_dmg < hp:
            return 0.0
        if min_dmg >= hp:
            return 1.0
        
        # 乱数16段階 (85%, 86%, ..., 100%)
        ko_count = 0
        for i in range(16):
            roll = min_dmg + (max_dmg - min_dmg) * i / 15
            if roll >= hp:
                ko_count += 1
        
        return ko_count / 16
    
    def _calculate_n_hits_to_ko(self, expected_damage: float, hp: int) -> int:
        """確定数を計算（期待値ベース）"""
        if expected_damage <= 0:
            return 0
        
        return max(1, int(hp / expected_damage + 0.99))  # 切り上げ
    
    def _calculate_two_turn_ko_prob(
        self, min_dmg: int, max_dmg: int, hp: int
    ) -> float:
        """2ターンでのKO確率を計算"""
        # 2発の合計ダメージの分布を近似
        two_hit_min = min_dmg * 2
        two_hit_max = max_dmg * 2
        
        return self._calculate_ko_prob(two_hit_min, two_hit_max, hp)


# =============================================================================
# 便利関数
# =============================================================================

def create_pokemon_from_poke_env(pokemon: Any) -> PokemonStats:
    """
    poke-env の Pokemon オブジェクトから PokemonStats を作成
    
    Args:
        pokemon: poke_env.environment.pokemon.Pokemon
        
    Returns:
        PokemonStats
    """
    # タイプ取得
    types = []
    if hasattr(pokemon, 'types') and pokemon.types:
        for t in pokemon.types:
            if t:
                types.append(t.name if hasattr(t, 'name') else str(t))
    
    # テラスタイプ
    terastallized = None
    if hasattr(pokemon, 'terastallized') and pokemon.terastallized:
        terastallized = pokemon.terastallized
    
    # ランク補正
    boosts = pokemon.boosts if hasattr(pokemon, 'boosts') else {}
    
    return PokemonStats(
        species=pokemon.species if hasattr(pokemon, 'species') else str(pokemon),
        hp=pokemon.current_hp if hasattr(pokemon, 'current_hp') else 100,
        max_hp=pokemon.max_hp if hasattr(pokemon, 'max_hp') else 100,
        attack=pokemon.stats.get('atk', 100) if hasattr(pokemon, 'stats') else 100,
        defense=pokemon.stats.get('def', 100) if hasattr(pokemon, 'stats') else 100,
        special_attack=pokemon.stats.get('spa', 100) if hasattr(pokemon, 'stats') else 100,
        special_defense=pokemon.stats.get('spd', 100) if hasattr(pokemon, 'stats') else 100,
        speed=pokemon.stats.get('spe', 100) if hasattr(pokemon, 'stats') else 100,
        types=types,
        ability=pokemon.ability if hasattr(pokemon, 'ability') else None,
        item=pokemon.item if hasattr(pokemon, 'item') else None,
        terastallized=terastallized,
        atk_boost=boosts.get('atk', 0),
        def_boost=boosts.get('def', 0),
        spa_boost=boosts.get('spa', 0),
        spd_boost=boosts.get('spd', 0),
        spe_boost=boosts.get('spe', 0),
    )


def create_move_from_poke_env(move: Any) -> MoveData:
    """
    poke-env の Move オブジェクトから MoveData を作成
    
    Args:
        move: poke_env.environment.move.Move
        
    Returns:
        MoveData
    """
    # タイプ
    move_type = "Normal"
    if hasattr(move, 'type') and move.type:
        move_type = move.type.name if hasattr(move.type, 'name') else str(move.type)
    
    # カテゴリ
    category = "physical"
    if hasattr(move, 'category'):
        cat = move.category
        if hasattr(cat, 'name'):
            category = cat.name.lower()
        elif hasattr(cat, 'value'):
            category = cat.value.lower()
        else:
            category = str(cat).lower()
    
    # 範囲技判定
    is_spread = False
    if hasattr(move, 'target'):
        target = move.target
        target_str = target.name if hasattr(target, 'name') else str(target)
        is_spread = "adjacent" in target_str.lower() and "foes" in target_str.lower()
    
    return MoveData(
        id=move.id if hasattr(move, 'id') else str(move),
        name=move.id if hasattr(move, 'id') else str(move),
        type=move_type,
        category=category,
        base_power=move.base_power if hasattr(move, 'base_power') and move.base_power else 0,
        priority=move.priority if hasattr(move, 'priority') else 0,
        is_spread=is_spread,
    )


# =============================================================================
# シングルトン
# =============================================================================

_service: Optional[DamageCalcService] = None


def get_damage_calc_service() -> DamageCalcService:
    """DamageCalcService のシングルトンを取得"""
    global _service
    if _service is None:
        _service = DamageCalcService()
    return _service
