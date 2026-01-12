"""
Battle State Simulator - バトル状態シミュレーター

CandidateScorerの精度向上のための包括的なバトルシミュレーター。

考慮要素:
- VGCDamageCalculator による精密ダメージ計算
- 全特性効果 (いかく, ひらいしん, もらいび等)
- 全アイテム効果 (オボンのみ, タスキ, こだわり等)
- EV推定/仮定システム
- 天候/フィールド/壁
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from copy import deepcopy

from src.domain.services.vgc_damage_calculator import (
    VGCPokemon, VGCMove, VGCDamageResult,
    get_vgc_damage_calculator, VGC_LEVEL
)
from src.domain.services.base_stats_db import get_base_stats_db
from src.domain.services.move_effect_db import get_move_effect_db
from src.domain.services.ability_db import get_ability_db


# =============================================================================
# EV推定システム
# =============================================================================

# VGCでよくある配分パターン
COMMON_EV_SPREADS = {
    "physical_sweeper": {"atk": 252, "spe": 252, "hp": 4},
    "special_sweeper": {"spa": 252, "spe": 252, "hp": 4},
    "bulky_attacker": {"hp": 252, "atk": 252, "def": 4},
    "bulky_special": {"hp": 252, "spa": 252, "spd": 4},
    "defensive": {"hp": 252, "def": 128, "spd": 128},
    "fast_support": {"hp": 252, "spe": 252, "def": 4},
}

# ポケモン別の推定配分
POKEMON_LIKELY_SPREADS = {
    # アタッカー
    "calyrexshadow": "special_sweeper",
    "calyrexice": "physical_sweeper",
    "koraidon": "physical_sweeper",
    "miraidon": "special_sweeper",
    "fluttermane": "special_sweeper",
    "chienyu": "special_sweeper",
    "chienpao": "physical_sweeper",
    "urshifurapidstrike": "physical_sweeper",
    "urshifusingletrike": "physical_sweeper",
    
    # サポート/耐久
    "incineroar": "defensive",
    "grimmsnarl": "fast_support",
    "rillaboom": "bulky_attacker",
    "whimsicott": "fast_support",
    "amoonguss": "defensive",
    "dondozo": "defensive",
    "tatsugiri": "special_sweeper",
    
    # 汎用
    "landorus": "physical_sweeper",
    "regieleki": "special_sweeper",
}


def estimate_ev_spread(pokemon_name: str) -> Dict[str, int]:
    """ポケモン名からEV配分を推定"""
    name_lower = pokemon_name.lower().replace(" ", "").replace("-", "")
    
    spread_type = POKEMON_LIKELY_SPREADS.get(name_lower, "bulky_attacker")
    return COMMON_EV_SPREADS.get(spread_type, {"hp": 84, "atk": 84, "def": 84, "spa": 84, "spd": 84, "spe": 84})


# =============================================================================
# 特性効果システム
# =============================================================================

# 場に出た時の効果
ENTRY_ABILITIES = {
    "intimidate": {"effect": "lower_opponent_atk", "stages": -1},
    "intrepidsword": {"effect": "boost_atk", "stages": 1},
    "dauntlessshield": {"effect": "boost_def", "stages": 1},
    "download": {"effect": "boost_atk_or_spa", "stages": 1},
    "drizzle": {"effect": "set_weather", "weather": "rain"},
    "drought": {"effect": "set_weather", "weather": "sun"},
    "sandstream": {"effect": "set_weather", "weather": "sand"},
    "snowwarning": {"effect": "set_weather", "weather": "snow"},
    "electricsurge": {"effect": "set_terrain", "terrain": "electric"},
    "psychicsurge": {"effect": "set_terrain", "terrain": "psychic"},
    "grassysurge": {"effect": "set_terrain", "terrain": "grassy"},
    "mistysurge": {"effect": "set_terrain", "terrain": "misty"},
}

# ダメージ受けた時の効果
DAMAGE_TAKEN_ABILITIES = {
    "multiscale": {"condition": "full_hp", "damage_mult": 0.5},
    "shadowshield": {"condition": "full_hp", "damage_mult": 0.5},
    "fluffy": {"contact_mult": 0.5, "fire_mult": 2.0},
    "icescales": {"special_mult": 0.5},
    "filter": {"super_effective_mult": 0.75},
    "solidrock": {"super_effective_mult": 0.75},
    "prismarmor": {"super_effective_mult": 0.75},
}

# 攻撃時の効果
ATTACK_ABILITIES = {
    "hugepower": {"atk_mult": 2.0},
    "purepower": {"atk_mult": 2.0},
    "hustle": {"atk_mult": 1.5},
    "adaptability": {"stab_mult": 2.0},
    "sheerforce": {"damage_mult": 1.3},
    "strongjaw": {"bite_mult": 1.5},
    "ironfist": {"punch_mult": 1.2},
    "technician": {"low_power_mult": 1.5, "threshold": 60},
    "neuroforce": {"super_effective_mult": 1.25},
}


# =============================================================================
# アイテム効果システム
# =============================================================================

# HP回復アイテム
RECOVERY_ITEMS = {
    "sitrusberry": {"trigger": "below_50", "heal_fraction": 0.25},
    "oranberry": {"trigger": "below_50", "heal_hp": 10},  # VGCではあまり使われない
    "aguavberry": {"trigger": "below_50", "heal_fraction": 0.33},
    "figyberry": {"trigger": "below_50", "heal_fraction": 0.33},
    "iapapaberry": {"trigger": "below_50", "heal_fraction": 0.33},
    "magoberry": {"trigger": "below_50", "heal_fraction": 0.33},
    "wikiberry": {"trigger": "below_50", "heal_fraction": 0.33},
}

# 耐久アイテム
SURVIVAL_ITEMS = {
    "focussash": {"effect": "survive_ohko", "condition": "full_hp"},
    "focusband": {"effect": "chance_survive", "chance": 0.10},
}

# ダメージ軽減アイテム
DAMAGE_REDUCTION_ITEMS = {
    "eviolite": {"def_mult": 1.5, "spd_mult": 1.5, "condition": "not_fully_evolved"},
    "assaultvest": {"spd_mult": 1.5},
}

# ダメージ増加アイテム
DAMAGE_BOOST_ITEMS = {
    "choiceband": {"atk_mult": 1.5},
    "choicespecs": {"spa_mult": 1.5},
    "lifeorb": {"damage_mult": 1.3, "recoil_fraction": 0.1},
    "expertbelt": {"super_effective_mult": 1.2},
}


# =============================================================================
# BattleStateSimulator
# =============================================================================

@dataclass
class SimulatedPokemon:
    """シミュレーション用ポケモン"""
    name: str
    hp_fraction: float = 1.0
    fainted: bool = False
    
    # タイプ
    types: List[str] = field(default_factory=list)
    
    # ステータス (推定)
    evs: Dict[str, int] = field(default_factory=dict)
    nature: str = "hardy"
    
    # 装備
    item: Optional[str] = None
    item_consumed: bool = False
    ability: Optional[str] = None
    
    # ランク
    atk_boost: int = 0
    def_boost: int = 0
    spa_boost: int = 0
    spd_boost: int = 0
    spe_boost: int = 0
    
    # 状態 (基本)
    protected: bool = False
    terastallized: bool = False
    tera_type: Optional[str] = None
    
    # 状態 (拡張)
    flinched: bool = False              # ひるみ状態
    encored: bool = False               # アンコール状態
    encored_move: Optional[str] = None  # アンコールされた技
    encore_turns: int = 0               # アンコール残りターン
    
    choice_locked: bool = False         # こだわりロック状態
    choice_move: Optional[str] = None   # ロックされた技
    
    protect_count: int = 0              # まもる連続使用回数
    first_turn: bool = True             # 登場した最初のターン (ねこだまし判定)
    
    # 状態異常
    status: Optional[str] = None        # "burn", "paralysis", "sleep", "freeze", "poison", "toxic"
    toxic_counter: int = 0              # どくどくカウンター
    
    # 追加効果
    is_substitute: bool = False         # みがわり中
    is_digging: bool = False            # あなをほる中
    is_flying: bool = False             # そらをとぶ中
    is_diving: bool = False             # ダイビング中


@dataclass
class FieldState:
    """フィールド状態"""
    weather: Optional[str] = None
    terrain: Optional[str] = None
    weather_turns: int = 0
    terrain_turns: int = 0
    
    player_reflect: bool = False
    player_lightscreen: bool = False
    player_tailwind: bool = False
    player_tailwind_turns: int = 0
    
    opponent_reflect: bool = False
    opponent_lightscreen: bool = False
    opponent_tailwind: bool = False
    opponent_tailwind_turns: int = 0
    
    trick_room: bool = False
    trick_room_turns: int = 0


class BattleStateSimulator:
    """
    包括的なバトル状態シミュレーター
    
    全ての特性/アイテム/EV推定を考慮した精密シミュレーション
    """
    
    def __init__(self):
        self.damage_calc = get_vgc_damage_calculator()
        self.base_stats_db = get_base_stats_db()
        self.move_db = get_move_effect_db()
        self.ability_db = get_ability_db()
    
    def create_simulated_pokemon(self, poke_dict: Dict[str, Any]) -> SimulatedPokemon:
        """DictからSimulatedPokemonを作成"""
        name = poke_dict.get("name", "")
        
        # EV推定 (相手のEVは不明なので推定)
        evs = poke_dict.get("evs") or estimate_ev_spread(name)
        
        # タイプ取得
        types = poke_dict.get("types", [])
        if not types:
            base = self.base_stats_db.get_pokemon_data(name)
            if base:
                types = base.types
        
        return SimulatedPokemon(
            name=name,
            hp_fraction=poke_dict.get("hp_fraction", 1.0),
            fainted=poke_dict.get("fainted", False),
            types=types,
            evs=evs,
            nature=poke_dict.get("nature", "hardy"),
            item=poke_dict.get("item"),
            ability=poke_dict.get("ability"),
            atk_boost=poke_dict.get("atk_boost", 0),
            def_boost=poke_dict.get("def_boost", 0),
            spa_boost=poke_dict.get("spa_boost", 0),
            spd_boost=poke_dict.get("spd_boost", 0),
            spe_boost=poke_dict.get("spe_boost", 0),
        )
    
    def create_vgc_pokemon(self, sim_poke: SimulatedPokemon) -> VGCPokemon:
        """SimulatedPokemonからVGCPokemonを作成"""
        base = self.base_stats_db.get_base_stats(sim_poke.name)
        
        if base:
            return VGCPokemon(
                name=sim_poke.name,
                base_hp=base.hp,
                base_atk=base.attack,
                base_def=base.defense,
                base_spa=base.special_attack,
                base_spd=base.special_defense,
                base_spe=base.speed,
                types=sim_poke.types,
                ev_hp=sim_poke.evs.get("hp", 0),
                ev_atk=sim_poke.evs.get("atk", 0),
                ev_def=sim_poke.evs.get("def", 0),
                ev_spa=sim_poke.evs.get("spa", 0),
                ev_spd=sim_poke.evs.get("spd", 0),
                ev_spe=sim_poke.evs.get("spe", 0),
                nature=sim_poke.nature,
                item=sim_poke.item,
                ability=sim_poke.ability,
                current_hp_percent=sim_poke.hp_fraction,
                atk_boost=sim_poke.atk_boost,
                def_boost=sim_poke.def_boost,
                spa_boost=sim_poke.spa_boost,
                spd_boost=sim_poke.spd_boost,
                spe_boost=sim_poke.spe_boost,
                is_terastallized=sim_poke.terastallized,
                tera_type=sim_poke.tera_type,
            )
        else:
            # 種族値不明時のデフォルト
            return VGCPokemon(
                name=sim_poke.name,
                base_hp=80, base_atk=80, base_def=80,
                base_spa=80, base_spd=80, base_spe=80,
                types=sim_poke.types or ["Normal"],
                current_hp_percent=sim_poke.hp_fraction,
            )
    
    def apply_entry_abilities(
        self,
        entering_pokemon: SimulatedPokemon,
        opponents: List[SimulatedPokemon],
        allies: List[SimulatedPokemon],
        field: FieldState,
        is_player: bool,
    ) -> None:
        """登場時の特性を適用"""
        ability = (entering_pokemon.ability or "").lower().replace(" ", "")
        
        if ability not in ENTRY_ABILITIES:
            return
        
        effect = ENTRY_ABILITIES[ability]
        
        # いかく
        if effect.get("effect") == "lower_opponent_atk":
            stages = effect.get("stages", -1)
            for opp in opponents:
                if not opp.fainted:
                    # クリアボディ等のチェック
                    opp_ability = (opp.ability or "").lower()
                    if opp_ability not in ["clearbody", "whitesmoke", "fullmetalbody", "innerfocus"]:
                        opp.atk_boost = max(-6, opp.atk_boost + stages)
        
        # 自己強化
        elif effect.get("effect") == "boost_atk":
            entering_pokemon.atk_boost = min(6, entering_pokemon.atk_boost + effect.get("stages", 1))
        elif effect.get("effect") == "boost_def":
            entering_pokemon.def_boost = min(6, entering_pokemon.def_boost + effect.get("stages", 1))
        
        # 天候設定
        elif effect.get("effect") == "set_weather":
            field.weather = effect.get("weather")
            field.weather_turns = 5
        
        # フィールド設定
        elif effect.get("effect") == "set_terrain":
            field.terrain = effect.get("terrain")
            field.terrain_turns = 5
    
    def calculate_damage_with_effects(
        self,
        attacker: SimulatedPokemon,
        defender: SimulatedPokemon,
        move_name: str,
        field: FieldState,
        is_player_attacking: bool,
    ) -> Tuple[VGCDamageResult, float]:
        """
        全効果を考慮したダメージ計算
        
        Returns:
            (VGCDamageResult, 実際に適用されるHP減少量)
        """
        # 技情報取得
        move_info = self.move_db.get_move_info(move_name)
        
        is_spread = False
        power = 80
        move_type = "Normal"
        category = "physical"
        
        if move_info:
            power = move_info.power or 80
            move_type = move_info.type
            category = move_info.category
            is_spread = move_info.target in ["allAdjacentFoes", "allAdjacent", "all"]
            
            # 追加効果情報を取得
            secondary_effect = None
            if hasattr(move_info, 'effect') and move_info.effect:
                secondary_effect = move_info.effect
        
        # やけど状態による攻撃力低下 (物理のみ)
        burn_atk_mult = 1.0
        if attacker.status == "burn" and category == "physical":
            # こんじょうチェック
            atk_ability = (attacker.ability or "").lower().replace(" ", "")
            if atk_ability != "guts":
                burn_atk_mult = 0.5
        
        # まひによる素早さ低下は VGCPokemon 側で処理
        
        vgc_move = VGCMove(
            name=move_name,
            type=move_type,
            category=category,
            base_power=power,
            is_spread=is_spread,
        )
        
        # VGCPokemon作成
        atk_vgc = self.create_vgc_pokemon(attacker)
        def_vgc = self.create_vgc_pokemon(defender)
        
        # やけど補正を攻撃ランクに反映
        if burn_atk_mult < 1.0:
            # 簡易的にランクを-2として扱う (0.5倍 ≈ -2ランク)
            atk_vgc.atk_boost = max(-6, atk_vgc.atk_boost - 2)
        
        # フィールド条件
        field_conditions = {
            "weather": field.weather,
            "terrain": field.terrain,
            "reflect": field.opponent_reflect if is_player_attacking else field.player_reflect,
            "lightscreen": field.opponent_lightscreen if is_player_attacking else field.player_lightscreen,
        }
        
        # マルチスケイル等のチェック
        def_ability = (defender.ability or "").lower().replace(" ", "")
        if def_ability in DAMAGE_TAKEN_ABILITIES:
            ability_effect = DAMAGE_TAKEN_ABILITIES[def_ability]
            if ability_effect.get("condition") == "full_hp" and defender.hp_fraction >= 1.0:
                power = int(power * ability_effect.get("damage_mult", 1.0))
                vgc_move = VGCMove(
                    name=move_name, type=move_type, category=category,
                    base_power=power, is_spread=is_spread,
                )
            # こおりのりんぷん (特殊技半減)
            if ability_effect.get("special_mult") and category == "special":
                power = int(power * ability_effect.get("special_mult", 1.0))
                vgc_move = VGCMove(
                    name=move_name, type=move_type, category=category,
                    base_power=power, is_spread=is_spread,
                )
        
        # ダメージ計算
        result = self.damage_calc.calculate(
            atk_vgc, def_vgc, vgc_move,
            is_doubles=True,
            field_conditions=field_conditions,
        )
        
        # 期待ダメージ（HP%）
        expected_damage = (result.min_percent + result.max_percent) / 2 / 100
        
        # きあいのタスキチェック
        def_item = (defender.item or "").lower().replace(" ", "")
        if def_item == "focussash":
            if defender.hp_fraction >= 1.0 and not defender.item_consumed:
                if expected_damage >= defender.hp_fraction:
                    expected_damage = defender.hp_fraction - 0.01
                    defender.item_consumed = True
        
        return result, expected_damage, secondary_effect
    
    def apply_post_damage_effects(
        self,
        pokemon: SimulatedPokemon,
        damage_taken: float,
    ) -> None:
        """ダメージ後の効果を適用（オボン等）"""
        new_hp = pokemon.hp_fraction - damage_taken
        
        # 倒れた判定
        if new_hp <= 0:
            pokemon.hp_fraction = 0
            pokemon.fainted = True
            return
        
        pokemon.hp_fraction = new_hp
        
        # 回復アイテムチェック
        item = (pokemon.item or "").lower().replace(" ", "")
        if item in RECOVERY_ITEMS and not pokemon.item_consumed:
            recovery = RECOVERY_ITEMS[item]
            
            # 50%以下でトリガー
            if recovery.get("trigger") == "below_50" and new_hp < 0.5:
                heal = recovery.get("heal_fraction", 0)
                pokemon.hp_fraction = min(1.0, new_hp + heal)
                pokemon.item_consumed = True
    
    def simulate_attack(
        self,
        attacker: SimulatedPokemon,
        defender: SimulatedPokemon,
        move_name: str,
        field: FieldState,
        is_player_attacking: bool,
    ) -> Dict[str, Any]:
        """
        攻撃をシミュレーション
        
        Phase 23: 追加効果対応
        - やけどは攻撃0.5倍
        - おんみつマントで追加効果無効
        - ちからずくは追加効果無効だが火力1.3倍
        
        Returns:
            {..., secondary_applied: bool, secondary_effect: str}
        """
        # まもるチェック
        if defender.protected:
            return {
                "damage_result": None,
                "hp_change": 0,
                "fainted": False,
                "item_triggered": None,
                "blocked": True,
            }
        
        # ダメージ計算
        result, expected_damage, secondary_effect = self.calculate_damage_with_effects(
            attacker, defender, move_name, field, is_player_attacking
        )
        
        if result.is_immune:
            return {
                "damage_result": result,
                "hp_change": 0,
                "fainted": False,
                "item_triggered": None,
                "immune": True,
            }
        
        # ダメージ適用
        old_hp = defender.hp_fraction
        self.apply_post_damage_effects(defender, expected_damage)
        
        # アイテムトリガー確認
        item_triggered = None
        if defender.item_consumed:
            item_triggered = defender.item
        
        # === 追加効果処理 (Phase 23) ===
        secondary_applied = False
        
        if secondary_effect and not defender.fainted:
            # おんみつマント / コートクロークチェック
            def_item = (defender.item or "").lower().replace(" ", "")
            def_ability = (defender.ability or "").lower().replace(" ", "")
            
            blocks_secondary = def_item in ["covertcloak"] or def_ability in ["shielddust"]
            
            # ちからずくは追加効果を発動しない
            atk_ability = (attacker.ability or "").lower().replace(" ", "")
            if atk_ability == "sheerforce":
                blocks_secondary = True
            
            if not blocks_secondary:
                secondary_applied = self.apply_secondary_effect(
                    defender, secondary_effect, result
                )
        
        return {
            "damage_result": result,
            "hp_change": old_hp - defender.hp_fraction,
            "fainted": defender.fainted,
            "item_triggered": item_triggered,
            "ko_probability": result.ko_chance,
            "n_hits_to_ko": result.n_hits_to_ko,
            "secondary_applied": secondary_applied,
            "secondary_effect": secondary_effect,
        }
    
    def apply_secondary_effect(
        self,
        defender: SimulatedPokemon,
        effect: str,
        damage_result: Any,
    ) -> bool:
        """
        追加効果を適用
        
        Returns:
            適用されたかどうか
        """
        import random
        
        effect_lower = effect.lower()
        
        # やけど
        if "burn" in effect_lower or "やけど" in effect_lower:
            # 確率取得 (例: "burn_10%" -> 0.1)
            prob = self._parse_probability(effect_lower, default=0.1)
            if random.random() < prob and not defender.status:
                # ほのおタイプは火傷しない
                if "Fire" not in defender.types:
                    defender.status = "burn"
                    return True
        
        # まひ
        elif "paralysis" in effect_lower or "まひ" in effect_lower:
            prob = self._parse_probability(effect_lower, default=0.3)
            if random.random() < prob and not defender.status:
                if "Electric" not in defender.types:
                    defender.status = "paralysis"
                    return True
        
        # こおり
        elif "freeze" in effect_lower or "こおり" in effect_lower:
            prob = self._parse_probability(effect_lower, default=0.1)
            if random.random() < prob and not defender.status:
                if "Ice" not in defender.types:
                    defender.status = "freeze"
                    return True
        
        # ひるみ
        elif "flinch" in effect_lower or "ひるみ" in effect_lower:
            prob = self._parse_probability(effect_lower, default=0.3)
            # せいしんりょく等のチェック
            def_ability = (defender.ability or "").lower().replace(" ", "")
            if def_ability not in ["innerfocus", "scrappy", "oblivious"]:
                if random.random() < prob:
                    defender.flinched = True
                    return True
        
        # 能力低下
        elif "lower" in effect_lower:
            return self._apply_stat_drop(defender, effect_lower)
        
        return False
    
    def _parse_probability(self, effect_str: str, default: float = 0.3) -> float:
        """文字列から確率をパース (例: "burn_10%" -> 0.1)"""
        import re
        match = re.search(r'(\d+)%', effect_str)
        if match:
            return int(match.group(1)) / 100
        
        # "100%" が含まれる場合
        if "100" in effect_str:
            return 1.0
        
        return default
    
    def _apply_stat_drop(self, defender: SimulatedPokemon, effect: str) -> bool:
        """能力低下を適用"""
        if "spe" in effect or "素早さ" in effect:
            defender.spe_boost = max(-6, defender.spe_boost - 1)
            return True
        elif "atk" in effect or "攻撃" in effect:
            defender.atk_boost = max(-6, defender.atk_boost - 1)
            return True
        elif "spa" in effect or "特攻" in effect:
            defender.spa_boost = max(-6, defender.spa_boost - 1)
            return True
        elif "def" in effect or "防御" in effect:
            defender.def_boost = max(-6, defender.def_boost - 1)
            return True
        elif "spd" in effect or "特防" in effect:
            defender.spd_boost = max(-6, defender.spd_boost - 1)
            return True
        return False
    
    # =========================================================================
    # 技効果メソッド (Phase 21)
    # =========================================================================
    
    def apply_protect(self, pokemon: SimulatedPokemon) -> bool:
        """
        まもるを適用
        
        Returns:
            成功したかどうか
        """
        # 連続使用による成功率低下: 1回目100%, 2回目50%, 3回目25%, 4回目12.5%...
        success_rate = 1.0 / (2 ** pokemon.protect_count)
        
        import random
        if random.random() < success_rate:
            pokemon.protected = True
            pokemon.protect_count += 1
            return True
        else:
            return False
    
    def can_use_fake_out(self, pokemon: SimulatedPokemon) -> bool:
        """ねこだましが使えるか判定"""
        return pokemon.first_turn and not pokemon.fainted
    
    def apply_fake_out(
        self,
        attacker: SimulatedPokemon,
        defender: SimulatedPokemon,
        field: FieldState,
    ) -> Dict[str, Any]:
        """
        ねこだましを適用
        
        - 登場した最初のターンのみ使用可能
        - 100%怯み
        - せいしんりょく/インナーフォーカスで無効
        """
        if not self.can_use_fake_out(attacker):
            return {"success": False, "reason": "初ターンでない"}
        
        # ダメージ計算
        result = self.simulate_attack(attacker, defender, "fakeout", field, True)
        
        if result.get("blocked") or result.get("immune"):
            return result
        
        # 怯み判定
        def_ability = (defender.ability or "").lower().replace(" ", "")
        immune_to_flinch = def_ability in ["innerfocus", "scrappy", "oblivious"]
        
        if not immune_to_flinch and not defender.fainted:
            defender.flinched = True
        
        result["flinched"] = not immune_to_flinch
        return result
    
    def apply_encore(
        self,
        target: SimulatedPokemon,
        last_move: Optional[str],
    ) -> bool:
        """
        アンコールを適用
        
        - 直前に技を使った相手に有効
        - 3ターン同じ技を強制
        """
        if not last_move or target.fainted:
            return False
        
        target.encored = True
        target.encored_move = last_move
        target.encore_turns = 3
        return True
    
    def apply_tailwind(self, is_player: bool, field: FieldState) -> None:
        """おいかぜを適用 (4ターン持続)"""
        if is_player:
            field.player_tailwind = True
            field.player_tailwind_turns = 4
        else:
            field.opponent_tailwind = True
            field.opponent_tailwind_turns = 4
    
    def apply_trick_room(self, field: FieldState) -> None:
        """トリックルームを適用 (5ターン持続)"""
        field.trick_room = not field.trick_room  # トグル
        field.trick_room_turns = 5 if field.trick_room else 0
    
    def apply_screens(self, move_name: str, is_player: bool, field: FieldState) -> None:
        """壁を適用 (5ターン持続)"""
        move_lower = move_name.lower()
        if "reflect" in move_lower:
            if is_player:
                field.player_reflect = True
            else:
                field.opponent_reflect = True
        elif "lightscreen" in move_lower:
            if is_player:
                field.player_lightscreen = True
            else:
                field.opponent_lightscreen = True
    
    def get_speed_order(
        self,
        player_team: List[SimulatedPokemon],
        opponent_team: List[SimulatedPokemon],
        field: FieldState,
    ) -> List[Tuple[SimulatedPokemon, bool, int]]:
        """
        素早さ順を計算
        
        Returns:
            [(pokemon, is_player, priority), ...] 行動順に並べ替え
        """
        all_pokemon = []
        
        for p in player_team:
            if not p.fainted:
                # 実数値計算 (簡易)
                vgc = self.create_vgc_pokemon(p)
                spe = vgc.calc_spe()
                
                # 追い風
                if field.player_tailwind:
                    spe *= 2
                
                # まひ
                if p.status == "paralysis":
                    spe = int(spe * 0.5)
                
                all_pokemon.append((p, True, spe))
        
        for o in opponent_team:
            if not o.fainted:
                vgc = self.create_vgc_pokemon(o)
                spe = vgc.calc_spe()
                
                if field.opponent_tailwind:
                    spe *= 2
                
                if o.status == "paralysis":
                    spe = int(spe * 0.5)
                
                all_pokemon.append((o, False, spe))
        
        # トリックルーム
        reverse = field.trick_room
        
        return sorted(all_pokemon, key=lambda x: x[2], reverse=not reverse)
    
    def end_turn(
        self,
        player_team: List[SimulatedPokemon],
        opponent_team: List[SimulatedPokemon],
        field: FieldState,
    ) -> None:
        """
        ターン終了処理
        
        - 天候ダメージ
        - 状態異常ダメージ
        - アンコール/追い風カウント減少
        - first_turn解除
        """
        # 全ポケモンの first_turn を解除
        for p in player_team + opponent_team:
            p.first_turn = False
            p.protected = False
            p.flinched = False
            
            # アンコールターン減少
            if p.encored:
                p.encore_turns -= 1
                if p.encore_turns <= 0:
                    p.encored = False
                    p.encored_move = None
            
            # どくどくダメージ (1/16, 2/16, ...)
            if p.status == "toxic" and not p.fainted:
                p.toxic_counter += 1
                damage = min(0.9375, p.toxic_counter * 0.0625)
                p.hp_fraction = max(0, p.hp_fraction - damage)
                if p.hp_fraction <= 0:
                    p.fainted = True
            
            # やけどダメージ (1/16)
            if p.status == "burn" and not p.fainted:
                p.hp_fraction = max(0, p.hp_fraction - 0.0625)
                if p.hp_fraction <= 0:
                    p.fainted = True
        
        # 天候ターン減少
        if field.weather_turns > 0:
            field.weather_turns -= 1
            if field.weather_turns <= 0:
                field.weather = None
        
        # 追い風ターン減少
        if field.player_tailwind_turns > 0:
            field.player_tailwind_turns -= 1
            if field.player_tailwind_turns <= 0:
                field.player_tailwind = False
        
        if field.opponent_tailwind_turns > 0:
            field.opponent_tailwind_turns -= 1
            if field.opponent_tailwind_turns <= 0:
                field.opponent_tailwind = False
        
        # トリックルームターン減少
        if field.trick_room_turns > 0:
            field.trick_room_turns -= 1
            if field.trick_room_turns <= 0:
                field.trick_room = False


# =============================================================================
# シングルトン
# =============================================================================

_simulator: Optional[BattleStateSimulator] = None

def get_battle_state_simulator() -> BattleStateSimulator:
    global _simulator
    if _simulator is None:
        _simulator = BattleStateSimulator()
    return _simulator
