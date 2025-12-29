"""
Turn Order Service - 行動順序予測サービス

素早さ種族値、個体値(想定)、努力値(想定)、ランク補正、
まひ、追い風、トリックルーム、特性(Swift Swim等)、アイテム(スカーフ)
などを考慮して、ターン内の行動順序を予測する。
"""

from typing import List, Tuple, Dict, Optional, Any
from poke_env.environment.pokemon import Pokemon
from poke_env.environment.double_battle import DoubleBattle

class TurnOrderService:
    """
    行動順序予測サービス
    """
    
    def get_predicted_turn_order(self, battle: DoubleBattle) -> List[Tuple[str, float]]:
        """
        現在の盤面における行動順序を予測して返す
        
        Returns:
            List[(PokemonName, EffectiveSpeed)]
            早い順(トリックルーム下では遅い順)にソート
        """
        speed_list: List[Tuple[str, float]] = []
        
        # 全アクティブポケモンを収集
        all_active = []
        # 自分 (P1)
        for i, mon in enumerate(battle.active_pokemon):
            if mon and not mon.fainted:
                all_active.append((mon, True)) # (Pokemon, is_player)
        # 相手 (P2)
        for i, mon in enumerate(battle.opponent_active_pokemon):
            if mon and not mon.fainted:
                all_active.append((mon, False))

        is_trick_room = "trickroom" in battle.fields

        for mon, is_player in all_active:
            effective_speed = self._calculate_effective_speed(mon, battle)
            # 名前 (P1/P2を区別できるように装飾しても良いが、まずは種族名)
            # 同名ポケモンがいる場合の区別はスロット等が必要だが、表示用として簡易実装
            name = mon.species # + (" (P1)" if is_player else " (P2)")
            speed_list.append((name, effective_speed, is_player))
            
        # ソート
        # トリックルーム: 遅い順 (Ascending)
        # 通常: 早い順 (Descending)
        # 優先度は技ごとに異なるため、ここでは「素早さ」のみの順序を返す
        # 実際のアクション順序は優先度(Priority)が最優先される
        
        # Pythonのsortは安定ソート。同速の場合はランダムだが、ここではリスト順維持
        speed_list.sort(key=lambda x: x[1], reverse=not is_trick_room)
        
        # 結果整形
        return [(x[0], x[1], x[2]) for x in speed_list]

    def _calculate_effective_speed(self, pokemon: Pokemon, battle: DoubleBattle) -> float:
        """
        実効素早さを計算
        """
        # 1. 基礎素早さ (Base Stats + IA/EVs)
        # 自分: pokemon.stats['spe'] (正確)
        # 相手: 推定値 (VGCならLevel 50, 31 IVs, 252 EVs, Positive Natureを一旦仮定)
        
        raw_speed = 0.0
        
        # stats辞書がある場合はそれを使う（自分、または開示情報）
        if pokemon.stats and 'spe' in pokemon.stats:
            raw_speed = float(pokemon.stats['spe'])
        else:
            # 相手のStatsがない場合 (poke-envの仕様によるが、通常は推定値が入っているはず)
            # base_statsからVGC最速想定で計算
            base_spe = pokemon.base_stats['spe']
            level = pokemon.level
            # (种族値 * 2 + 31 + 252/4) * Level / 100 + 5
            # Lv50: (Base + 15.5 + 31.5) + 5 = Base + 52
            raw_speed = ((base_spe * 2 + 31 + 63) * level / 100) + 5
            raw_speed *= 1.1 # 補正性格
            raw_speed = float(int(raw_speed))

        # 2. ランク補正
        # -6 to +6
        # pokemon.boosts['spe']
        boost = pokemon.boosts.get('spe', 0)
        multiplier = 1.0
        if boost > 0:
            multiplier = (2 + boost) / 2
        elif boost < 0:
            multiplier = 2 / (2 + abs(boost))
        
        speed = raw_speed * multiplier
        
        # 3. まひ (Paralysis)
        if pokemon.status and pokemon.status.name == "PAR":
            # Gen 7+: 1/2
            speed *= 0.5
            
        # 4. アイテム (こだわりスカーフ)
        if pokemon.item == "choicescarf":
            speed *= 1.5
        elif pokemon.item == "ironball":
            speed *= 0.5
            
        # 5. 特性 (Ability)
        # 天候依存など
        ability = pokemon.ability
        weather = battle.weather.keys() if battle.weather else [] # dict keys
        
        # すいすい (Swift Swim) - Rain
        if ability == "swiftswim" and any(w for w in weather if "rain" in w.lower()):
            speed *= 2.0
        # ようりょくそ (Chlorophyll) - Sun
        elif ability == "chlorophyll" and any(w for w in weather if "sunny" in w.lower()):
            speed *= 2.0
        # すなかき (Sand Rush) - Sandstorm
        elif ability == "sandrush" and any(w for w in weather if "sand" in w.lower()):
            speed *= 2.0
        # ゆきかき (Slush Rush) - Snow/Hail
        elif ability == "slushrush" and any(w for w in weather if "snow" in w.lower() or "hail" in w.lower()):
            speed *= 2.0
        # クォークチャージ (Quark Drive) - Electric Terrain or Booster Energy
        # 簡易実装: 一番高いのが素早さなら1.5倍
        elif ability == "quarkdrive":
            if "electricterrain" in battle.fields or pokemon.item == "boosterenergy":
                # 本当は一番高いステータス判定が必要だが、高速アタッカーはSが高いと仮定
                # Iron Bundle, Iron Valiant etc.
                if pokemon.base_stats['spe'] >= 100: # Heuristic
                    speed *= 1.5
        # 古代活性 (Protosynthesis)
        elif ability == "protosynthesis":
            if any(w for w in weather if "sunny" in w.lower()) or pokemon.item == "boosterenergy":
                if pokemon.base_stats['spe'] >= 100: # Heuristic
                    speed *= 1.5
        # Unburden (かるわざ) - アイテム消費後 (追跡困難だが、Itemなしなら発動と仮定？いや、消費履歴が必要。一旦無視)
        
        # 6. 追い風 (Tailwind)
        # battle.side_conditions (自分の場), battle.opponent_side_conditions (相手の場)
        # poke-envのDoubleBattleでは side_conditions は辞書
        import logging
        # logging.info(f"Side Conditions: {battle.side_conditions}, Opp: {battle.opponent_side_conditions}")
        
        # pokemonがどちらのプレイヤーか判定して追い風チェック
        # active_pokemonリストに含まれるならPlayer側
        is_p1 = pokemon in battle.active_pokemon
        
        side_conds = battle.side_conditions if is_p1 else battle.opponent_side_conditions
        if "tailwind" in side_conds:
             speed *= 2.0

        return int(speed)

_turn_order_service = None

def get_turn_order_service():
    global _turn_order_service
    if _turn_order_service is None:
        _turn_order_service = TurnOrderService()
    return _turn_order_service
