"""
StatParticleFilter - EV/実数値のオンライン推定

OTS（テラ/持ち物/技は確定）前提で、相手のEV/実数値を粒子フィルターで推定する。

観測可能な情報:
1. 行動順（S比較）
2. 受けたダメージ量（A/D/Cライン）
3. 回復量（残飯/再生力の発動量でHP実数が絞れる）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import random
import math


@dataclass
class StatParticle:
    """1体のポケモンの実数値仮説（粒子）"""
    
    hp: int
    atk: int
    def_: int  # defは予約語
    spa: int
    spd: int
    spe: int
    weight: float = 1.0  # 尤度重み
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "hp": self.hp,
            "atk": self.atk,
            "def": self.def_,
            "spa": self.spa,
            "spd": self.spd,
            "spe": self.spe,
        }
    
    def copy(self) -> 'StatParticle':
        return StatParticle(
            hp=self.hp, atk=self.atk, def_=self.def_,
            spa=self.spa, spd=self.spd, spe=self.spe,
            weight=self.weight
        )


@dataclass 
class PokemonStatBelief:
    """1体のポケモンの実数値確率分布（粒子集合）"""
    
    species: str
    level: int = 50
    particles: List[StatParticle] = field(default_factory=list)
    n_particles: int = 30  # 粒子数
    
    # 確定情報（OTS前提）
    known_nature: Optional[str] = None
    known_item: Optional[str] = None
    known_ability: Optional[str] = None
    
    # 観測履歴
    speed_observations: List[Tuple[str, str, bool]] = field(default_factory=list)  # (my_pokemon, opponent, was_faster)
    damage_observations: List[Dict] = field(default_factory=list)  # {attacker, defender, move, damage_dealt, damage_ratio}
    
    def initialize_from_base_stats(self, base_stats: Dict[str, int]):
        """種族値からランダムな粒子を初期化"""
        self.particles = []
        
        for _ in range(self.n_particles):
            # ランダムな努力値配分（合計510以下）
            evs = self._random_evs()
            
            # ランダムな性格補正
            nature_mod = self._random_nature_modifiers()
            
            # 実数値を計算
            stats = self._calc_stats(base_stats, evs, nature_mod)
            
            self.particles.append(StatParticle(
                hp=stats["hp"],
                atk=stats["atk"],
                def_=stats["def"],
                spa=stats["spa"],
                spd=stats["spd"],
                spe=stats["spe"],
                weight=1.0 / self.n_particles
            ))
    
    def _random_evs(self) -> Dict[str, int]:
        """ランダムな努力値配分を生成"""
        stats = ["hp", "atk", "def", "spa", "spd", "spe"]
        evs = {s: 0 for s in stats}
        remaining = 510
        
        # ランダムに振り分け（4の倍数で）
        while remaining > 0:
            stat = random.choice(stats)
            add = min(random.choice([0, 4, 8, 12, 16, 20, 252 - evs[stat]]), remaining)
            if evs[stat] + add <= 252:
                evs[stat] += add
                remaining -= add
            if all(evs[s] >= 252 for s in stats):
                break
        
        return evs
    
    def _random_nature_modifiers(self) -> Dict[str, float]:
        """ランダムな性格補正を生成"""
        stats = ["atk", "def", "spa", "spd", "spe"]
        mods = {s: 1.0 for s in stats}
        mods["hp"] = 1.0  # HPは補正なし
        
        # 50%の確率で補正あり性格
        if random.random() > 0.3:
            up = random.choice(stats)
            down = random.choice([s for s in stats if s != up])
            mods[up] = 1.1
            mods[down] = 0.9
        
        return mods
    
    def _calc_stats(self, base: Dict[str, int], evs: Dict[str, int], nature: Dict[str, float]) -> Dict[str, int]:
        """実数値を計算"""
        stats = {}
        
        # HP計算
        base_hp = base.get("hp", 100)
        ev_hp = evs.get("hp", 0)
        stats["hp"] = ((base_hp * 2 + 31 + ev_hp // 4) * self.level // 100) + self.level + 10
        
        # 他のステータス
        for stat in ["atk", "def", "spa", "spd", "spe"]:
            base_stat = base.get(stat, 100)
            ev_stat = evs.get(stat, 0)
            nat_mod = nature.get(stat, 1.0)
            stats[stat] = int((((base_stat * 2 + 31 + ev_stat // 4) * self.level // 100) + 5) * nat_mod)
        
        return stats
    
    def update_with_speed_observation(self, my_speed: int, was_faster: bool, trick_room: bool = False):
        """
        行動順の観測で更新
        
        Args:
            my_speed: 自分のポケモンの素早さ
            was_faster: 相手が先に動いたか
            trick_room: トリックルーム中か
        """
        for particle in self.particles:
            opp_speed = particle.spe
            
            if trick_room:
                # トリックルーム中は遅い方が先
                expected_faster = opp_speed < my_speed
            else:
                expected_faster = opp_speed > my_speed
            
            # 観測と一致するか
            if expected_faster == was_faster:
                particle.weight *= 1.5  # 尤度UP
            else:
                particle.weight *= 0.3  # 尤度DOWN
        
        self._normalize_weights()
        self._resample_if_needed()
    
    def update_with_damage_observation(
        self,
        damage_dealt: int,
        attacker_stats: Dict[str, int],
        move_power: int,
        move_category: str,  # "physical" or "special"
        type_effectiveness: float = 1.0,
        is_stab: bool = False,
    ):
        """
        受けたダメージ量の観測で更新（防御側の耐久推定）
        
        Args:
            damage_dealt: 実際に与えたダメージ
            attacker_stats: 攻撃側の実数値（自分が攻撃した場合）
            move_power: 技の威力
            move_category: 物理/特殊
            type_effectiveness: タイプ相性倍率
            is_stab: タイプ一致か
        """
        for particle in self.particles:
            # ダメージ計算（簡易版）
            if move_category == "physical":
                atk = attacker_stats.get("atk", 100)
                def_ = particle.def_
            else:
                atk = attacker_stats.get("spa", 100)
                def_ = particle.spd
            
            stab = 1.5 if is_stab else 1.0
            
            # ダメージ期待値
            expected_damage = ((22 * move_power * atk / def_) / 50 + 2) * stab * type_effectiveness
            
            # 乱数幅（0.85〜1.0）を考慮
            min_damage = expected_damage * 0.85
            max_damage = expected_damage * 1.0
            
            # 観測されたダメージが範囲内か
            if min_damage <= damage_dealt <= max_damage:
                particle.weight *= 1.3
            elif damage_dealt < min_damage:
                # 予想より低ダメ → 耐久が高い
                particle.weight *= 0.5
            else:
                # 予想より高ダメ → 耐久が低い
                particle.weight *= 0.5
        
        self._normalize_weights()
        self._resample_if_needed()
    
    def _normalize_weights(self):
        """重みを正規化"""
        total = sum(p.weight for p in self.particles)
        if total > 0:
            for p in self.particles:
                p.weight /= total
    
    def _resample_if_needed(self, threshold: float = 0.5):
        """有効サンプルサイズが閾値を下回ったらリサンプル"""
        ess = 1.0 / sum(p.weight ** 2 for p in self.particles)
        
        if ess < self.n_particles * threshold:
            self._resample()
    
    def _resample(self):
        """重み付きリサンプリング"""
        weights = [p.weight for p in self.particles]
        new_particles = random.choices(self.particles, weights=weights, k=self.n_particles)
        
        # 重みをリセット
        self.particles = []
        for p in new_particles:
            new_p = p.copy()
            new_p.weight = 1.0 / self.n_particles
            self.particles.append(new_p)
    
    def get_stat_estimate(self, stat: str) -> Tuple[float, float, float]:
        """
        ステータスの推定値を取得
        
        Returns:
            (mean, lower_10%, upper_90%)
        """
        values = []
        weights = []
        
        for p in self.particles:
            if stat == "hp":
                values.append(p.hp)
            elif stat == "atk":
                values.append(p.atk)
            elif stat == "def":
                values.append(p.def_)
            elif stat == "spa":
                values.append(p.spa)
            elif stat == "spd":
                values.append(p.spd)
            elif stat == "spe":
                values.append(p.spe)
            weights.append(p.weight)
        
        # 重み付き平均
        mean = sum(v * w for v, w in zip(values, weights))
        
        # ソートして分位点
        sorted_pairs = sorted(zip(values, weights), key=lambda x: x[0])
        cumsum = 0
        lower = sorted_pairs[0][0]
        upper = sorted_pairs[-1][0]
        
        for v, w in sorted_pairs:
            cumsum += w
            if cumsum >= 0.1 and lower == sorted_pairs[0][0]:
                lower = v
            if cumsum >= 0.9:
                upper = v
                break
        
        return mean, lower, upper
    
    def get_speed_range(self) -> Tuple[int, int]:
        """素早さの推定範囲（下振れ〜上振れ）"""
        _, lower, upper = self.get_stat_estimate("spe")
        return int(lower), int(upper)
    
    def get_bulk_estimate(self) -> Dict[str, Tuple[float, float, float]]:
        """耐久ライン（HP, B, D）の推定"""
        return {
            "hp": self.get_stat_estimate("hp"),
            "def": self.get_stat_estimate("def"),
            "spd": self.get_stat_estimate("spd"),
        }


class StatParticleFilter:
    """
    全相手ポケモンの実数値粒子フィルター
    
    使用例:
    ```python
    filter = StatParticleFilter()
    
    # 初期化（種族値から）
    filter.initialize_pokemon("Garchomp", BASE_STATS["Garchomp"])
    
    # 行動順観測
    filter.observe_speed("Garchomp", my_speed=150, was_faster=True)
    
    # ダメージ観測
    filter.observe_damage("Garchomp", damage=120, ...)
    
    # 推定値取得
    speed_range = filter.get_speed_range("Garchomp")
    ```
    """
    
    def __init__(self, n_particles: int = 30):
        self.n_particles = n_particles
        self.beliefs: Dict[str, PokemonStatBelief] = {}
    
    def initialize_pokemon(self, species: str, base_stats: Dict[str, int]):
        """ポケモンの粒子を初期化"""
        belief = PokemonStatBelief(
            species=species,
            n_particles=self.n_particles
        )
        belief.initialize_from_base_stats(base_stats)
        self.beliefs[species] = belief
    
    def observe_speed(self, species: str, my_speed: int, was_faster: bool, trick_room: bool = False):
        """行動順を観測"""
        if species in self.beliefs:
            self.beliefs[species].update_with_speed_observation(my_speed, was_faster, trick_room)
    
    def observe_damage(
        self,
        species: str,
        damage_dealt: int,
        attacker_stats: Dict[str, int],
        move_power: int,
        move_category: str,
        type_effectiveness: float = 1.0,
        is_stab: bool = False,
    ):
        """ダメージを観測"""
        if species in self.beliefs:
            self.beliefs[species].update_with_damage_observation(
                damage_dealt, attacker_stats, move_power, move_category,
                type_effectiveness, is_stab
            )
    
    def get_speed_range(self, species: str) -> Tuple[int, int]:
        """素早さの推定範囲を取得"""
        if species in self.beliefs:
            return self.beliefs[species].get_speed_range()
        return (0, 999)  # 不明
    
    def get_stat_estimate(self, species: str, stat: str) -> Tuple[float, float, float]:
        """ステータスの推定値を取得"""
        if species in self.beliefs:
            return self.beliefs[species].get_stat_estimate(stat)
        return (100.0, 50.0, 150.0)  # デフォルト
    
    def get_mean_stats(self, species: str) -> Dict[str, int]:
        """平均実数値を取得（ダメ計用）"""
        if species not in self.beliefs:
            return {"hp": 150, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}
        
        belief = self.beliefs[species]
        return {
            "hp": int(belief.get_stat_estimate("hp")[0]),
            "atk": int(belief.get_stat_estimate("atk")[0]),
            "def": int(belief.get_stat_estimate("def")[0]),
            "spa": int(belief.get_stat_estimate("spa")[0]),
            "spd": int(belief.get_stat_estimate("spd")[0]),
            "spe": int(belief.get_stat_estimate("spe")[0]),
        }
    
    def get_pessimistic_stats(self, species: str) -> Dict[str, int]:
        """悲観的実数値（下振れ10%分位点）を取得"""
        if species not in self.beliefs:
            return {"hp": 200, "atk": 150, "def": 150, "spa": 150, "spd": 150, "spe": 200}
        
        belief = self.beliefs[species]
        return {
            "hp": int(belief.get_stat_estimate("hp")[2]),  # 上振れ
            "atk": int(belief.get_stat_estimate("atk")[2]),
            "def": int(belief.get_stat_estimate("def")[2]),  # 相手の耐久は上振れを見る
            "spa": int(belief.get_stat_estimate("spa")[2]),
            "spd": int(belief.get_stat_estimate("spd")[2]),
            "spe": int(belief.get_stat_estimate("spe")[2]),
        }


# シングルトン
_stat_filter: Optional[StatParticleFilter] = None


def get_stat_particle_filter() -> StatParticleFilter:
    """StatParticleFilter のシングルトンを取得"""
    global _stat_filter
    if _stat_filter is None:
        _stat_filter = StatParticleFilter()
    return _stat_filter


def reset_stat_particle_filter():
    """StatParticleFilter をリセット（新バトル開始時）"""
    global _stat_filter
    _stat_filter = None
