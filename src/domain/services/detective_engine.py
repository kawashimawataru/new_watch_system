"""
Detective Engine: EV推定エンジン

バトルログから観測される情報（速度、ダメージ）を元に、
ベイズ推定によって相手ポケモンのEV配分を推定する。

使用方法:
    from predictor.core.detective_engine import DetectiveEngine
    
    engine = DetectiveEngine("data/smogon_stats/gen9vgc2024regh-1760.json")
    
    # 事前確率をロード
    engine.load_prior("Gholdengo")
    
    # 速度判定で更新
    engine.update_from_speed_comparison("Dragonite", went_first=False)
    
    # 最も確率の高いEV配分を取得
    best_spread = engine.get_most_likely_spread()
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import copy

from predictor.data.smogon_chaos_parser import SmogonChaosParser, PokemonPrior
from predictor.data.showdown_loader import ShowdownDataRepository


@dataclass
class SpreadHypothesis:
    """EV配分の仮説"""
    
    spread_str: str  # 例: "Modest:4/0/0/252/0/252"
    nature: str
    evs: Dict[str, int]  # {"hp": 4, "atk": 0, ...}
    probability: float
    
    def calculate_stat(self, base_stat: int, stat_name: str, level: int = 50) -> int:
        """
        実数値を計算
        
        Args:
            base_stat: 種族値
            stat_name: "hp", "atk", "def", "spa", "spd", "spe"
            level: レベル（VGCは50固定）
        
        Returns:
            実数値
        """
        ev = self.evs.get(stat_name, 0)
        iv = 31  # 個体値は最大と仮定
        
        # 性格補正
        nature_modifiers = {
            # 攻撃↑
            "Lonely": {"atk": 1.1, "def": 0.9},
            "Brave": {"atk": 1.1, "spe": 0.9},
            "Adamant": {"atk": 1.1, "spa": 0.9},
            "Naughty": {"atk": 1.1, "spd": 0.9},
            # 防御↑
            "Bold": {"def": 1.1, "atk": 0.9},
            "Relaxed": {"def": 1.1, "spe": 0.9},
            "Impish": {"def": 1.1, "spa": 0.9},
            "Lax": {"def": 1.1, "spd": 0.9},
            # 特攻↑
            "Modest": {"spa": 1.1, "spe": 0.9},
            "Mild": {"spa": 1.1, "def": 0.9},
            "Quiet": {"spa": 1.1, "spe": 0.9},
            "Rash": {"spa": 1.1, "spd": 0.9},
            # 特防↑
            "Calm": {"spd": 1.1, "atk": 0.9},
            "Gentle": {"spd": 1.1, "def": 0.9},
            "Sassy": {"spd": 1.1, "spe": 0.9},
            "Careful": {"spd": 1.1, "spa": 0.9},
            # 素早さ↑
            "Timid": {"spe": 1.1, "atk": 0.9},
            "Hasty": {"spe": 1.1, "def": 0.9},
            "Jolly": {"spe": 1.1, "spa": 0.9},
            "Naive": {"spe": 1.1, "spd": 0.9},
        }
        
        modifier = nature_modifiers.get(self.nature, {}).get(stat_name, 1.0)
        
        if stat_name == "hp":
            # HP計算式
            return int((2 * base_stat + iv + ev // 4) * level // 100) + level + 10
        else:
            # その他のステータス
            return int(((2 * base_stat + iv + ev // 4) * level // 100) + 5) * modifier


class DetectiveEngine:
    """EV推定エンジン（名探偵）"""
    
    def __init__(self, chaos_json_path: str | Path):
        """
        Args:
            chaos_json_path: Smogon Chaos JSONファイルのパス
        """
        self.parser = SmogonChaosParser(chaos_json_path)
        self.showdown_data = ShowdownDataRepository()
        
        # 現在推定中のポケモン
        self.target_pokemon: Optional[str] = None
        self.hypotheses: List[SpreadHypothesis] = []
    
    def load_prior(self, pokemon_name: str) -> bool:
        """
        ポケモンの事前確率分布をロード
        
        Args:
            pokemon_name: ポケモン名（英語）
        
        Returns:
            成功した場合True
        """
        prior = self.parser.get_pokemon_prior(pokemon_name)
        
        if not prior:
            print(f"❌ {pokemon_name} のデータが見つかりません")
            return False
        
        self.target_pokemon = pokemon_name
        self.hypotheses = []
        
        # 各EV配分を仮説として登録
        total_weight = sum(prior.spreads.values())
        
        for spread_str, weight in prior.spreads.items():
            parsed = prior.parse_spread(spread_str)
            if not parsed:
                continue
            
            # 確率を正規化
            probability = weight / total_weight if total_weight > 0 else 0
            
            hypothesis = SpreadHypothesis(
                spread_str=spread_str,
                nature=parsed["nature"],
                evs={
                    "hp": parsed["hp"],
                    "atk": parsed["atk"],
                    "def": parsed["def"],
                    "spa": parsed["spa"],
                    "spd": parsed["spd"],
                    "spe": parsed["spe"],
                },
                probability=probability,
            )
            
            self.hypotheses.append(hypothesis)
        
        print(f"✅ {pokemon_name} の事前分布をロード: {len(self.hypotheses)}個の仮説")
        return True
    
    def update_from_speed_comparison(
        self,
        opponent_pokemon: str,
        opponent_went_first: bool,
        *,
        opponent_speed_ev: Optional[int] = None,
        opponent_nature: Optional[str] = None,
    ) -> None:
        """
        速度判定によってEV分布を更新
        
        Args:
            opponent_pokemon: 比較相手のポケモン名
            opponent_went_first: 相手が先に動いたか
            opponent_speed_ev: 相手の素早さEV（分かっている場合）
            opponent_nature: 相手の性格（分かっている場合）
        """
        if not self.target_pokemon:
            print("❌ 推定対象のポケモンが設定されていません")
            return
        
        # 相手のポケモンデータを取得
        opponent_species = self.showdown_data.get_species(opponent_pokemon)
        opponent_base_speed = opponent_species.base_stats.get("spe", 100)
        
        # 相手の素早さ実数値を推定（分からない場合は最速を仮定）
        if opponent_speed_ev is None:
            opponent_speed_ev = 252
        if opponent_nature is None:
            opponent_nature = "Jolly"  # 最速性格を仮定
        
        # 相手の素早さ実数値を計算
        opponent_speed = self._calculate_speed(
            opponent_base_speed,
            opponent_speed_ev,
            opponent_nature
        )
        
        # 自分の種族値を取得
        target_species = self.showdown_data.get_species(self.target_pokemon)
        target_base_speed = target_species.base_stats.get("spe", 100)
        
        # ベイズ更新
        
        # ベイズ更新
        print(f"🔍 速度判定: {self.target_pokemon} vs {opponent_pokemon}")
        print(f"   相手が{'先' if opponent_went_first else '後'}に動きました")
        print(f"   相手の素早さ実数値: {opponent_speed} (推定)")
        
        for hyp in self.hypotheses:
            my_speed = hyp.calculate_stat(target_base_speed, "spe")
            
            # 尤度を計算
            if opponent_went_first:
                # 相手が先 → 自分の素早さが相手より遅い必要がある
                likelihood = 1.0 if my_speed < opponent_speed else 0.1  # 誤差を考慮
            else:
                # 自分が先 → 自分の素早さが相手より速い必要がある
                likelihood = 1.0 if my_speed >= opponent_speed else 0.1
            
            # 事後確率 ∝ 事前確率 × 尤度
            hyp.probability *= likelihood
        
        # 正規化
        self._normalize_probabilities()
        
        print(f"✅ 更新完了: 上位5件の仮説")
        for i, hyp in enumerate(self.get_top_hypotheses(5), 1):
            speed = hyp.calculate_stat(target_base_speed, "spe")
            print(f"   {i}. {hyp.nature} S{hyp.evs['spe']} (実数値{speed}) → {hyp.probability:.2%}")
    
    def _calculate_speed(self, base: int, ev: int, nature: str, iv: int = 31, level: int = 50) -> int:
        """素早さ実数値を計算"""
        modifier = 1.1 if nature in ["Timid", "Hasty", "Jolly", "Naive"] else 1.0
        return int(((2 * base + iv + ev // 4) * level // 100 + 5) * modifier)
    
    def _normalize_probabilities(self) -> None:
        """確率を正規化（合計が1になるように）"""
        total = sum(h.probability for h in self.hypotheses)
        if total > 0:
            for h in self.hypotheses:
                h.probability /= total
    
    def update_from_damage_observation(
        self,
        attacker_pokemon: str,
        attacker_spread: SpreadHypothesis,
        move_name: str,
        observed_damage_percent: float,
        attacker_item: Optional[str] = None,
        attacker_ability: Optional[str] = None,
        defender_item: Optional[str] = None,
        defender_ability: Optional[str] = None,
        field: Optional[Dict] = None,
        tolerance: float = 5.0
    ) -> None:
        """
        観測されたダメージからEV分布を推定（ベイズ更新）
        
        Args:
            attacker_pokemon: 攻撃側のポケモン名
            attacker_spread: 攻撃側のEV配分
            move_name: 使用した技
            observed_damage_percent: 観測されたダメージ% (例: 55.0)
            attacker_item: 攻撃側の持ち物
            attacker_ability: 攻撃側の特性
            defender_item: 防御側の持ち物
            defender_ability: 防御側の特性
            field: 場の状態
            tolerance: 誤差許容範囲% (デフォルト: 5%)
        """
        if not self.target_pokemon:
            print("❌ 推定対象のポケモンが設定されていません")
            return
        
        print(f"\n🔍 ダメージ判定: {attacker_pokemon} → {self.target_pokemon}")
        print(f"   技: {move_name}")
        print(f"   観測ダメージ: {observed_damage_percent:.1f}%")
        
        # @smogon/calc を使用
        from predictor.engine.smogon_calc_wrapper import SmogonCalcWrapper
        
        with SmogonCalcWrapper() as calc:
            updated_count = 0
            
            for hyp in self.hypotheses:
                if hyp.probability <= 0.0001:  # 確率が極小の仮説はスキップ
                    continue
                
                # この仮説でダメージ計算
                result = calc.calculate_damage(
                    attacker_name=attacker_pokemon,
                    attacker_spread=attacker_spread,
                    defender_name=self.target_pokemon,
                    defender_spread=hyp,
                    move_name=move_name,
                    attacker_item=attacker_item,
                    defender_item=defender_item,
                    attacker_ability=attacker_ability,
                    defender_ability=defender_ability,
                    field=field
                )
                
                if not result.success:
                    continue
                
                # 観測値との一致度を計算（尤度）
                # ダメージ範囲内なら高い確率、範囲外なら距離に応じて減衰
                min_dmg = result.min_percent
                max_dmg = result.max_percent
                
                if min_dmg <= observed_damage_percent <= max_dmg:
                    # 完全一致
                    likelihood = 1.0
                elif observed_damage_percent < min_dmg:
                    # 観測値が予測より低い
                    diff = min_dmg - observed_damage_percent
                    likelihood = max(0.01, 1.0 - (diff / tolerance))
                else:
                    # 観測値が予測より高い
                    diff = observed_damage_percent - max_dmg
                    likelihood = max(0.01, 1.0 - (diff / tolerance))
                
                # ベイズ更新
                hyp.probability *= likelihood
                updated_count += 1
        
        # 正規化
        self._normalize_probabilities()
        
        print(f"✅ 更新完了: {updated_count}件の仮説を更新")
        
        # 上位5件を表示
        top5 = self.get_top_hypotheses(5)
        for i, h in enumerate(top5, 1):
            print(f"   {i}. {h.nature:12s} {h.spread_str:30s} → {h.probability:.2%}")
    
    def get_top_hypotheses(self, n: int = 5) -> List[SpreadHypothesis]:
        """確率上位N件の仮説を取得"""
        return sorted(self.hypotheses, key=lambda h: h.probability, reverse=True)[:n]
    
    def get_most_likely_spread(self) -> Optional[SpreadHypothesis]:
        """最も確率の高いEV配分を取得"""
        if not self.hypotheses:
            return None
        return max(self.hypotheses, key=lambda h: h.probability)
    
    def export_distribution(self) -> Dict[str, any]:
        """現在の確率分布をエクスポート"""
        return {
            "pokemon": self.target_pokemon,
            "hypotheses": [
                {
                    "spread": h.spread_str,
                    "nature": h.nature,
                    "evs": h.evs,
                    "probability": h.probability,
                }
                for h in self.get_top_hypotheses(10)
            ]
        }


def main():
    """動作確認用デモ"""
    print("=" * 70)
    print("🕵️ Detective Engine デモ")
    print("=" * 70)
    print()
    
    # データパス
    data_path = Path(__file__).parent.parent.parent / "data/smogon_stats/gen9vgc2024regh-1760.json"
    
    # エンジン初期化
    engine = DetectiveEngine(data_path)
    
    print()
    print("-" * 70)
    print("Step 1: 事前確率のロード")
    print("-" * 70)
    
    # Gholdengoの事前分布をロード
    engine.load_prior("Gholdengo")
    
    print()
    print("事前分布 Top 5:")
    for i, hyp in enumerate(engine.get_top_hypotheses(5), 1):
        print(f"  {i}. {hyp.spread_str:40s} {hyp.probability:.2%}")
    
    print()
    print("-" * 70)
    print("Step 2: 速度判定による更新")
    print("-" * 70)
    print()
    
    # シナリオ: Gholdengo vs Dragonite で、Dragoniteが先に動いた
    # → Gholdengoは最速Dragonite（実数値189）より遅いはず
    engine.update_from_speed_comparison(
        opponent_pokemon="Dragonite",
        opponent_went_first=True,
        opponent_speed_ev=252,
        opponent_nature="Jolly"
    )
    
    print()
    print("事後分布 Top 5:")
    target_species = engine.showdown_data.get_species("Gholdengo")
    base_speed = target_species.base_stats.get("spe", 100)
    
    for i, hyp in enumerate(engine.get_top_hypotheses(5), 1):
        speed = hyp.calculate_stat(base_speed, "spe")
        print(f"  {i}. {hyp.nature:12s} S{hyp.evs['spe']:3d} (実数値{speed:.1f}) → {hyp.probability:.2%}")
    
    print()
    print("-" * 70)
    print("Step 3: ダメージ判定による更新")
    print("-" * 70)
    print()
    
    # シナリオ: Gholdengo (Specs) が Dragonite に Make It Rain を使用
    # 観測ダメージ: 55% (実際のダメージを仮定)
    
    # 攻撃側のGholdengo配分を定義（仮定: Modest C252 S252）
    from predictor.core.ev_estimator import SpreadHypothesis
    gholdengo_attacker = SpreadHypothesis(
        label="attacker",
        nature="Modest",
        evs={"hp": 4, "atk": 0, "def": 0, "spa": 252, "spd": 0, "spe": 252},
        ivs={},
        probability=1.0,
        species="Gholdengo"
    )
    
    engine.update_from_damage_observation(
        attacker_pokemon="Gholdengo",
        attacker_spread=gholdengo_attacker,
        move_name="Make It Rain",
        observed_damage_percent=55.0,  # 観測されたダメージ%
        attacker_item="Choice Specs",
        attacker_ability="Good as Gold",
        defender_ability="Multiscale"  # Dragoniteの特性
    )
    
    print()
    print("最終事後分布 Top 5:")
    for i, hyp in enumerate(engine.get_top_hypotheses(5), 1):
        print(f"  {i}. {hyp.nature:12s} {hyp.spread_str:30s} → {hyp.probability:.2%}")
    
    print()
    print("-" * 70)
    print("Step 4: 最尤推定")
    print("-" * 70)
    print()
    
    best = engine.get_most_likely_spread()
    if best:
        print(f"最も確率が高いEV配分:")
        print(f"  性格: {best.nature}")
        print(f"  EV: H{best.evs['hp']} A{best.evs['atk']} B{best.evs['def']} C{best.evs['spa']} D{best.evs['spd']} S{best.evs['spe']}")
        print(f"  確率: {best.probability:.2%}")
        
        print()
        print(f"実数値計算 (Lv50):")
        stats_names = [("HP", "hp"), ("攻撃", "atk"), ("防御", "def"), ("特攻", "spa"), ("特防", "spd"), ("素早", "spe")]
        
        for label, stat in stats_names:
            base = target_species.base_stats.get(stat, 100)
            actual = best.calculate_stat(base, stat)
            print(f"    {label}: {actual:.0f}")
    
    print()
    print("=" * 70)
    print("✅ Detective Engine デモ完了")
    print("=" * 70)


if __name__ == "__main__":
    main()
