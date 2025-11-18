"""
Smogon Chaos JSON Parser

Smogon統計データを読み込み、ポケモンごとの事前確率分布を提供する。

使用方法:
    from predictor.data.smogon_chaos_parser import SmogonChaosParser
    
    parser = SmogonChaosParser("data/smogon_stats/gen9vgc2024regh-1760.json")
    prior = parser.get_pokemon_prior("Gholdengo")
    print(prior.spreads)  # EV配分の確率分布
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class PokemonPrior:
    """ポケモンの事前確率分布"""
    
    name: str
    usage_rate: float
    
    # 努力値配分: {配分文字列: 確率}
    spreads: Dict[str, float]
    
    # 特性: {特性名: 確率}
    abilities: Dict[str, float]
    
    # 持ち物: {アイテム名: 確率}
    items: Dict[str, float]
    
    # 技: {技名: 確率}
    moves: Dict[str, float]
    
    # テラスタイプ: {タイプ名: 確率}
    tera_types: Dict[str, float]
    
    # 性格: {性格名: 確率} (spreadから抽出)
    natures: Dict[str, float]
    
    def get_top_spreads(self, n: int = 5) -> List[Tuple[str, float]]:
        """使用率上位N件のEV配分を取得"""
        return sorted(self.spreads.items(), key=lambda x: x[1], reverse=True)[:n]
    
    def get_top_items(self, n: int = 5) -> List[Tuple[str, float]]:
        """使用率上位N件の持ち物を取得"""
        return sorted(self.items.items(), key=lambda x: x[1], reverse=True)[:n]
    
    def parse_spread(self, spread_str: str) -> Dict[str, int]:
        """
        EV配分文字列をパース
        
        例: "Jolly:252/0/0/0/4/252" -> {"nature": "Jolly", "hp": 252, "atk": 252, ...}
        """
        parts = spread_str.split(":")
        if len(parts) != 2:
            return {}
        
        nature, evs = parts
        ev_values = evs.split("/")
        
        if len(ev_values) != 6:
            return {}
        
        return {
            "nature": nature,
            "hp": int(ev_values[0]),
            "atk": int(ev_values[1]),
            "def": int(ev_values[2]),
            "spa": int(ev_values[3]),
            "spd": int(ev_values[4]),
            "spe": int(ev_values[5]),
        }


class SmogonChaosParser:
    """Smogon Chaos JSONを読み込み、事前確率を提供するクラス"""
    
    def __init__(self, json_path: str | Path):
        """
        Args:
            json_path: Chaos JSONファイルのパス
        """
        self.json_path = Path(json_path)
        
        with open(self.json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        
        self.pokemon_data = self.data.get("data", {})
        self.info = self.data.get("info", {})
        
        print(f"✅ Smogon Chaos JSON loaded")
        print(f"   Metagame: {self.info.get('metagame', 'unknown')}")
        print(f"   Cutoff: {self.info.get('cutoff', 0)}")
        print(f"   Total Pokemon: {len(self.pokemon_data)}")
    
    def get_pokemon_prior(self, pokemon_name: str) -> PokemonPrior | None:
        """
        指定ポケモンの事前確率分布を取得
        
        Args:
            pokemon_name: ポケモン名（英語）
        
        Returns:
            PokemonPrior または None（存在しない場合）
        """
        stats = self.pokemon_data.get(pokemon_name)
        if not stats:
            return None
        
        # 性格の抽出（スプレッドから）
        natures = {}
        spreads = stats.get("Spreads", {})
        for spread_str in spreads.keys():
            nature = spread_str.split(":")[0]
            if nature:
                natures[nature] = natures.get(nature, 0) + spreads[spread_str]
        
        return PokemonPrior(
            name=pokemon_name,
            usage_rate=stats.get("usage", 0.0),
            spreads=stats.get("Spreads", {}),
            abilities=stats.get("Abilities", {}),
            items=stats.get("Items", {}),
            moves=stats.get("Moves", {}),
            tera_types=stats.get("Tera Types", {}),
            natures=natures,
        )
    
    def get_top_pokemon(self, n: int = 10) -> List[Tuple[str, float]]:
        """使用率上位N件のポケモンを取得"""
        sorted_pokemon = sorted(
            self.pokemon_data.items(),
            key=lambda x: x[1].get("usage", 0),
            reverse=True
        )
        return [(name, stats["usage"]) for name, stats in sorted_pokemon[:n]]
    
    def list_available_pokemon(self) -> List[str]:
        """利用可能な全ポケモン名のリストを取得"""
        return list(self.pokemon_data.keys())


def main():
    """動作確認用"""
    import sys
    
    # データファイルのパス
    data_path = Path(__file__).parent.parent.parent / "data/smogon_stats/gen9vgc2024regh-1760.json"
    
    if not data_path.exists():
        print(f"❌ データファイルが見つかりません: {data_path}")
        sys.exit(1)
    
    # パーサー初期化
    parser = SmogonChaosParser(data_path)
    
    print()
    print("=" * 70)
    print("📊 使用率 Top 10")
    print("=" * 70)
    top10 = parser.get_top_pokemon(10)
    for i, (name, usage) in enumerate(top10, 1):
        print(f"{i:2d}. {name:25s} {usage:6.2%}")
    
    print()
    print("=" * 70)
    print("🔍 Gholdengo の詳細分析")
    print("=" * 70)
    
    # Gholdengoの事前確率を取得
    gholdengo_prior = parser.get_pokemon_prior("Gholdengo")
    
    if gholdengo_prior:
        print()
        print(f"使用率: {gholdengo_prior.usage_rate:.2%}")
        print()
        
        print("📊 努力値配分 Top 5:")
        for i, (spread, prob) in enumerate(gholdengo_prior.get_top_spreads(5), 1):
            parsed = gholdengo_prior.parse_spread(spread)
            nature = parsed.get("nature", "???")
            evs = f"H{parsed.get('hp', 0)} A{parsed.get('atk', 0)} B{parsed.get('def', 0)} C{parsed.get('spa', 0)} D{parsed.get('spd', 0)} S{parsed.get('spe', 0)}"
            print(f"  {i}. {nature:12s} {evs:30s} ({prob:.2%})")
        
        print()
        print("✨ 特性:")
        for ability, prob in sorted(gholdengo_prior.abilities.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {ability:20s} {prob:.2%}")
        
        print()
        print("🎒 持ち物 Top 5:")
        for i, (item, prob) in enumerate(gholdengo_prior.get_top_items(5), 1):
            print(f"  {i}. {item:25s} {prob:.2%}")
        
        print()
        print("⚔️ 技 Top 8:")
        sorted_moves = sorted(gholdengo_prior.moves.items(), key=lambda x: x[1], reverse=True)[:8]
        for i, (move, prob) in enumerate(sorted_moves, 1):
            print(f"  {i}. {move:25s} {prob:.2%}")
        
        print()
        print("💎 性格分布:")
        sorted_natures = sorted(gholdengo_prior.natures.items(), key=lambda x: x[1], reverse=True)[:5]
        for nature, prob in sorted_natures:
            print(f"  - {nature:12s} {prob:.2%}")
    
    print()
    print("=" * 70)
    print("✅ Parser 動作確認完了")
    print("=" * 70)


if __name__ == "__main__":
    main()
