"""
Complete Pokemon Battle Mechanics Database
Based on Pokemon Showdown source (smogon/pokemon-showdown)

This file contains comprehensive battle mechanics extracted from:
- data/abilities.ts
- data/moves.ts  
- data/items.ts
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field


# =============================================================================
# 全特性データベース (VGC関連のみ抜粋)
# =============================================================================

COMPLETE_ABILITIES: Dict[str, Dict[str, Any]] = {
    # --- ダメージ補正特性 ---
    "adaptability": {"stab_mult": 2.0, "desc": "タイプ一致2.0倍"},
    "aerilate": {"type_change": "Normal->Flying", "power_mult": 1.2},
    "pixilate": {"type_change": "Normal->Fairy", "power_mult": 1.2},
    "refrigerate": {"type_change": "Normal->Ice", "power_mult": 1.2},
    "galvanize": {"type_change": "Normal->Electric", "power_mult": 1.2},
    
    "hugepower": {"atk_mult": 2.0},
    "purepower": {"atk_mult": 2.0},
    "hustle": {"atk_mult": 1.5, "accuracy_mult": 0.8},
    "gorillatactics": {"atk_mult": 1.5, "choice_lock": True},
    "sheerforce": {"damage_mult": 1.3, "removes_secondary": True},
    "technician": {"power_mult": 1.5, "condition": "power<=60"},
    "strongjaw": {"power_mult": 1.5, "condition": "bite_moves"},
    "ironfist": {"power_mult": 1.2, "condition": "punch_moves"},
    "toughclaws": {"power_mult": 1.3, "condition": "contact"},
    "analytic": {"power_mult": 1.3, "condition": "moves_last"},
    "neuroforce": {"super_effective_mult": 1.25},
    "sniper": {"crit_mult": 2.25},
    "tintedlens": {"not_very_effective_mult": 2.0},
    
    # --- いかく系 ---
    "intimidate": {"on_switch": "lower_opponent_atk", "stages": -1},
    "intrepidsword": {"on_switch": "boost_atk", "stages": 1},
    "dauntlessshield": {"on_switch": "boost_def", "stages": 1},
    "download": {"on_switch": "boost_atk_or_spa", "stages": 1},
    "supremeoverlord": {"boost_per_fainted": 0.1, "max_boost": 0.5},
    
    # --- いかく無効化 ---
    "defiant": {"on_stat_drop": "boost_atk", "stages": 2},
    "competitive": {"on_stat_drop": "boost_spa", "stages": 2},
    "clearbody": {"prevents": "stat_drops"},
    "whitesmoke": {"prevents": "stat_drops"},
    "fullmetalbody": {"prevents": "stat_drops"},
    "innerfocus": {"prevents": ["flinch", "intimidate"]},
    "owntempo": {"prevents": "confusion"},
    "oblivious": {"prevents": ["attract", "taunt", "intimidate"]},
    "guarddog": {"on_intimidate": "boost_atk", "prevents": "drag_out"},
    "rattled": {"on_intimidate": "boost_spe", "on_hit_by_dark_bug_ghost": "boost_spe"},
    
    # --- 天候特性 ---
    "drought": {"on_switch": "set_weather", "weather": "sun"},
    "drizzle": {"on_switch": "set_weather", "weather": "rain"},
    "sandstream": {"on_switch": "set_weather", "weather": "sand"},
    "snowwarning": {"on_switch": "set_weather", "weather": "snow"},
    "airlock": {"effect": "suppress_weather"},
    "cloudnine": {"effect": "suppress_weather"},
    "desolateland": {"weather": "harsh_sun", "permanent": True},
    "primordialsea": {"weather": "heavy_rain", "permanent": True},
    "deltastream": {"weather": "strong_winds", "permanent": True},
    
    # --- 天候補正 ---
    "chlorophyll": {"spe_mult": 2.0, "condition": "sunny"},
    "swiftswim": {"spe_mult": 2.0, "condition": "rain"},
    "sandrush": {"spe_mult": 2.0, "condition": "sandstorm"},
    "slushrush": {"spe_mult": 2.0, "condition": "snow"},
    "solarpower": {"spa_mult": 1.5, "sun_damage": 0.125, "condition": "sunny"},
    "protosynthesis": {"boosts_highest_stat": True, "condition": "sunny_or_booster_energy"},
    
    # --- フィールド特性 ---
    "electricsurge": {"on_switch": "set_terrain", "terrain": "electric"},
    "psychicsurge": {"on_switch": "set_terrain", "terrain": "psychic"},
    "grassysurge": {"on_switch": "set_terrain", "terrain": "grassy"},
    "mistysurge": {"on_switch": "set_terrain", "terrain": "misty"},
    "hadronengine": {"terrain": "electric", "spa_mult": 1.33},
    "orichalcumpulse": {"weather": "sun", "atk_mult": 1.33},
    "quarkdrive": {"boosts_highest_stat": True, "condition": "electric_terrain_or_booster_energy"},
    
    # --- 免疫特性 ---
    "levitate": {"immunity": "Ground"},
    "flashfire": {"immunity": "Fire", "on_hit": "boost_fire_power"},
    "waterabsorb": {"immunity": "Water", "on_hit": "heal_25%"},
    "voltabsorb": {"immunity": "Electric", "on_hit": "heal_25%"},
    "stormdrain": {"immunity": "Water", "on_hit": "boost_spa"},
    "lightningrod": {"immunity": "Electric", "on_hit": "boost_spa"},
    "sapsipper": {"immunity": "Grass", "on_hit": "boost_atk"},
    "motordrive": {"immunity": "Electric", "on_hit": "boost_spe"},
    "dryskin": {"immunity": "Water", "on_hit": "heal_25%", "fire_weakness": 1.25, "sun_damage": 0.125},
    "eartheater": {"immunity": "Ground", "on_hit": "heal_25%"},
    "wellbakedbody": {"immunity": "Fire", "on_hit": "boost_def"},
    "telepathy": {"immunity": "ally_attacks"},
    
    # --- 耐久特性 ---
    "multiscale": {"damage_mult": 0.5, "condition": "full_hp"},
    "shadowshield": {"damage_mult": 0.5, "condition": "full_hp"},
    "fluffy": {"contact_mult": 0.5, "fire_mult": 2.0},
    "icescales": {"special_mult": 0.5},
    "filter": {"super_effective_mult": 0.75},
    "solidrock": {"super_effective_mult": 0.75},
    "prismarmor": {"super_effective_mult": 0.75},
    "furcoat": {"def_mult": 2.0},
    "marvelscale": {"def_mult": 1.5, "condition": "status"},
    "stamina": {"on_hit": "boost_def"},
    "watercompaction": {"on_hit_by_water": "boost_def_2"},
    
    # --- 状態異常関連 ---
    "guts": {"atk_mult": 1.5, "condition": "status", "ignores_burn": True},
    "quickfeet": {"spe_mult": 1.5, "condition": "status"},
    "flareboost": {"spa_mult": 1.5, "condition": "burn"},
    "toxicboost": {"atk_mult": 1.5, "condition": "poison"},
    "poisonheal": {"on_poison": "heal_12.5%"},
    "magicguard": {"prevents": "indirect_damage"},
    "immunity": {"prevents": "poison"},
    "limber": {"prevents": "paralysis"},
    "waterveil": {"prevents": "burn"},
    "magmaarmor": {"prevents": "freeze"},
    "insomnia": {"prevents": "sleep"},
    "vitalspirit": {"prevents": "sleep"},
    "comatose": {"always_asleep": True, "cannot_status": True},
    
    # --- 接触関連 ---
    "roughskin": {"on_contact": "damage_1/8"},
    "ironbarbs": {"on_contact": "damage_1/8"},
    "flamebody": {"on_contact": "burn_30%"},
    "poisonpoint": {"on_contact": "poison_30%"},
    "static": {"on_contact": "paralysis_30%"},
    "effectspore": {"on_contact": "sleep/poison/paralysis_10%"},
    "cutecharm": {"on_contact": "attract_30%"},
    "gooey": {"on_contact": "lower_spe"},
    "tanglinghair": {"on_contact": "lower_spe"},
    "perishbody": {"on_contact": "perish_count_3"},
    "mummy": {"on_contact": "change_ability_to_mummy"},
    "wanderingspirit": {"on_contact": "swap_abilities"},
    
    # --- 優先度関連 ---
    "prankster": {"priority": 1, "condition": "status_moves"},
    "galewings": {"priority": 1, "condition": "flying_moves_full_hp"},
    "triage": {"priority": 3, "condition": "healing_moves"},
    "quickdraw": {"priority": "random_first", "chance": 0.3},
    
    # --- その他重要 ---
    "unaware": {"ignores": "opponent_stat_changes"},
    "contrary": {"inverts": "stat_changes"},
    "simple": {"doubles": "stat_changes"},
    "beastboost": {"on_ko": "boost_highest_stat"},
    "soulheart": {"on_ko": "boost_spa"},
    "moxie": {"on_ko": "boost_atk"},
    "grimneigh": {"on_ko": "boost_spa"},
    "chillingneigh": {"on_ko": "boost_atk"},
    "asone": {"combines": ["unnerve", "grimneigh_or_chillingneigh"]},
    "unseenfist": {"pierces": "protect"},
    "parentalbond": {"hits_twice": True, "second_hit_power": 0.25},
    "trace": {"copies_ability": True},
    "imposter": {"transforms": True},
    "shadowtag": {"prevents": "switching"},
    "arenatrap": {"prevents": "switching", "condition": "grounded"},
    "magnetpull": {"prevents": "switching", "condition": "steel_type"},
    "moldbreaker": {"ignores": "defensive_abilities"},
    "teravolt": {"ignores": "defensive_abilities"},
    "turboblaze": {"ignores": "defensive_abilities"},
    "myceliummight": {"ignores": "defensive_abilities", "condition": "status_moves", "priority": -1},
    "neutralizinggas": {"suppresses": "all_other_abilities"},
    
    # --- わざわい特性 (災い) ---
    "swordsofruin": {"atk_mult": 1.25, "effect": "lower_opponent_def"},
    "tabletsofruin": {"effect": "lower_opponent_atk_25%"},
    "vesselsofruin": {"effect": "lower_opponent_spa_25%"},
    "beadsofruin": {"effect": "lower_opponent_spd_25%"},
}


# =============================================================================
# 全技データベース (VGC重要技)
# =============================================================================

COMPLETE_MOVES: Dict[str, Dict[str, Any]] = {
    # --- 優先度技 ---
    "protect": {"priority": 4, "effect": "protect", "consecutive_fail": True},
    "detect": {"priority": 4, "effect": "protect", "consecutive_fail": True},
    "wideguard": {"priority": 3, "effect": "protect_spread"},
    "quickguard": {"priority": 3, "effect": "protect_priority"},
    "kingsshield": {"priority": 4, "effect": "protect", "on_contact": "lower_atk_1"},
    "spikyshield": {"priority": 4, "effect": "protect", "on_contact": "damage_1/8"},
    "banefulbunker": {"priority": 4, "effect": "protect", "on_contact": "poison"},
    "obstruct": {"priority": 4, "effect": "protect", "on_contact": "lower_def_2"},
    "silktrap": {"priority": 4, "effect": "protect", "on_contact": "lower_spe_1"},
    
    "fakeout": {"priority": 3, "effect": "flinch_100%", "first_turn_only": True},
    "feint": {"priority": 2, "effect": "breaks_protect", "power": 30},
    "extremespeed": {"priority": 2, "power": 80},
    "suckerpunch": {"priority": 1, "power": 70, "condition": "opponent_using_attack"},
    "aquajet": {"priority": 1, "power": 40},
    "bulletseed": {"priority": 1, "power": 40},
    "machpunch": {"priority": 1, "power": 40},
    "iceshard": {"priority": 1, "power": 40},
    "shadowsneak": {"priority": 1, "power": 40},
    "accelerock": {"priority": 1, "power": 40},
    "jetpunch": {"priority": 1, "power": 60},
    "aquastep": {"priority": 0, "power": 80, "secondary": "boost_spe_1"},
    
    # --- ネガティブ優先度 ---
    "trickroom": {"priority": -7, "effect": "set_trick_room", "turns": 5},
    "teleport": {"priority": -6, "effect": "switch_out"},
    "roar": {"priority": -6, "effect": "force_switch"},
    "whirlwind": {"priority": -6, "effect": "force_switch"},
    "counter": {"priority": -5, "effect": "double_physical_damage"},
    "mirrorcoat": {"priority": -5, "effect": "double_special_damage"},
    "focuspunch": {"priority": -3, "power": 150, "condition": "not_hit_first"},
    
    # --- 全体技 ---
    "heatwave": {"power": 95, "target": "allAdjacentFoes", "accuracy": 90, "secondary": "burn_10%"},
    "earthquake": {"power": 100, "target": "allAdjacent", "hits_allies": True},
    "rockslide": {"power": 75, "target": "allAdjacentFoes", "secondary": "flinch_30%"},
    "dazzlinggleam": {"power": 80, "target": "allAdjacentFoes"},
    "blizzard": {"power": 110, "target": "allAdjacentFoes", "accuracy": 70, "secondary": "freeze_10%"},
    "discharge": {"power": 80, "target": "allAdjacent", "hits_allies": True, "secondary": "paralysis_30%"},
    "snarl": {"power": 55, "target": "allAdjacentFoes", "secondary": "lower_spa_1"},
    "icywind": {"power": 55, "target": "allAdjacentFoes", "secondary": "lower_spe_1"},
    "muddywater": {"power": 90, "target": "allAdjacentFoes", "secondary": "lower_accuracy_1"},
    "astralbarrage": {"power": 120, "target": "allAdjacentFoes", "type": "Ghost"},
    "electrowebf": {"power": 55, "target": "allAdjacentFoes", "secondary": "lower_spe_1"},
    "makeitrain": {"power": 120, "target": "allAdjacentFoes", "secondary": "lower_own_spa_1"},
    
    # --- 変化技 (優先度なし) ---
    "tailwind": {"effect": "set_tailwind", "turns": 4, "spe_mult": 2.0},
    "reflect": {"effect": "set_reflect", "turns": 5, "physical_mult": 0.5},
    "lightscreen": {"effect": "set_lightscreen", "turns": 5, "special_mult": 0.5},
    "auroraveil": {"effect": "set_aurora_veil", "condition": "hail/snow", "turns": 5, "damage_mult": 0.5},
    "encore": {"effect": "lock_move", "turns": 3},
    "taunt": {"effect": "prevent_status_moves", "turns": 3},
    "disable": {"effect": "disable_last_move", "turns": 4},
    "imprison": {"effect": "prevent_shared_moves"},
    "healingwish": {"effect": "heal_switch_in_full"},
    "lunardance": {"effect": "heal_switch_in_full_pp"},
    "helpinghand": {"priority": 5, "effect": "boost_ally_power_1.5x"},
    "allyswitch": {"priority": 1, "effect": "swap_positions"},
    "followme": {"priority": 2, "effect": "redirect_attacks"},
    "ragepowder": {"priority": 2, "effect": "redirect_attacks", "type": "Bug"},
    
    # --- 連続技 ---
    "surgingstrikes": {"power": 25, "hits": 3, "always_crit": True},
    "wickedblow": {"power": 75, "always_crit": True},
    "populationbomb": {"power": 20, "hits": "1-10"},
    "bulletseed": {"power": 25, "hits": "2-5"},
    "iciclespear": {"power": 25, "hits": "2-5"},
    "rockblast": {"power": 25, "hits": "2-5"},
    "scaleshot": {"power": 25, "hits": "2-5", "secondary": "boost_spe_1", "lower_def_1": True},
    "tripleaxel": {"power": "20+20+20", "hits": 3, "power_increases": True},
    "tripledive": {"power": "30+30+30", "hits": 3},
    
    # --- 特殊条件技 ---
    "glare": {"effect": "paralysis", "accuracy": 100, "affects_ground": True},
    "thunderwave": {"effect": "paralysis", "accuracy": 90, "type": "Electric"},
    "willowisp": {"effect": "burn", "accuracy": 85},
    "spore": {"effect": "sleep", "accuracy": 100, "type": "Grass"},
    "sleeppowder": {"effect": "sleep", "accuracy": 75},
    "yawn": {"effect": "sleep_next_turn"},
    "swagger": {"effect": "confuse", "boost_atk_2": True},
    "flatter": {"effect": "confuse", "boost_spa_2": True},
    
    # --- 回復技 ---
    "recover": {"effect": "heal_50%"},
    "roost": {"effect": "heal_50%", "removes_flying": True},
    "softboiled": {"effect": "heal_50%"},
    "slackoff": {"effect": "heal_50%"},
    "synthesis": {"effect": "heal_weather_dependent"},
    "morningsun": {"effect": "heal_weather_dependent"},
    "pollenpuff": {"power": 90, "effect": "heal_ally_or_damage_enemy"},
    "lifedew": {"effect": "heal_25%_all_allies"},
    
    # --- 固定ダメージ ---
    "seismictoss": {"damage": "level"},
    "nightshade": {"damage": "level"},
    "superfang": {"damage": "50%_current_hp"},
    "endeavor": {"damage": "match_hp"},
    "finalgambit": {"damage": "user_hp", "user_faints": True},
}


# =============================================================================
# 全アイテムデータベース
# =============================================================================

COMPLETE_ITEMS: Dict[str, Dict[str, Any]] = {
    # --- こだわり系 ---
    "choiceband": {"atk_mult": 1.5, "locks_move": True},
    "choicespecs": {"spa_mult": 1.5, "locks_move": True},
    "choicescarf": {"spe_mult": 1.5, "locks_move": True},
    
    # --- 火力アイテム ---
    "lifeorb": {"damage_mult": 1.3, "recoil": 0.1},
    "expertbelt": {"super_effective_mult": 1.2},
    "muscleband": {"physical_mult": 1.1},
    "wiseglasses": {"special_mult": 1.1},
    "metronome": {"consecutive_mult": 0.2, "max": 2.0},
    "punchingglove": {"punch_mult": 1.1, "no_contact": True},
    "loadeddice": {"multi_hit_4+": True},
    
    # --- タイプ強化 ---
    "charcoal": {"type_mult": 1.2, "type": "Fire"},
    "mysticwater": {"type_mult": 1.2, "type": "Water"},
    "miracleseed": {"type_mult": 1.2, "type": "Grass"},
    "magnet": {"type_mult": 1.2, "type": "Electric"},
    "nevermeltice": {"type_mult": 1.2, "type": "Ice"},
    "blackbelt": {"type_mult": 1.2, "type": "Fighting"},
    "poisonbarb": {"type_mult": 1.2, "type": "Poison"},
    "softsand": {"type_mult": 1.2, "type": "Ground"},
    "sharpbeak": {"type_mult": 1.2, "type": "Flying"},
    "twistedspoon": {"type_mult": 1.2, "type": "Psychic"},
    "silverpowder": {"type_mult": 1.2, "type": "Bug"},
    "hardstone": {"type_mult": 1.2, "type": "Rock"},
    "spelltag": {"type_mult": 1.2, "type": "Ghost"},
    "dragonfang": {"type_mult": 1.2, "type": "Dragon"},
    "blackglasses": {"type_mult": 1.2, "type": "Dark"},
    "metalcoat": {"type_mult": 1.2, "type": "Steel"},
    "fairyfeather": {"type_mult": 1.2, "type": "Fairy"},
    
    # --- 耐久アイテム ---
    "focussash": {"survives_ohko": True, "condition": "full_hp", "single_use": True},
    "focusband": {"survives_ko": True, "chance": 0.1},
    "eviolite": {"def_mult": 1.5, "spd_mult": 1.5, "condition": "not_fully_evolved"},
    "assaultvest": {"spd_mult": 1.5, "prevents": "status_moves"},
    "rockyhelmet": {"on_contact": "damage_1/6"},
    "airballoon": {"immunity": "Ground", "pops_on_hit": True},
    "safetygoggles": {"immunity": ["powder", "weather_damage"]},
    "covertcloak": {"prevents": "secondary_effects"},
    "clearamulet": {"prevents": "stat_drops"},
    
    # --- 回復アイテム ---
    "sitrusberry": {"trigger": "hp<=50%", "heal": 0.25, "single_use": True},
    "figyberry": {"trigger": "hp<=25%", "heal": 0.33, "confuse_if_dislike": True},
    "aguavberry": {"trigger": "hp<=25%", "heal": 0.33},
    "iapapaberry": {"trigger": "hp<=25%", "heal": 0.33},
    "magoberry": {"trigger": "hp<=25%", "heal": 0.33},
    "wikiberry": {"trigger": "hp<=25%", "heal": 0.33},
    "leftovers": {"end_of_turn": "heal_1/16"},
    "blacksludge": {"end_of_turn": "heal_1/16_poison_only", "damage_if_not_poison": True},
    "shellbell": {"on_damage": "heal_1/8_damage_dealt"},
    
    # --- 状態異常アイテム ---
    "lumberry": {"cures": "any_status", "single_use": True},
    "rawstberry": {"cures": "burn", "single_use": True},
    "cheriberry": {"cures": "paralysis", "single_use": True},
    "chestoberry": {"cures": "sleep", "single_use": True},
    "pechaberry": {"cures": "poison", "single_use": True},
    "aspearberry": {"cures": "freeze", "single_use": True},
    "persimberry": {"cures": "confusion", "single_use": True},
    "mentalherb": {"cures": ["infatuation", "taunt", "encore", "disable"], "single_use": True},
    
    # --- 特殊アイテム ---
    "boosterenergy": {"activates": ["protosynthesis", "quarkdrive"]},
    "throatspray": {"on_sound_move": "boost_spa_1", "single_use": True},
    "weaknesspolicy": {"on_super_effective": "boost_atk_spa_2", "single_use": True},
    "whiteherb": {"on_stat_drop": "restore_stats", "single_use": True},
    "redcard": {"on_hit": "force_switch_attacker", "single_use": True},
    "ejectbutton": {"on_hit": "switch_out", "single_use": True},
    "ejectpack": {"on_stat_drop": "switch_out", "single_use": True},
    "roomservice": {"on_trick_room": "lower_spe_1", "single_use": True},
    "blunderpolicy": {"on_miss": "boost_spe_2", "single_use": True},
    "mirrorherb": {"copies_stat_boosts": True, "single_use": True},
    
    # --- 速度関連 ---
    "ironball": {"spe_mult": 0.5, "grounds": True},
    "machobrace": {"spe_mult": 0.5},
    "quickclaw": {"priority_chance": 0.2},
    "laggingtail": {"moves_last": True},
    "fullincense": {"moves_last": True},
}


# =============================================================================
# 状態異常完全データ
# =============================================================================

STATUS_EFFECTS: Dict[str, Dict[str, Any]] = {
    "burn": {
        "damage_per_turn": 0.0625,  # 1/16
        "atk_mult": 0.5,
        "cured_by": ["rawstberry", "lumberry", "healbell", "aromatherapy"],
        "immune": ["Fire", "waterveil", "comatose"],
    },
    "paralysis": {
        "spe_mult": 0.5,
        "full_paralysis_chance": 0.25,
        "cured_by": ["cheriberry", "lumberry", "healbell", "aromatherapy"],
        "immune": ["Electric", "limber", "comatose"],
    },
    "poison": {
        "damage_per_turn": 0.125,  # 1/8
        "cured_by": ["pechaberry", "lumberry", "healbell", "aromatherapy"],
        "immune": ["Poison", "Steel", "immunity", "comatose"],
    },
    "toxic": {
        "damage_per_turn": "1/16 * turns",  # 累積
        "max_damage": 0.9375,  # 15/16
        "cured_by": ["pechaberry", "lumberry", "healbell", "aromatherapy"],
        "immune": ["Poison", "Steel", "immunity", "comatose"],
    },
    "sleep": {
        "cannot_move": True,
        "turns": "1-3",
        "cured_by": ["chestoberry", "lumberry", "wakeupslap"],
        "immune": ["insomnia", "vitalspirit", "comatose"],
    },
    "freeze": {
        "cannot_move": True,
        "thaw_chance": 0.2,
        "thaw_moves": ["flamewheel", "sacredfire", "scald", "scorchingsands"],
        "cured_by": ["aspearberry", "lumberry"],
        "immune": ["Ice", "magmaarmor", "comatose"],
    },
}


# =============================================================================
# ダブルバトル専用メカニクス
# =============================================================================

DOUBLES_MECHANICS: Dict[str, Any] = {
    "spread_damage_mult": 0.75,  # 全体技は0.75倍
    "position_matters": True,    # 位置によるターゲット
    "ally_switch_priority": 1,   # アリーなりかわりの優先度
    "follow_me_priority": 2,     # このゆびの優先度
    "helping_hand_mult": 1.5,    # てだすけ倍率
    "protect_blocks_ally": False,  # まもるは味方の全体技を止めない
    "earthquake_hits_ally": True,  # じしんは味方に当たる
    "telepathy_prevents_ally_damage": True,  # テレパシーで味方の攻撃免除
}


# =============================================================================
# ヘルパー関数
# =============================================================================

def get_ability_data(ability_name: str) -> Optional[Dict[str, Any]]:
    """特性データを取得"""
    return COMPLETE_ABILITIES.get(ability_name.lower().replace(" ", "").replace("-", ""))

def get_move_data(move_name: str) -> Optional[Dict[str, Any]]:
    """技データを取得"""
    return COMPLETE_MOVES.get(move_name.lower().replace(" ", "").replace("-", ""))

def get_item_data(item_name: str) -> Optional[Dict[str, Any]]:
    """アイテムデータを取得"""
    return COMPLETE_ITEMS.get(item_name.lower().replace(" ", "").replace("-", ""))

def get_status_data(status_name: str) -> Optional[Dict[str, Any]]:
    """状態異常データを取得"""
    return STATUS_EFFECTS.get(status_name.lower())
