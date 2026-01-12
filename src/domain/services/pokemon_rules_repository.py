"""
Pokemon Rules Repository - ポケモンルール統合リポジトリ

既存の各種ルール実装を統合し、一元的にアクセスできるようにする。
CandidateScorerやBattle AIから使用。

統合対象:
- type_chart.py: タイプ相性
- move_effect_db.py: 技効果
- ability_db.py: 特性
- base_stats_db.py: 種族値
- item_effects.py: アイテム効果
- move_properties.py: 技優先度
- generation_config.py: 世代別ルール
- turn_order_service.py: 行動順計算
- damage_calc_service.py: 精密ダメージ計算
- ev_estimator.py: EV推定
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple

# --- 既存モジュールのインポート ---
from src.domain.models.type_chart import (
    get_type_effectiveness, TYPE_CHART
)
from src.domain.models.item_effects import (
    get_item_effect, is_choice_item, blocks_status_moves, 
    get_boost_multiplier, ItemEffect
)
from src.domain.models.move_properties import (
    get_move_priority, is_priority_move, is_conditional_priority,
    get_move_score_bonus, PRIORITY_MOVES
)
from src.domain.models.generation_config import (
    get_generation_manager, set_generation, 
    GenerationConfig, SpecialMechanic, GENERATION_CONFIGS
)
from src.domain.services.move_effect_db import (
    get_move_effect_db, MoveInfo, MOVE_DATABASE
)
from src.domain.services.ability_db import (
    get_ability_db, AbilityInfo, ABILITY_DATABASE
)
from src.domain.services.base_stats_db import (
    get_base_stats_db, BaseStats, PokemonData, POKEMON_DATABASE
)


@dataclass
class DamageContext:
    """ダメージ計算コンテキスト"""
    attacker_name: str
    defender_name: str
    move_name: str
    move_type: str
    move_power: int
    move_category: str = "physical"
    
    attacker_item: Optional[str] = None
    attacker_ability: Optional[str] = None
    defender_ability: Optional[str] = None
    defender_item: Optional[str] = None
    
    weather: Optional[str] = None
    terrain: Optional[str] = None
    is_terastallized: bool = False
    tera_type: Optional[str] = None
    is_dynamaxed: bool = False


@dataclass
class DamageResult:
    """ダメージ計算結果"""
    min_percent: float
    max_percent: float
    expected_percent: float
    is_ko: bool
    effectiveness: float
    notes: List[str]


class PokemonRulesRepository:
    """
    ポケモンルール統合リポジトリ
    
    全てのルール関連データに一元的にアクセスするためのファサード。
    """
    
    def __init__(self, generation: int = 9):
        self.generation = generation
        self.gen_manager = get_generation_manager(generation)
        self._move_db = get_move_effect_db()
        self._ability_db = get_ability_db()
        self._stats_db = get_base_stats_db()
    
    def set_generation(self, gen: int) -> None:
        """世代を切り替える"""
        self.generation = gen
        self.gen_manager.set_generation(gen)
    
    # ===== タイプ相性 =====
    
    def get_type_effectiveness(
        self,
        attack_type: str, 
        defender_types: List[str],
    ) -> float:
        """タイプ相性倍率を取得"""
        return get_type_effectiveness(attack_type, defender_types)
    
    def is_immune(self, attack_type: str, defender_types: List[str]) -> bool:
        """無効かどうか"""
        return self.get_type_effectiveness(attack_type, defender_types) == 0.0
    
    def is_super_effective(self, attack_type: str, defender_types: List[str]) -> bool:
        """抜群かどうか"""
        return self.get_type_effectiveness(attack_type, defender_types) >= 2.0
    
    # ===== 技情報 =====
    
    def get_move_info(self, move_name: str) -> Optional[MoveInfo]:
        """技情報を取得"""
        return self._move_db.get_move_info(move_name)
    
    def get_move_power(self, move_name: str) -> int:
        """技威力を取得"""
        info = self.get_move_info(move_name)
        return info.power if info and info.power else 80
    
    def get_move_priority_value(self, move_name: str) -> int:
        """技優先度を取得"""
        # まずmove_effect_dbをチェック
        info = self.get_move_info(move_name)
        if info:
            return info.priority
        # なければmove_propertiesをチェック
        return get_move_priority(move_name)
    
    # ===== 特性情報 =====
    
    def get_ability_info(self, ability_name: str) -> Optional[AbilityInfo]:
        """特性情報を取得"""
        return self._ability_db.get_ability_info(ability_name)
    
    def get_ability_damage_modifier(self, ability: str) -> float:
        """特性によるダメージ倍率"""
        return self._ability_db.get_damage_modifier(ability)
    
    def is_ability_immune(self, ability: str, move_type: str) -> bool:
        """特性による免疫"""
        return self._ability_db.is_immune_to_type(ability, move_type)
    
    # ===== 種族値情報 =====
    
    def get_pokemon_data(self, pokemon_name: str) -> Optional[PokemonData]:
        """ポケモンデータを取得"""
        return self._stats_db.get_pokemon_data(pokemon_name)
    
    def get_base_stats(self, pokemon_name: str) -> Optional[BaseStats]:
        """種族値を取得"""
        return self._stats_db.get_base_stats(pokemon_name)
    
    def get_base_speed(self, pokemon_name: str) -> int:
        """素早さ種族値を取得"""
        return self._stats_db.get_base_speed(pokemon_name)
    
    # ===== アイテム情報 =====
    
    def get_item_effect(self, item_name: str) -> Optional[ItemEffect]:
        """アイテム効果を取得"""
        return get_item_effect(item_name)
    
    def get_item_boost(self, item_name: str) -> float:
        """アイテムによる倍率"""
        return get_boost_multiplier(item_name)
    
    def is_choice_locked(self, item_name: str) -> bool:
        """こだわり系アイテムか"""
        return is_choice_item(item_name)
    
    # ===== 世代別ギミック =====
    
    def get_generation_config(self) -> GenerationConfig:
        """現在の世代設定を取得"""
        return self.gen_manager.current_config
    
    def get_available_generations(self) -> List[Dict[str, Any]]:
        """利用可能な世代一覧"""
        return self.gen_manager.get_available_generations()
    
    def can_use_mechanic(self) -> bool:
        """特殊ギミックが使用可能か"""
        return self.gen_manager.can_use_mechanic()
    
    def get_current_mechanic(self) -> SpecialMechanic:
        """現在の世代の特殊ギミック"""
        return self.gen_manager.current_mechanic
    
    # ===== ダメージ計算 =====
    
    def estimate_damage(self, context: DamageContext) -> DamageResult:
        """簡易ダメージ計算"""
        # 種族値取得
        atk_stats = self.get_base_stats(context.attacker_name)
        def_stats = self.get_base_stats(context.defender_name)
        
        is_physical = context.move_category == "physical"
        
        # 攻撃ステータス
        if atk_stats:
            atk = atk_stats.attack if is_physical else atk_stats.special_attack
        else:
            atk = 100
        
        # 防御ステータス
        if def_stats:
            defense = def_stats.defense if is_physical else def_stats.special_defense
        else:
            defense = 100
        
        # タイプ相性
        eff = self.get_type_effectiveness(
            context.move_type, 
            self._stats_db.get_types(context.defender_name)
        )
        
        notes = []
        
        # 免疫チェック
        if eff == 0.0:
            return DamageResult(0, 0, 0, False, eff, ["無効"])
        
        # 特性免疫チェック  
        if context.defender_ability:
            if self.is_ability_immune(context.defender_ability, context.move_type):
                notes.append(f"{context.defender_ability}で無効")
                return DamageResult(0, 0, 0, False, 0.0, notes)
        
        # 基本ダメージ
        power = context.move_power or 80
        base = (power * atk / defense / 200.0) * eff
        
        # アイテム倍率
        item_mult = self.get_item_boost(context.attacker_item or "")
        base *= item_mult
        if item_mult > 1.0:
            notes.append(f"アイテム×{item_mult}")
        
        # 特性倍率
        ability_mult = self.get_ability_damage_modifier(context.attacker_ability or "")
        base *= ability_mult
        if ability_mult > 1.0:
            notes.append(f"特性×{ability_mult}")
        
        # テラスタル
        if context.is_terastallized and context.tera_type == context.move_type:
            base *= 1.5
            notes.append("テラスタル一致")
        
        # ダイマックス
        if context.is_dynamaxed:
            base *= 0.5  # ダイマックス相手へのダメージ半減
            notes.append("ダイマックス相手")
        
        # 乱数幅
        min_dmg = base * 0.85
        max_dmg = base * 1.0
        expected = base * 0.925
        
        is_ko = max_dmg >= 1.0
        
        if eff >= 2.0:
            notes.append("効果抜群")
        elif eff < 1.0:
            notes.append("効果今一つ")
        
        return DamageResult(
            min_percent=min_dmg,
            max_percent=max_dmg,
            expected_percent=expected,
            is_ko=is_ko,
            effectiveness=eff,
            notes=notes,
        )
    
    # ===== 行動順序 =====
    
    def get_speed_order(
        self,
        pokemon_list: List[Dict[str, Any]],
        weather: Optional[str] = None,
        trick_room: bool = False,
        tailwind_active: Dict[str, bool] = None,
    ) -> List[Tuple[str, float]]:
        """行動順序を計算"""
        tailwind_active = tailwind_active or {}
        speeds = []
        
        for poke in pokemon_list:
            name = poke.get("name", "")
            base_speed = self.get_base_speed(name)
            
            # 実効素早さ計算
            speed = base_speed  # 簡易版
            
            # アイテム
            item = poke.get("item", "")
            if item.lower() == "choicescarf":
                speed *= 1.5
            
            # 特性
            ability = poke.get("ability", "")
            ability_info = self.get_ability_info(ability)
            if ability_info and ability_info.speed_modifier:
                speed_mod = self._ability_db.get_speed_modifier(ability, weather)
                speed *= speed_mod
            
            # 追い風
            is_player = poke.get("is_player", True)
            if tailwind_active.get("player" if is_player else "opponent"):
                speed *= 2.0
            
            speeds.append((name, speed))
        
        # ソート
        speeds.sort(key=lambda x: x[1], reverse=not trick_room)
        
        return speeds
    
    # ===== 精密ダメージ計算 (DamageCalcService使用) =====
    
    def precise_calculate(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        move: Dict[str, Any],
        field_conditions: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        DamageCalcServiceを使った精密ダメージ計算
        
        Returns:
            {
                "min_damage": int,
                "max_damage": int,
                "expected_percent": float,
                "ko_prob": float,
                "n_hits_to_ko": int,
                "two_turn_ko_prob": float,
                "is_immune": bool,
                "type_effectiveness": float,
            }
        """
        from src.domain.services.damage_calc_service import (
            DamageCalcService, PokemonStats, MoveData, get_damage_calc_service
        )
        
        calc = get_damage_calc_service()
        
        # PokemonStatsを構築
        atk_stats = self._build_pokemon_stats(attacker)
        def_stats = self._build_pokemon_stats(defender)
        
        # MoveDataを構築
        move_data = self._build_move_data(move)
        
        # 計算実行
        result = calc.calculate(atk_stats, def_stats, move_data, field_conditions)
        
        return {
            "min_damage": result.min_damage,
            "max_damage": result.max_damage,
            "expected_percent": result.expected,
            "ko_prob": result.ko_prob,
            "n_hits_to_ko": result.n_hits_to_ko,
            "two_turn_ko_prob": result.two_turn_ko_prob,
            "is_immune": result.is_immune,
            "type_effectiveness": result.type_effectiveness,
        }
    
    def _build_pokemon_stats(self, poke: Dict[str, Any]) -> Any:
        """Dict形式のポケモンからPokemonStatsを構築"""
        from src.domain.services.damage_calc_service import PokemonStats
        
        name = poke.get("name", "")
        base = self.get_base_stats(name)
        
        # EVベースの実数値計算
        level = poke.get("level", 50)
        evs = poke.get("evs", {})
        ivs = poke.get("ivs", {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31})
        nature_boost = poke.get("nature_boost", {})  # {"atk": 1.1, "spe": 0.9} 等
        
        def calc_stat(base_val: int, stat_name: str, is_hp: bool = False) -> int:
            """実数値計算: ((種族値*2 + 個体値 + 努力値/4) * Lv/100) + (HP:Lv+10, 他:5)"""
            iv = ivs.get(stat_name, 31)
            ev = evs.get(stat_name, 0)
            
            if is_hp:
                val = (base_val * 2 + iv + ev // 4) * level // 100 + level + 10
            else:
                val = (base_val * 2 + iv + ev // 4) * level // 100 + 5
                # 性格補正
                nat = nature_boost.get(stat_name, 1.0)
                val = int(val * nat)
            
            return val
        
        if base:
            hp = calc_stat(base.hp, "hp", is_hp=True)
            attack = calc_stat(base.attack, "atk")
            defense = calc_stat(base.defense, "def")
            spa = calc_stat(base.special_attack, "spa")
            spd = calc_stat(base.special_defense, "spd")
            speed = calc_stat(base.speed, "spe")
            types_list = self._stats_db.get_types(name)
        else:
            # デフォルト値
            hp = poke.get("hp", 150)
            attack = poke.get("attack", 100)
            defense = poke.get("defense", 100)
            spa = poke.get("special_attack", 100)
            spd = poke.get("special_defense", 100)
            speed = poke.get("speed", 100)
            types_list = poke.get("types", ["Normal"])
        
        # HP割合から現在HP計算
        hp_fraction = poke.get("hp_fraction", 1.0)
        current_hp = int(hp * hp_fraction)
        
        return PokemonStats(
            species=name,
            hp=current_hp,
            max_hp=hp,
            attack=attack,
            defense=defense,
            special_attack=spa,
            special_defense=spd,
            speed=speed,
            types=types_list,
            ability=poke.get("ability"),
            item=poke.get("item"),
            terastallized=poke.get("tera_type") if poke.get("is_terastallized") else None,
            atk_boost=poke.get("boosts", {}).get("atk", 0),
            def_boost=poke.get("boosts", {}).get("def", 0),
            spa_boost=poke.get("boosts", {}).get("spa", 0),
            spd_boost=poke.get("boosts", {}).get("spd", 0),
            spe_boost=poke.get("boosts", {}).get("spe", 0),
        )
    
    def _build_move_data(self, move: Dict[str, Any]) -> Any:
        """Dict形式の技からMoveDataを構築"""
        from src.domain.services.damage_calc_service import MoveData
        
        move_name = move.get("name", "attack")
        move_info = self.get_move_info(move_name)
        
        if move_info:
            return MoveData(
                id=move_name,
                name=move_info.japanese_name,
                type=move_info.type,
                category=move_info.category,
                base_power=move_info.power or 0,
                priority=move_info.priority,
                is_spread=move_info.target in ["allAdjacentFoes", "allAdjacent", "all"],
            )
        else:
            return MoveData(
                id=move_name,
                name=move_name,
                type=move.get("move_type", move.get("type", "Normal")),
                category=move.get("category", "physical"),
                base_power=move.get("power", move.get("base_power", 80)),
                priority=move.get("priority", 0),
                is_spread=False,
            )
    
    # ===== EV/性格ベースのステータス計算 =====
    
    def calculate_real_stat(
        self,
        pokemon_name: str,
        stat_name: str,
        ev: int = 252,
        iv: int = 31,
        level: int = 50,
        nature_modifier: float = 1.0,
    ) -> int:
        """
        種族値+EV+IV+性格から実数値を計算
        
        Args:
            pokemon_name: ポケモン名
            stat_name: "hp", "atk", "def", "spa", "spd", "spe"
            ev: 努力値 (0-252)
            iv: 個体値 (0-31)
            level: レベル (通常50)
            nature_modifier: 性格補正 (0.9, 1.0, 1.1)
        
        Returns:
            実数値
        """
        base = self.get_base_stats(pokemon_name)
        if not base:
            return 100  # デフォルト
        
        stat_map = {
            "hp": base.hp,
            "atk": base.attack,
            "def": base.defense,
            "spa": base.special_attack,
            "spd": base.special_defense,
            "spe": base.speed,
        }
        
        base_val = stat_map.get(stat_name, 100)
        
        if stat_name == "hp":
            # HP: ((種族値*2 + IV + EV/4) * Lv/100) + Lv + 10
            return (base_val * 2 + iv + ev // 4) * level // 100 + level + 10
        else:
            # 他: ((種族値*2 + IV + EV/4) * Lv/100 + 5) * 性格
            val = (base_val * 2 + iv + ev // 4) * level // 100 + 5
            return int(val * nature_modifier)
    
    def get_vgc_common_spreads(self, pokemon_name: str) -> List[Dict[str, Any]]:
        """
        VGCでよく使われるEV配分を返す
        
        Returns:
            [{"label": "最速", "nature": "Jolly", "evs": {...}, "stats": {...}}]
        """
        base = self.get_base_stats(pokemon_name)
        if not base:
            return []
        
        spreads = []
        
        # 最速 (252-0-0-0-4-252, 陽気)
        max_speed = self.calculate_real_stat(pokemon_name, "spe", ev=252, nature_modifier=1.1)
        spreads.append({
            "label": "最速",
            "nature": "Jolly/Timid",
            "evs": {"atk": 252, "spd": 4, "spe": 252},
            "stats": {"spe": max_speed},
        })
        
        # 準速 (252-0-0-0-4-252, 意地っ張り/控えめ)
        sub_speed = self.calculate_real_stat(pokemon_name, "spe", ev=252, nature_modifier=1.0)
        spreads.append({
            "label": "準速",
            "nature": "Adamant/Modest",
            "evs": {"atk": 252, "spd": 4, "spe": 252},
            "stats": {"spe": sub_speed},
        })
        
        # 耐久振り
        hp_max = self.calculate_real_stat(pokemon_name, "hp", ev=252)
        spreads.append({
            "label": "耐久振り",
            "nature": "Various",
            "evs": {"hp": 252, "def": 128, "spd": 128},
            "stats": {"hp": hp_max},
        })
        
        return spreads


# Singleton
_pokemon_rules_repo = None

def get_pokemon_rules_repository(generation: int = 9) -> PokemonRulesRepository:
    global _pokemon_rules_repo
    if _pokemon_rules_repo is None:
        _pokemon_rules_repo = PokemonRulesRepository(generation)
    return _pokemon_rules_repo
