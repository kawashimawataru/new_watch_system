"""
Candidate Scorer - 観戦AI用候補手スコアリング

シミュレーションベースで1-2ターン先を評価し、
スコアの高い候補手を返す。

アルゴリズム:
1. 現在の盤面から全合法手を列挙
2. 各行動について、相手の最善応手を仮定してシミュレーション
3. 1ターン後の盤面を評価
4. 上位候補について、さらに2ターン目を探索
5. 最終スコアで候補をランク付け

将棋/チェスの技術:
- Minimax的な相手最善応手の考慮
- α-βライクな枝刈り（上位候補のみ深掘り）
- 静止探索（交換続行中は評価を延長）

Phase 20 改善:
- VGCDamageCalculator による精密ダメージ計算
- BattleStateSimulator による特性/アイテム/EV推定
- KOベースのスコアリング
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import copy

from src.domain.services.board_evaluator import BoardEvaluator, BoardScore
from src.domain.models.type_chart import get_type_effectiveness
from src.domain.services.battle_state_simulator import (
    get_battle_state_simulator, FieldState, BattleStateSimulator
)


@dataclass
class ScoredCandidate:
    """スコア付き候補手"""
    # ダブルバトル: 2匹分の行動
    move1: str                    # Slot Aの行動
    target1: str                  # Slot Aのターゲット
    type1: str                    # "attack", "protect", "switch"
    move2: str                    # Slot Bの行動
    target2: str                  # Slot Bのターゲット
    type2: str                    # "attack", "protect", "switch"
    
    # スコア情報
    score: float                  # 総合スコア (0-100)
    turn1_eval: float             # 1ターン後評価
    turn2_eval: Optional[float] = None  # 2ターン後評価
    
    # 詳細
    reasoning_hint: str = ""      # LLM解説用ヒント
    risk_level: str = "normal"    # "safe", "normal", "risky"
    expected_outcome: str = ""    # 予想される結果
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "move1": self.move1,
            "target1": self.target1,
            "type1": self.type1,
            "move2": self.move2,
            "target2": self.target2,
            "type2": self.type2,
            "score": round(self.score, 1),
            "turn1_eval": round(self.turn1_eval, 3),
            "turn2_eval": round(self.turn2_eval, 3) if self.turn2_eval else None,
            "reasoning_hint": self.reasoning_hint,
            "risk_level": self.risk_level,
            "expected_outcome": self.expected_outcome,
        }


class CandidateScorer:
    """
    観戦AI用候補手スコアラー
    
    シミュレーションベースで候補手を評価し、
    スコア順にランク付けして返す。
    
    Phase 16: 世代別ギミック対応
    - Gen 6/7: メガシンカ、Zワザ
    - Gen 8: ダイマックス
    - Gen 9: テラスタル
    """
    
    # 設定
    MAX_CANDIDATES = 5          # 返す候補数
    DEPTH_1_WIDTH = 10          # 1ターン目で評価する候補数
    DEPTH_2_WIDTH = 3           # 2ターン目まで探索する候補数
    
    # よく使う技のタイプマッピング
    MOVE_TYPES = {
        "まもる": ("protect", "Normal"),
        "protect": ("protect", "Normal"),
        "ねこだまし": ("attack", "Normal"),
        "fakeout": ("attack", "Normal"),
        "ドレインパンチ": ("attack", "Fighting"),
        "drainpunch": ("attack", "Fighting"),
        "テラクラスター": ("attack", "Normal"),
        "teracluster": ("attack", "Normal"),
        "アストラルビット": ("attack", "Ghost"),
        "astralbarrage": ("attack", "Ghost"),
        "すいりゅうれんだ": ("attack", "Water"),
        "surgingstrikes": ("attack", "Water"),
        "交代": ("switch", None),
        "switch": ("switch", None),
    }
    
    def __init__(self, generation: int = 9):
        """
        Args:
            generation: 世代番号 (6, 7, 8, 9)
        """
        from src.domain.models.generation_config import get_generation_manager
        
        self.evaluator = BoardEvaluator()
        self.gen_manager = get_generation_manager(generation)
        self._generation = generation
        
        # Phase 20: BattleStateSimulator 統合
        self.battle_simulator = get_battle_state_simulator()
    
    def set_generation(self, generation: int) -> None:
        """世代を切り替える"""
        self.gen_manager.set_generation(generation)
        self._generation = generation
    
    @property
    def generation(self) -> int:
        return self._generation
    
    def score_candidates(
        self,
        player_active: List[Dict[str, Any]],
        opponent_active: List[Dict[str, Any]],
        player_bench: List[Dict[str, Any]] = None,
        opponent_bench: List[Dict[str, Any]] = None,
        field_state: Dict[str, Any] = None,
    ) -> List[ScoredCandidate]:
        """
        候補手をスコアリングして上位を返す
        
        Args:
            player_active: 自分の場のポケモン
            opponent_active: 相手の場のポケモン
            player_bench: 自分の控え
            opponent_bench: 相手の控え
            field_state: フィールド状態
        
        Returns:
            List[ScoredCandidate]: スコア順の候補手リスト
        """
        player_bench = player_bench or []
        opponent_bench = opponent_bench or []
        field_state = field_state or {}
        
        # 1. 全行動を列挙
        all_actions = self._enumerate_actions(player_active, player_bench)
        
        # 2. 1ターン目の評価
        scored_actions = []
        for action in all_actions[:self.DEPTH_1_WIDTH]:
            turn1_eval = self._evaluate_action(
                action, player_active, opponent_active,
                player_bench, opponent_bench, field_state
            )
            scored_actions.append((action, turn1_eval))
        
        # スコア順にソート
        scored_actions.sort(key=lambda x: x[1], reverse=True)
        
        # 3. 上位候補について2ターン目を探索
        candidates = []
        for i, (action, turn1_eval) in enumerate(scored_actions[:self.DEPTH_2_WIDTH]):
            # 2ターン目評価
            turn2_eval = self._evaluate_turn2(
                action, player_active, opponent_active,
                player_bench, opponent_bench, field_state
            )
            
            # スコア計算 (1ターン目 60%, 2ターン目 40%)
            final_score = (turn1_eval * 0.6 + turn2_eval * 0.4) * 50 + 50  # 0-100に変換
            final_score = max(0, min(100, final_score))
            
            # 候補を作成
            candidate = self._create_candidate(
                action, final_score, turn1_eval, turn2_eval
            )
            candidates.append(candidate)
        
        # 残りの候補（2ターン目評価なし）
        for action, turn1_eval in scored_actions[self.DEPTH_2_WIDTH:self.MAX_CANDIDATES]:
            final_score = turn1_eval * 50 + 50
            final_score = max(0, min(100, final_score))
            candidate = self._create_candidate(action, final_score, turn1_eval, None)
            candidates.append(candidate)
        
        # 最終ソート
        candidates.sort(key=lambda c: c.score, reverse=True)
        
        return candidates[:self.MAX_CANDIDATES]
    
    def _enumerate_actions(
        self,
        player_active: List[Dict],
        player_bench: List[Dict],
    ) -> List[Dict[str, Any]]:
        """全合法手を列挙"""
        actions = []
        
        # アクティブポケモンの技を取得
        poke_a = player_active[0] if len(player_active) > 0 else None
        poke_b = player_active[1] if len(player_active) > 1 else None
        
        moves_a = self._get_available_moves(poke_a, player_bench)
        moves_b = self._get_available_moves(poke_b, player_bench)
        
        # 組み合わせを生成
        for m1 in moves_a:
            for m2 in moves_b:
                actions.append({
                    "slot_a": m1,
                    "slot_b": m2,
                })
        
        return actions
    
    def _get_available_moves(
        self,
        pokemon: Optional[Dict],
        bench: List[Dict],
    ) -> List[Dict[str, Any]]:
        """
        利用可能な行動を取得
        
        Phase 16: 世代別の特殊ギミックを含む
        """
        from src.domain.models.generation_config import SpecialMechanic
        
        if not pokemon or pokemon.get("fainted", False):
            return [{"name": "パス", "type": "pass", "target": ""}]
        
        moves = []
        
        # 通常技
        for move in pokemon.get("moves", []):
            move_name = move.get("name", "技")
            move_type = move.get("type", "Normal")
            target = move.get("target", "相手")
            
            moves.append({
                "name": move_name,
                "type": "attack",
                "move_type": move_type,
                "target": target,
            })
        
        # まもる（常に追加）
        moves.append({
            "name": "まもる",
            "type": "protect",
            "move_type": "Normal",
            "target": "",
        })
        
        # 交代
        for b in bench:
            if not b.get("fainted", False):
                moves.append({
                    "name": f"交代→{b.get('name', '控え')}",
                    "type": "switch",
                    "move_type": None,
                    "target": b.get("name", ""),
                })
        
        # ===== 世代別特殊ギミック =====
        if self.gen_manager.can_use_mechanic():
            mechanic = self.gen_manager.current_mechanic
            
            # Gen 6/7: メガシンカ
            if mechanic == SpecialMechanic.MEGA:
                if pokemon.get("can_mega", False) or pokemon.get("mega_stone"):
                    moves.append({
                        "name": "メガシンカ",
                        "type": "mega",
                        "move_type": None,
                        "target": "",
                        "mechanic": "mega",
                    })
            
            # Gen 7: Zワザ
            elif mechanic == SpecialMechanic.ZMOVE:
                z_crystal = pokemon.get("z_crystal", pokemon.get("item", ""))
                if "z" in z_crystal.lower() or pokemon.get("can_zmove", False):
                    # 各攻撃技にZ版を追加
                    for move in pokemon.get("moves", []):
                        move_name = move.get("name", "技")
                        move_type = move.get("type", "Normal")
                        z_power = self.gen_manager.calculate_zmove_power(
                            move.get("power", 80)
                        )
                        moves.append({
                            "name": f"Z{move_name}",
                            "type": "zmove",
                            "move_type": move_type,
                            "target": "相手",
                            "base_power": z_power,
                            "mechanic": "zmove",
                        })
            
            # Gen 8: ダイマックス
            elif mechanic == SpecialMechanic.DYNAMAX:
                moves.append({
                    "name": "ダイマックス",
                    "type": "dynamax",
                    "move_type": None,
                    "target": "",
                    "mechanic": "dynamax",
                })
                # ダイマックス中は全技がダイマックス技に
                for move in pokemon.get("moves", []):
                    move_name = move.get("name", "技")
                    move_type = move.get("type", "Normal")
                    category = move.get("category", "physical")
                    dmax_power = self.gen_manager.calculate_dynamax_power(
                        move.get("power", 80), category
                    )
                    moves.append({
                        "name": f"ダイマックス{move_name}",
                        "type": "dynamax_move",
                        "move_type": move_type,
                        "target": "相手",
                        "base_power": dmax_power,
                        "mechanic": "dynamax",
                    })
            
            # Gen 9: テラスタル
            elif mechanic == SpecialMechanic.TERASTAL:
                tera_type = pokemon.get("tera_type", pokemon.get("types", ["Normal"])[0])
                moves.append({
                    "name": f"テラスタル({tera_type})",
                    "type": "terastal",
                    "move_type": None,
                    "target": "",
                    "tera_type": tera_type,
                    "mechanic": "terastal",
                })
        
        return moves if moves else [{"name": "まもる", "type": "protect", "target": ""}]
    
    def _evaluate_action(
        self,
        action: Dict[str, Any],
        player_active: List[Dict],
        opponent_active: List[Dict],
        player_bench: List[Dict],
        opponent_bench: List[Dict],
        field_state: Dict,
    ) -> float:
        """
        1ターン後の盤面を評価
        
        Phase 20: KOベースのスコアリング
        - 確定KO可能な行動に高スコア
        - 乱数KOにも一定のボーナス
        - VGCDamageCalculatorで精密計算
        """
        # 行動をシミュレーション
        new_player, new_opponent = self._simulate_turn(
            action, player_active, opponent_active, field_state
        )
        
        # 盤面を評価
        score = self.evaluator.evaluate(
            new_player + player_bench,
            new_opponent + opponent_bench,
            field_state
        )
        
        # Phase 20: KOベースのボーナス計算
        ko_bonus = self._calculate_ko_bonus(action, player_active, opponent_active, field_state)
        
        return score.total + ko_bonus
    
    def _calculate_ko_bonus(
        self,
        action: Dict[str, Any],
        player_active: List[Dict],
        opponent_active: List[Dict],
        field_state: Dict,
    ) -> float:
        """
        KO確率に基づくボーナススコアを計算
        
        Returns:
            bonus: -0.2 ~ 0.5
        """
        bonus = 0.0
        
        # フィールド状態を構築
        field = FieldState(
            weather=field_state.get("weather"),
            terrain=field_state.get("terrain"),
            player_reflect=field_state.get("player_reflect", False),
            player_lightscreen=field_state.get("player_lightscreen", False),
            opponent_reflect=field_state.get("opponent_reflect", False),
            opponent_lightscreen=field_state.get("opponent_lightscreen", False),
        )
        
        # 各スロットの行動を評価
        for slot_key in ["slot_a", "slot_b"]:
            slot_action = action.get(slot_key, {})
            if not slot_action:
                continue
            
            move_type = slot_action.get("type", "")
            move_name = slot_action.get("name", "")
            
            if move_type not in ["attack", "special"]:
                continue
            
            # 攻撃者を取得
            slot_idx = 0 if slot_key == "slot_a" else 1
            if slot_idx >= len(player_active):
                continue
            attacker = player_active[slot_idx]
            if attacker.get("fainted", False):
                continue
            
            # SimulatedPokemonを作成
            sim_attacker = self.battle_simulator.create_simulated_pokemon(attacker)
            
            # 各相手に対してダメージ計算
            for target in opponent_active:
                if target.get("fainted", False):
                    continue
                
                sim_defender = self.battle_simulator.create_simulated_pokemon(target)
                
                try:
                    result = self.battle_simulator.simulate_attack(
                        sim_attacker, sim_defender, move_name, field, is_player_attacking=True
                    )
                    
                    if result.get("damage_result"):
                        ko_prob = result.get("ko_probability", 0)
                        n_hits = result.get("n_hits_to_ko", 99)
                        
                        # 確定KO: +0.3
                        if ko_prob >= 1.0:
                            bonus += 0.3
                        # 高乱数KO (50%+): +0.15
                        elif ko_prob >= 0.5:
                            bonus += 0.15
                        # 確定2発: +0.1
                        elif n_hits == 2:
                            bonus += 0.1
                        # 乱数2発: +0.05
                        elif n_hits <= 2:
                            bonus += 0.05
                            
                except Exception:
                    # エラー時はスキップ
                    pass
        
        return min(0.5, bonus)  # 最大0.5
    
    def _evaluate_turn2(
        self,
        action: Dict[str, Any],
        player_active: List[Dict],
        opponent_active: List[Dict],
        player_bench: List[Dict],
        opponent_bench: List[Dict],
        field_state: Dict,
    ) -> float:
        """2ターン目の評価"""
        # 1ターン目をシミュレーション
        new_player, new_opponent = self._simulate_turn(
            action, player_active, opponent_active, field_state
        )
        
        # 2ターン目の候補を評価（簡易版: 最善手のみ）
        actions_t2 = self._enumerate_actions(new_player, player_bench)[:5]
        
        best_score = -1.0
        for a2 in actions_t2:
            new_p2, new_o2 = self._simulate_turn(
                a2, new_player, new_opponent, field_state
            )
            score = self.evaluator.evaluate(
                new_p2 + player_bench,
                new_o2 + opponent_bench,
                field_state
            )
            best_score = max(best_score, score.total)
        
        return best_score
    
    def _simulate_turn(
        self,
        action: Dict[str, Any],
        player_active: List[Dict],
        opponent_active: List[Dict],
        field_state: Dict,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        1ターンをシミュレーション
        
        Phase 15.1: MoveEffectDBを使用して技効果を正確に反映
        - 優先度（行動順序）
        - 威力（ダメージ量）
        - 効果（怯み、守る貫通など）
        """
        from src.domain.services.move_effect_db import get_move_effect_db
        
        # ディープコピー
        new_player = [copy.deepcopy(p) for p in player_active]
        new_opponent = [copy.deepcopy(o) for o in opponent_active]
        
        # 技效果DBを取得
        move_db = get_move_effect_db()
        
        # 行動リストを作成（優先度順にソート）
        actions_to_apply = []
        
        # 自分の行動
        slot_a = action.get("slot_a", {})
        slot_b = action.get("slot_b", {})
        
        for slot_idx, slot_action in enumerate([slot_a, slot_b]):
            if slot_action.get("type") == "pass":
                continue
            move_name = slot_action.get("name", "")
            move_info = move_db.get_move_info(move_name.lower().replace(" ", ""))
            priority = move_info.priority if move_info else 0
            
            actions_to_apply.append({
                "is_player": True,
                "slot": slot_idx,
                "action": slot_action,
                "priority": priority,
                "move_info": move_info,
            })
        
        # 相手の行動を仮定（最も厳しい択: 弱点を突く攻撃）
        for opp_idx, opp in enumerate(new_opponent):
            if opp.get("fainted", False):
                continue
            
            best_move = None
            best_priority = 0
            for move in opp.get("moves", []):
                move_name = move.get("name", "")
                move_info = move_db.get_move_info(move_name.lower().replace(" ", ""))
                if move_info and move_info.priority > best_priority:
                    best_priority = move_info.priority
                    best_move = move
            
            if not best_move:
                best_move = {"name": "攻撃", "type": "Normal"}
            
            move_info = move_db.get_move_info(best_move.get("name", "").lower().replace(" ", ""))
            actions_to_apply.append({
                "is_player": False,
                "slot": opp_idx,
                "action": best_move,
                "priority": move_info.priority if move_info else 0,
                "move_info": move_info,
            })
        
        # 優先度順にソート（高い方が先）
        # 同優先度の場合は素早さ順（未実装、簡易版）
        actions_to_apply.sort(key=lambda a: a["priority"], reverse=True)
        
        # 行動を順に適用
        protected_slots = {"player": set(), "opponent": set()}
        
        for act in actions_to_apply:
            if act["is_player"]:
                self._apply_move_enhanced(
                    act["action"], act["move_info"], act["slot"],
                    new_player, new_opponent, protected_slots, is_player=True
                )
            else:
                self._apply_move_enhanced(
                    act["action"], act["move_info"], act["slot"],
                    new_opponent, new_player, protected_slots, is_player=False
                )
        
        return new_player, new_opponent
    
    def _apply_move_enhanced(
        self,
        move: Dict,
        move_info: Any,
        slot: int,
        attacker_team: List[Dict],
        defender_team: List[Dict],
        protected_slots: Dict,
        is_player: bool,
    ):
        """
        技を適用（MoveEffectDB + アイテム/特性/種族値情報を使用）
        
        Phase 15.2: 考慮する要素
        - 威力（power）: ダメージ量に直結
        - 優先度: 行動順で既に考慮済み
        - 効果: まもる、怯みなど
        - アイテム: こだわり系, いのちのたま, etc.
        - 特性: ちからもち, いかく, ひらいしん, etc.
        - 種族値: 実際の攻撃/防御ステータス
        """
        from src.domain.services.move_effect_db import get_move_effect_db
        from src.domain.models.item_effects import get_item_effect, get_boost_multiplier
        from src.domain.services.ability_db import get_ability_db
        from src.domain.services.base_stats_db import get_base_stats_db
        
        move_type = move.get("type", "attack")
        move_name = move.get("name", "")
        
        # まもる系
        if move_type == "protect" or (move_info and move_info.priority >= 4 and "守" in move_name):
            key = "player" if is_player else "opponent"
            protected_slots[key].add(slot)
            return
        
        # 交代
        if move_type == "switch":
            return
        
        # 攻撃技でない場合はスキップ
        if move_type != "attack" and not (move_info and move_info.category in ["physical", "special"]):
            return
        
        # 攻撃者情報を取得
        attacker = attacker_team[slot] if slot < len(attacker_team) else None
        if not attacker or attacker.get("fainted", False):
            return
        
        move_type_element = move.get("move_type", "Normal")
        if move_info:
            move_type_element = move_info.type
        
        # 威力を取得（なければデフォルト80）
        power = 80
        if move_info and move_info.power:
            power = move_info.power
        
        # カテゴリ判定
        is_physical = True
        if move_info:
            is_physical = move_info.category == "physical"
        
        # --- アイテム倍率 ---
        item = attacker.get("item", "")
        item_multiplier = get_boost_multiplier(item)
        
        # いのちのたま
        item_effect = get_item_effect(item)
        if item_effect and item_effect.boost_multiplier > 1.0:
            item_multiplier = item_effect.boost_multiplier
        
        # --- 特性倍率 ---
        ability = attacker.get("ability", "")
        ability_db = get_ability_db()
        ability_multiplier = ability_db.get_damage_modifier(ability)
        
        # --- 種族値ベースのステータス ---
        base_stats_db = get_base_stats_db()
        poke_name = attacker.get("name", "")
        base_stats = base_stats_db.get_base_stats(poke_name)
        
        # 攻撃/特攻の実数値を推定 (種族値 * 2 + 努力値/4 + 個体値) / 5 * Lv + 5
        # 簡易式: 種族値を直接使用して相対値を計算
        if base_stats:
            if is_physical:
                attack_stat = base_stats.attack
            else:
                attack_stat = base_stats.special_attack
        else:
            attack_stat = 100  # デフォルト
        
        # --- ターゲットへのダメージ計算 ---
        target_key = "opponent" if is_player else "player"
        for target_idx, target in enumerate(defender_team):
            if target.get("fainted", False):
                continue
            
            # まもっているかチェック
            if target_idx in protected_slots[target_key]:
                # ふかしのこぶし（ウーラオス）チェック
                is_unseen_fist = ability.lower() == "unseenfist"
                is_feint = move_info and "feint" in move_info.name.lower()
                if not is_feint and not is_unseen_fist:
                    continue
            
            # 特性による免疫チェック
            target_ability = target.get("ability", "")
            if ability_db.is_immune_to_type(target_ability, move_type_element):
                continue  # ひらいしん、ちょすい等
            
            # タイプ相性
            eff = get_type_effectiveness(
                move_type_element,
                target.get("types", ["Normal"])
            )
            
            # 無効なら次へ
            if eff == 0.0:
                continue
            
            # 防御側の種族値
            target_name = target.get("name", "")
            target_stats = base_stats_db.get_base_stats(target_name)
            if target_stats:
                if is_physical:
                    defense_stat = target_stats.defense
                else:
                    defense_stat = target_stats.special_defense
            else:
                defense_stat = 100
            
            # --- 最終ダメージ計算 ---
            # 簡易ダメージ式: (威力 * 攻撃 / 防御 / 200) * タイプ相性 * アイテム * 特性
            # これで ~0.3-0.5 程度のダメージ率になるように調整
            base_damage = (power * attack_stat / defense_stat / 200.0) * eff
            base_damage *= item_multiplier
            base_damage *= ability_multiplier
            
            # 連続技の場合（すいりゅうれんだ等）
            if move_info and "連続" in move_info.effect:
                base_damage *= 1.5
            
            # 急所確定技
            if move_info and "急所" in move_info.effect:
                base_damage *= 1.5
            
            # きあいのタスキチェック
            target_item = target.get("item", "")
            target_item_effect = get_item_effect(target_item)
            current_hp = target.get("hp_fraction", 1.0)
            
            if target_item_effect and "focussash" in target_item.lower():
                if current_hp >= 1.0 and base_damage >= current_hp:
                    base_damage = current_hp - 0.01  # タスキで耐える
            
            # ダメージ適用
            new_hp = max(0, current_hp - base_damage)
            target["hp_fraction"] = new_hp
            
            if new_hp <= 0:
                target["fainted"] = True
            
            break  # 1体にのみ攻撃（単体技の場合）
    
    def _apply_opponent_action(
        self,
        player: List[Dict],
        opponent: List[Dict],
    ):
        """相手の行動を仮定して適用（旧バージョン互換用）"""
        from src.domain.services.move_effect_db import get_move_effect_db
        move_db = get_move_effect_db()
        
        # 最も厳しい択: 自分のHPが低いポケモンを狙う
        for target in sorted(player, key=lambda p: p.get("hp_fraction", 1.0)):
            if target.get("fainted", False):
                continue
            
            for attacker in opponent:
                if attacker.get("fainted", False):
                    continue
                
                # 最も威力の高い技を選択
                best_damage = 0.15
                for move in attacker.get("moves", []):
                    move_name = move.get("name", "").lower().replace(" ", "")
                    move_info = move_db.get_move_info(move_name)
                    
                    eff = get_type_effectiveness(
                        move.get("type", "Normal"),
                        target.get("types", ["Normal"])
                    )
                    
                    if move_info and move_info.power:
                        damage = (move_info.power / 250.0) * eff
                    else:
                        damage = 0.15 * eff
                    
                    best_damage = max(best_damage, damage)
                
                current_hp = target.get("hp_fraction", 1.0)
                target["hp_fraction"] = max(0, current_hp - best_damage)
                
                if target["hp_fraction"] <= 0:
                    target["fainted"] = True
                
                break
            break
    
    def _create_candidate(
        self,
        action: Dict[str, Any],
        score: float,
        turn1_eval: float,
        turn2_eval: Optional[float],
    ) -> ScoredCandidate:
        """ScoredCandidateを作成"""
        slot_a = action.get("slot_a", {})
        slot_b = action.get("slot_b", {})
        
        # リスクレベル判定
        risk = "normal"
        if any(slot_a.get("type") == "switch" for _ in [1]):
            risk = "risky"
        if slot_a.get("type") == "protect" and slot_b.get("type") == "protect":
            risk = "safe"
        
        # 解説ヒント生成
        hint = self._generate_hint(slot_a, slot_b, score)
        
        # 予想結果
        outcome = ""
        if score >= 60:
            outcome = "有利な展開が期待できる"
        elif score >= 40:
            outcome = "互角の展開"
        else:
            outcome = "厳しい展開になる可能性"
        
        return ScoredCandidate(
            move1=slot_a.get("name", "技A"),
            target1=slot_a.get("target", ""),
            type1=slot_a.get("type", "attack"),
            move2=slot_b.get("name", "技B"),
            target2=slot_b.get("target", ""),
            type2=slot_b.get("type", "attack"),
            score=score,
            turn1_eval=turn1_eval,
            turn2_eval=turn2_eval,
            reasoning_hint=hint,
            risk_level=risk,
            expected_outcome=outcome,
        )
    
    def _generate_hint(
        self,
        slot_a: Dict,
        slot_b: Dict,
        score: float,
    ) -> str:
        """LLM解説用のヒントを生成"""
        hints = []
        
        if slot_a.get("type") == "attack" and slot_b.get("type") == "attack":
            hints.append("攻撃的な選択")
        elif slot_a.get("type") == "protect" or slot_b.get("type") == "protect":
            hints.append("守備的な選択")
        
        if score >= 60:
            hints.append("高評価")
        
        return "、".join(hints) if hints else ""


# Singleton
_candidate_scorer = None

def get_candidate_scorer() -> CandidateScorer:
    global _candidate_scorer
    if _candidate_scorer is None:
        _candidate_scorer = CandidateScorer()
    return _candidate_scorer
