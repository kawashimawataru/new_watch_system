"""
Base Stats Database - 種族値データベース

VGCで使われるポケモンの種族値を定義。
ダメージ計算・素早さ比較に使用。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class BaseStats:
    """種族値"""
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "hp": self.hp,
            "atk": self.attack,
            "def": self.defense,
            "spa": self.special_attack,
            "spd": self.special_defense,
            "spe": self.speed,
        }


@dataclass
class PokemonData:
    """ポケモンデータ"""
    name: str                   # 英語名
    japanese_name: str          # 日本語名
    types: List[str]            # タイプ
    base_stats: BaseStats       # 種族値
    abilities: List[str]        # 特性
    common_items: List[str] = None     # よく持つ道具
    common_moves: List[str] = None     # よく使う技
    
    def __post_init__(self):
        if self.common_items is None:
            self.common_items = []
        if self.common_moves is None:
            self.common_moves = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "japanese_name": self.japanese_name,
            "types": self.types,
            "base_stats": self.base_stats.to_dict(),
            "abilities": self.abilities,
        }


# VGCでよく使われるポケモンのデータベース
POKEMON_DATABASE: Dict[str, PokemonData] = {
    # --- 禁止伝説 ---
    "calyrexshadow": PokemonData(
        name="calyrexshadow", japanese_name="バドレックス(黒馬)",
        types=["Psychic", "Ghost"],
        base_stats=BaseStats(100, 85, 80, 165, 100, 150),
        abilities=["asone"],
        common_items=["focussash", "choicespecs", "lifeorb"],
        common_moves=["astralbarrage", "psychic", "nastyplot", "protect"]
    ),
    "calyrexice": PokemonData(
        name="calyrexice", japanese_name="バドレックス(白馬)",
        types=["Psychic", "Ice"],
        base_stats=BaseStats(100, 165, 150, 85, 130, 50),
        abilities=["asone"],
        common_items=["clearamulet", "assaultvest", "lifeorb"],
        common_moves=["glaciallance", "highhorsepower", "closecombat", "protect"]
    ),
    "miraidon": PokemonData(
        name="miraidon", japanese_name="ミライドン",
        types=["Electric", "Dragon"],
        base_stats=BaseStats(100, 85, 100, 135, 115, 135),
        abilities=["hadronengine"],
        common_items=["lifeorb", "boosterenergy", "choicespecs"],
        common_moves=["electrobeam", "dracometeor", "voltswitch", "protect"]
    ),
    "koraidon": PokemonData(
        name="koraidon", japanese_name="コライドン",
        types=["Fighting", "Dragon"],
        base_stats=BaseStats(100, 135, 115, 85, 100, 135),
        abilities=["orichalcumpulse"],
        common_items=["clearamulet", "lifeorb", "choiceband"],
        common_moves=["collisioncourse", "flareblitz", "uturn", "protect"]
    ),
    
    # --- テラパゴス ---
    "terapagos": PokemonData(
        name="terapagos", japanese_name="テラパゴス",
        types=["Normal"],  # Terastal form is Stellar
        base_stats=BaseStats(160, 105, 110, 130, 110, 85),
        abilities=["terashift", "terashell"],
        common_items=["leftovers", "sitrusberry"],
        common_moves=["teracluster", "earthpower", "calmmind", "protect"]
    ),
    
    # --- 準伝説・一般 VGC常連 ---
    "urshifurapidstrike": PokemonData(
        name="urshifurapidstrike", japanese_name="ウーラオス(れんげき)",
        types=["Fighting", "Water"],
        base_stats=BaseStats(100, 130, 100, 63, 60, 97),
        abilities=["unseenfist"],
        common_items=["focussash", "choiceband", "mysticwater"],
        common_moves=["surgingstrikes", "closecombat", "aquajet", "protect"]
    ),
    "urshifusinglestrike": PokemonData(
        name="urshifusinglestrike", japanese_name="ウーラオス(いちげき)",
        types=["Fighting", "Dark"],
        base_stats=BaseStats(100, 130, 100, 63, 60, 97),
        abilities=["unseenfist"],
        common_items=["focussash", "choiceband", "blackglasses"],
        common_moves=["wickedblow", "closecombat", "suckerpunch", "protect"]
    ),
    "incineroar": PokemonData(
        name="incineroar", japanese_name="ガオガエン",
        types=["Fire", "Dark"],
        base_stats=BaseStats(95, 115, 90, 80, 90, 60),
        abilities=["intimidate", "blaze"],
        common_items=["sitrusberry", "safetygoggles", "assaultvest"],
        common_moves=["fakeout", "flareblitz", "knockoff", "partingshot"]
    ),
    "rillaboom": PokemonData(
        name="rillaboom", japanese_name="ゴリランダー",
        types=["Grass"],
        base_stats=BaseStats(100, 125, 90, 60, 70, 85),
        abilities=["grassysurge", "overgrow"],
        common_items=["miracleseed", "assaultvest", "choiceband"],
        common_moves=["grassyglide", "woodhammer", "uturn", "fakeout"]
    ),
    "amoonguss": PokemonData(
        name="amoonguss", japanese_name="モロバレル",
        types=["Grass", "Poison"],
        base_stats=BaseStats(114, 85, 70, 85, 80, 30),
        abilities=["regenerator", "effectspore"],
        common_items=["sitrusberry", "rockyhelmet", "covertcloak"],
        common_moves=["spore", "ragepowder", "pollenpuff", "protect"]
    ),
    "flutter_mane": PokemonData(
        name="fluttermane", japanese_name="ハバタクカミ",
        types=["Ghost", "Fairy"],
        base_stats=BaseStats(55, 55, 55, 135, 135, 135),
        abilities=["protosynthesis"],
        common_items=["boosterenergy", "choicespecs", "focussash"],
        common_moves=["moonblast", "shadowball", "dazzlinggleam", "protect"]
    ),
    "iron_hands": PokemonData(
        name="ironhands", japanese_name="テツノカイナ",
        types=["Fighting", "Electric"],
        base_stats=BaseStats(154, 140, 108, 50, 68, 50),
        abilities=["quarkdrive"],
        common_items=["assaultvest", "boosterenergy", "sitrusberry"],
        common_moves=["drainpunch", "wildcharge", "fakeout", "protect"]
    ),
    "landorus": PokemonData(
        name="landorus", japanese_name="ランドロス(霊獣)",
        types=["Ground", "Flying"],
        base_stats=BaseStats(89, 145, 90, 105, 80, 91),
        abilities=["intimidate", "sheerforce"],
        common_items=["choicescarf", "assaultvest", "lifeorb"],
        common_moves=["earthquake", "uturn", "rockslide", "protect"]
    ),
    "ogerpon_wellspring": PokemonData(
        name="ogerponwellspring", japanese_name="オーガポン(いど)",
        types=["Grass", "Water"],
        base_stats=BaseStats(80, 120, 84, 60, 96, 110),
        abilities=["waterabsorb"],
        common_items=["wellspringmask"],  # 固有アイテム
        common_moves=["ivycudgel", "woodhammer", "hornleech", "protect"]
    ),
    "ogerpon_hearthflame": PokemonData(
        name="ogerponhearthflame", japanese_name="オーガポン(かまど)",
        types=["Grass", "Fire"],
        base_stats=BaseStats(80, 120, 84, 60, 96, 110),
        abilities=["moldbreaker"],
        common_items=["hearthflamemask"],
        common_moves=["ivycudgel", "woodhammer", "hornleech", "protect"]
    ),
    "regieleki": PokemonData(
        name="regieleki", japanese_name="レジエレキ",
        types=["Electric"],
        base_stats=BaseStats(80, 100, 50, 100, 50, 200),
        abilities=["transistor"],
        common_items=["focussash", "lifeorb", "lightclay"],
        common_moves=["thunderbolt", "voltswitch", "electroweb", "protect"]
    ),
    "indeedee_f": PokemonData(
        name="indeedeef", japanese_name="イエッサン♀",
        types=["Psychic", "Normal"],
        base_stats=BaseStats(70, 55, 65, 95, 105, 85),
        abilities=["psychicsurge", "synchronize"],
        common_items=["focussash", "psychicseed"],
        common_moves=["followme", "helpinghand", "psychic", "protect"]
    ),
    "whimsicott": PokemonData(
        name="whimsicott", japanese_name="エルフーン",
        types=["Grass", "Fairy"],
        base_stats=BaseStats(60, 67, 85, 77, 75, 116),
        abilities=["prankster", "infiltrator"],
        common_items=["focussash", "covertcloak"],
        common_moves=["tailwind", "encore", "moonblast", "protect"]
    ),
}


class BaseStatsDB:
    """種族値データベースサービス"""
    
    @classmethod
    def get_pokemon_data(cls, pokemon_name: str) -> Optional[PokemonData]:
        """ポケモン名からデータを取得"""
        if not pokemon_name:
            return None
        key = pokemon_name.lower().replace(" ", "").replace("-", "").replace("_", "")
        
        # 直接マッチ
        if key in POKEMON_DATABASE:
            return POKEMON_DATABASE[key]
        
        # 部分マッチ
        for db_key, data in POKEMON_DATABASE.items():
            if key in db_key or db_key in key:
                return data
            if key in data.japanese_name.lower():
                return data
        
        return None
    
    @classmethod
    def get_base_stats(cls, pokemon_name: str) -> Optional[BaseStats]:
        """種族値を取得"""
        data = cls.get_pokemon_data(pokemon_name)
        return data.base_stats if data else None
    
    @classmethod
    def get_base_speed(cls, pokemon_name: str) -> int:
        """素早さ種族値を取得"""
        data = cls.get_pokemon_data(pokemon_name)
        return data.base_stats.speed if data else 80  # デフォルト
    
    @classmethod
    def get_types(cls, pokemon_name: str) -> List[str]:
        """タイプを取得"""
        data = cls.get_pokemon_data(pokemon_name)
        return data.types if data else ["Normal"]
    
    @classmethod
    def get_abilities(cls, pokemon_name: str) -> List[str]:
        """特性リストを取得"""
        data = cls.get_pokemon_data(pokemon_name)
        return data.abilities if data else []


# Singleton
_base_stats_db = None

def get_base_stats_db() -> BaseStatsDB:
    global _base_stats_db
    if _base_stats_db is None:
        _base_stats_db = BaseStatsDB()
    return _base_stats_db
