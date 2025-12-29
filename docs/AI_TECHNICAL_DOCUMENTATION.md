# VGC AI Battle System - 技術ドキュメント

> **目的**: 本ドキュメントは、VGC AI Battle System の設計・実装を外部エンジニアが理解できるよう、詳細に解説します。

**最終更新**: 2025-12-29

---

## 📋 目次

1. [システム概要](#1-システム概要)
2. [アーキテクチャ](#2-アーキテクチャ)
3. [予測エンジン](#3-予測エンジン)
4. [行動選択ロジック](#4-行動選択ロジック)
5. [ドメインサービス](#5-ドメインサービス)
6. [データフロー](#6-データフロー)
7. [主要アルゴリズム](#7-主要アルゴリズム)
8. [観戦システム（将来構想）](#8-観戦システム将来構想)
9. [今後の課題・改善案](#9-今後の課題改善案)

---

## 1. システム概要

### 1.1 目的
ポケモン VGC（Video Game Championships）のダブルバトルにおいて、人間プレイヤーと対戦可能なAIを構築する。

### 1.2 主要機能
| 機能 | 説明 |
|------|------|
| **対戦AI** | Pokemon Showdown 上で人間のチャレンジを受けて自動対戦 |
| **勝率予測** | 各ターンで双方の勝率をリアルタイム表示 |
| **行動予測** | 自分・相手両方の次のターンの行動確率を表示 |
| **行動順序予測** | 素早さ・優先度・天候を考慮した攻撃順を表示 |

### 1.3 技術スタック
- **Python 3.11+**
- **poke-env**: Pokemon Showdown クライアントライブラリ
- **LightGBM**: 勝率予測モデル（Fast-Lane）
- **カスタムMCTS**: モンテカルロ木探索（Slow-Lane）

---

## 2. アーキテクチャ

### 2.1 レイヤード構造

```text
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation Layer                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  VGCAIPlayer (frontend/vgc_ai_player.py)                │   │
│  │  - poke-env Player を継承                               │   │
│  │  - choose_move() で行動選択                             │   │
│  │  - チームプレビュー、勝率表示、行動予測表示             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Strategy Layer                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  HybridStrategist (predictor/player/hybrid_strategist)  │   │
│  │  - Fast-Lane (LightGBM) + Slow-Lane (MCTS) を統合       │   │
│  │  - predict_both() で両方の予測を同時実行                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│          ┌───────────────────┼───────────────────┐              │
│          ▼                   ▼                   ▼              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │
│  │ FastStrategist│   │ MonteCarloSt │   │ (Future)     │        │
│  │ (LightGBM)   │   │ (MCTS)       │   │ AlphaZero    │        │
│  └──────────────┘   └──────────────┘   └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Domain Layer                                  │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐      │
│  │ ActionFilter   │ │ TurnOrder      │ │ Knowledge      │      │
│  │ Service        │ │ Service        │ │ Service        │      │
│  └────────────────┘ └────────────────┘ └────────────────┘      │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐      │
│  │ Move Model     │ │ Item Model     │ │ TypeChart      │      │
│  └────────────────┘ └────────────────┘ └────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ShowdownDataLoader (Showdown JSON読み込み)             │   │
│  │  SmogonCalcWrapper (ダメージ計算API)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 ファイル構成

```
new_watch_game_system/
├── frontend/
│   └── vgc_ai_player.py        # メインAIプレイヤー (約1000行)
├── predictor/
│   ├── player/
│   │   ├── hybrid_strategist.py    # Fast+Slow統合
│   │   ├── fast_strategist.py      # LightGBM
│   │   └── monte_carlo_strategist.py # MCTS (約600行)
│   └── core/
│       ├── models.py               # BattleState等データモデル
│       └── eval_algorithms/
│           └── heuristic_eval.py   # ヒューリスティック評価
├── src/domain/
│   ├── models/
│   │   ├── move.py                 # 技データモデル
│   │   ├── item.py                 # アイテムデータモデル
│   │   └── type_chart.py           # タイプ相性表
│   ├── services/
│   │   ├── action_filter_service.py # こだわりロック等
│   │   ├── turn_order_service.py   # 行動順序計算
│   │   └── knowledge_service.py    # 外部知識サービス
│   └── adapters/
│       └── showdown_data_loader.py # JSONデータ読み込み
└── scripts/
    └── run_vgc_ai.py              # 起動スクリプト
```

---

## 3. 予測エンジン

### 3.1 HybridStrategist

**役割**: 2つの予測手法を組み合わせて、速度と精度のバランスを取る。

```python
class HybridStrategist:
    def predict_both(self, battle_state: BattleState):
        """
        Fast-Lane と Slow-Lane を並行実行
        
        Returns:
            (fast_result, slow_result)
        """
        fast_result = self.fast_strategist.predict(battle_state)
        slow_result = self.mcts_strategist.predict_win_rate(battle_state)
        return fast_result, slow_result
```

| Lane | 手法 | レイテンシ | 精度 | 用途 |
|------|------|----------|------|------|
| **Fast-Lane** | LightGBM | < 1ms | 中 | 即時応答、勝率概算 |
| **Slow-Lane** | MCTS | 10-100ms | 高 | 最適手探索、詳細予測 |

### 3.2 Fast-Lane (LightGBM)

**モデルファイル**: `models/fast_lane.pkl`

**入力特徴量** (13個):
```python
features = [
    "p1_active_hp_sum",      # P1のアクティブポケモンHP合計
    "p2_active_hp_sum",      # P2のアクティブポケモンHP合計
    "p1_reserves_count",     # P1の控えポケモン数
    "p2_reserves_count",     # P2の控えポケモン数
    "p1_status_count",       # P1の状態異常数
    "p2_status_count",       # P2の状態異常数
    "turn_number",           # 現在のターン数
    "weather_code",          # 天候
    "terrain_code",          # フィールド
    "p1_tailwind_active",    # P1追い風
    "p2_tailwind_active",    # P2追い風
    "p1_trickroom_active",   # トリックルーム
    "p1_boost_sum",          # P1ステータス変化合計
]
```

**出力**: P1勝率 (0.0 - 1.0)

### 3.3 Slow-Lane (MCTS)

**アルゴリズム**: モンテカルロ木探索 + Guided Playouts

```python
class MonteCarloStrategist:
    def __init__(self, n_rollouts=300, max_turns=15):
        self.n_rollouts = n_rollouts
        self.max_turns = max_turns
        self.evaluator = HeuristicEvaluator()
    
    def predict_win_rate(self, battle_state):
        """
        1. 合法手を列挙
        2. 各行動について rollouts を実行
        3. 最も勝率の高い行動を返す
        """
        legal_actions = self._get_legal_actions(battle_state)
        action_win_rates = {}
        
        for action in legal_actions:
            wins = 0
            for _ in range(trials_per_action):
                winner, _ = self._simulate_battle(battle_state, action)
                if winner == "player_a":
                    wins += 1
            action_win_rates[action] = wins / trials_per_action
        
        best_action = max(action_win_rates, key=action_win_rates.get)
        return {"optimal_action": best_action, ...}
```

#### 3.3.1 Guided Playouts (Phase 3 実装)

従来の「完全ランダム」から「ヒューリスティック重み付け選択」に改善:

```python
def _simulate_battle(self, initial_state, first_action):
    current_state = self._copy_state(initial_state)
    current_state = self._apply_action(current_state, first_action)
    
    while not game_over:
        legal_actions = self._get_legal_actions(current_state)
        
        # Guided Playouts: 重み付きランダム選択
        action_candidates = self._convert_to_action_candidates(legal_actions)
        weights = self.evaluator.get_action_weights(current_state, action_candidates)
        selected_action = random.choices(legal_actions, weights=weights, k=1)[0]
        
        current_state = self._apply_action(current_state, selected_action)
    
    return winner, turns
```

**重み計算 (HeuristicEvaluator.get_action_weights)**:
```python
def get_action_weights(self, state, actions):
    scores = []
    for action in actions:
        score = self._score_action_candidate(action)
        
        # HP低下時の先制技ボーナス
        if "priority" in action.tags and actor_hp < 0.4:
            score += 0.3
        
        # Protect初回ボーナス
        if action.move == "protect":
            score += 0.15
        
        # 味方殴りペナルティ
        if "ally" in action.target:
            score -= 0.3
        
        scores.append(score)
    
    # Softmax正規化 (温度パラメータ = 0.5)
    return softmax(scores, temperature=0.5)
```

---

## 4. 行動選択ロジック

### 4.1 choose_move() の全体フロー

```python
def choose_move(self, battle: DoubleBattle):
    # 1. 盤面情報を表示
    self._display_battle_state(battle)
    
    # 2. BattleState に変換
    battle_state = self._convert_battle_to_state(battle)
    
    # 3. HybridStrategist で予測
    fast_result, slow_result = self.strategist.predict_both(battle_state)
    
    # 4. 勝率を表示
    self._display_win_rates(fast_result, slow_result)
    
    # 5. 行動予測を表示
    self._display_action_predictions(battle, slow_result.alternatives)
    
    # 6. 行動選択
    if slow_result.alternatives:
        # MCTS推奨の行動を採用
        orders = self._parse_action_description(battle, slow_result.best_action)
    else:
        # ヒューリスティックにフォールバック
        orders = self._choose_heuristic_action(battle)
    
    # 7. DoubleBattleOrder を返す
    return DoubleBattleOrder(first_order=orders[0], second_order=orders[1])
```

### 4.2 ヒューリスティック行動選択

**ファイル**: `frontend/vgc_ai_player.py` の `_choose_heuristic_action()`

```python
def _choose_heuristic_action(self, battle):
    orders = []
    
    for i, pokemon in enumerate(battle.active_pokemon):
        if pokemon is None or pokemon.fainted:
            continue
        
        available_moves = battle.available_moves[i]
        item = pokemon.item
        
        # 1. こだわりロックの確認
        locked_move = self.action_filter.get_locked_move(pokemon.species)
        if locked_move and is_choice_item(item):
            available_moves = [m for m in available_moves if m.id == locked_move]
        
        # 2. Assault Vest: 変化技を除外
        if blocks_status_moves(item):
            available_moves = [m for m in available_moves if not is_status_move(m)]
        
        # 3. スコア計算
        def calculate_move_score(move):
            score = move.base_power or 50
            score += get_move_score_bonus(move.id)
            
            # 先制技ボーナス
            priority = get_move_priority(move.id)
            score += max(0, priority) * 10
            
            # 初ターン限定技 (Fake Out)
            if move.id in ["fakeout", "firstimpression"]:
                if is_first_turn:
                    score += 50
                else:
                    return -1  # 使用不可
            
            return score
        
        best_move = max(available_moves, key=calculate_move_score)
        
        # 4. ターゲット選択
        if needs_target(best_move):
            target = find_first_alive_opponent(battle)
        else:
            target = None
        
        orders.append(self.create_order(best_move, move_target=target))
    
    return orders
```

### 4.3 ターゲット指定

**poke-env のターゲット規則**:
| 値 | 意味 |
|----|------|
| `1` | 相手スロット1 (左) |
| `2` | 相手スロット2 (右) |
| `-1` | 味方スロット1 |
| `-2` | 味方スロット2 |

---

## 5. ドメインサービス

### 5.1 ActionFilterService

**役割**: こだわり系アイテムのロック状態追跡、使用可能技のフィルタリング

```python
class ActionFilterService:
    def __init__(self):
        self._locked_moves: Dict[str, str] = {}  # {species: move_id}
    
    def get_locked_move(self, species: str) -> Optional[str]:
        """ロックされた技を取得"""
        return self._locked_moves.get(species)
    
    def update_lock_status(self, species: str, item: str, move_id: str):
        """技を使用した際にロック状態を更新"""
        if is_choice_item(item):
            self._locked_moves[species] = move_id
    
    def clear_lock(self, species: str):
        """交代時にロック解除"""
        self._locked_moves.pop(species, None)
```

### 5.2 TurnOrderService

**役割**: 行動順序の計算（素早さ、追い風、トリックルーム、麻痺、アイテム、特性を考慮）

```python
class TurnOrderService:
    def calculate_turn_order(self, pokemon_list, field_conditions):
        """
        行動順序を計算
        
        考慮要素:
        - 基礎素早さ + ランク補正
        - 麻痺 (0.5倍)
        - こだわりスカーフ (1.5倍)
        - くろいてっきゅう (0.5倍)
        - 追い風 (2.0倍)
        - トリックルーム (素早さ逆順)
        - すいすい / ようりょくそ等の天候特性
        """
        results = []
        for pokemon in pokemon_list:
            speed = self._calculate_effective_speed(pokemon, field_conditions)
            results.append((pokemon, speed))
        
        # トリックルーム時は逆順
        if field_conditions.trick_room:
            results.sort(key=lambda x: x[1])
        else:
            results.sort(key=lambda x: x[1], reverse=True)
        
        return results
```

### 5.3 KnowledgeService (PokeLLMon KAG参考)

**役割**: タイプ相性、先制技、危険特性などの「知識」を提供

```python
class KnowledgeService:
    def get_type_matchup_advice(self, move_type, defender_types):
        """タイプ相性のアドバイス"""
        effectiveness = calculate_effectiveness(move_type, defender_types)
        if effectiveness >= 2.0:
            return (effectiveness, "効果抜群！")
        elif effectiveness == 0.0:
            return (effectiveness, "無効（タイプ相性）")
        ...
    
    def get_ability_warning(self, ability):
        """危険な特性の警告"""
        # intimidate, prankster, wonderguard 等
        return self.DANGEROUS_ABILITIES.get(ability)
    
    def should_avoid_move(self, move_type, defender_types, defender_ability):
        """この技を避けるべきか判定"""
        # タイプ相性 or 特性による無効化をチェック
        ...
```

---

## 6. データフロー

```text
[Pokemon Showdown Server]
        │
        │ Websocket
        ▼
[poke-env Client]
        │
        │ Battle オブジェクト
        ▼
[VGCAIPlayer.choose_move()]
        │
        ├──1. _convert_battle_to_state()
        │      BattleState に変換
        ▼
[HybridStrategist.predict_both()]
        │
        ├──Fast-Lane
        │   └── LightGBM で勝率予測
        │
        └──Slow-Lane
            └── MCTS + Guided Playouts
                    │
                    └── HeuristicEvaluator で重み計算
        │
        ▼
[行動選択]
        │
        ├── MCTS推奨があれば採用
        └── なければ _choose_heuristic_action()
                │
                ├── ActionFilterService (ロック確認)
                ├── TurnOrderService (順序計算)
                └── KnowledgeService (タイプ相性)
        │
        ▼
[DoubleBattleOrder]
        │
        │ /choose move thunderbolt 1, move protect
        ▼
[Pokemon Showdown Server]
```

---

## 7. 主要アルゴリズム

### 7.1 ダメージ計算

```python
def _calculate_damage(self, attacker, defender, move_name):
    """簡易ダメージ計算（ダメージ率を返す）"""
    move = Move(move_name)
    base_power = move.base_power
    
    # アイテム補正
    if attacker.item:
        item = Item(attacker.item)
        base_power *= item.get_damage_modifier(move.type, move.is_physical)
    
    # ステータスベース計算
    atk = max(attacker.attack, attacker.special_attack)
    defense = min(defender.defense, defender.special_defense)
    
    damage_pct = (base_power * atk / defense / 200.0)
    
    # 半減実による軽減
    if defender.item:
        def_item = Item(defender.item)
        resist_type = def_item.get_resist_berry_type()
        if resist_type == move.type and effectiveness > 1.0:
            damage_pct *= 0.5
    
    return min(damage_pct, 1.0)
```

### 7.2 Consistent Action Generation (PokeLLMon参考)

**問題**: AIがパニック状態で非合理的な交代を連発する

**解決策**: 交代ペナルティをHP状況に応じて調整

```python
def _score_action_candidate(self, action):
    score = base_score
    
    # パニック交代ペナルティ
    if action.is_switch:
        if actor_hp > 0.7:
            score -= 0.4  # HP高いのに交代は大幅減点
        elif actor_hp > 0.4:
            score -= 0.15
        else:
            score -= 0.05  # HP低い場合は妥当
    
    # 連続Protectペナルティ
    if action.move == "protect" and consecutive_protects > 0:
        score -= 0.3 * consecutive_protects
    
    # 無効技の回避
    if action.is_immune:
        score -= 1.0
    
    return score
```

---

## 8. 観戦システム（将来構想）

### 8.1 概要

**現状**: 未実装

**目標**: Nintendo Switch の実機バトルを観戦し、リアルタイムでAI予測を表示するシステム

### 8.2 システム構成図

```text
┌──────────────────────────────────────────────────────────────────┐
│                    Nintendo Switch                                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  ポケモン スカーレット/バイオレット                        │  │
│  │  (VGCバトル画面)                                           │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ HDMI / キャプチャボード
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    キャプチャデバイス                             │
│  - Elgato HD60 S / AVerMedia 等                                  │
│  - OBS Studio / ffmpeg でフレーム取得                            │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ 映像フレーム (30fps)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    画面認識モジュール                             │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  ScreenReader (src/infrastructure/screen_reader.py)        │  │
│  │  - OCR: ポケモン名、HP、技名を読み取り                     │  │
│  │  - 画像認識: ポケモン画像からspeciesを特定                 │  │
│  │  - 状態検出: 状態異常アイコン、天候、フィールド            │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  技術候補:                                                  │  │
│  │  - Tesseract OCR / EasyOCR                                 │  │
│  │  - OpenCV テンプレートマッチング                           │  │
│  │  - YOLOv8 / ResNet でポケモン認識                          │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ BattleState (標準化データ)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    AI予測エンジン (既存)                          │
│  - HybridStrategist                                               │
│  - TurnOrderService                                               │
│  - KnowledgeService                                               │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ 予測結果
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    表示レイヤー                                   │
│  - OBS ブラウザソース + WebSocket                                │
│  - 勝率予測、行動予測、行動順序をオーバーレイ表示                │
└──────────────────────────────────────────────────────────────────┘
```

### 8.3 データフロー

1. **Switch画面キャプチャ** → キャプチャボードで映像取得
2. **OCR/画像認識** → ポケモン名、HP、技名を抽出
3. **BattleState変換** → 既存AIシステム互換形式に
4. **AI予測** → HybridStrategist で勝率・行動予測
5. **オーバーレイ表示** → 配信画面に予測結果を重ねて表示

### 8.4 技術的課題

| 課題 | 難易度 | 解決案 |
|------|--------|--------|
| OCRの精度 | 高 | 日本語/英語両対応モデル |
| ポケモン認識 | 高 | 画像分類モデル or テンプレートマッチング |
| HP読み取り | 中 | HPバーの色・長さから割合計算 |

---

## 9. 今後の課題・改善案

### 9.1 未解決課題

| 優先度 | 課題 | 詳細 |
|--------|------|------|
| 高 | LightGBM特徴量不足 | 13個では精度限界。タイプ相性、技情報を追加 |
| 高 | 選出ロジック | 現在は先頭4匹固定。相手チームを見て最適化 |
| 中 | AlphaZero統合 | Policy/Value NN + MCTS |
| 中 | In-Context RL | バトルフィードバックからリアルタイム学習 |

### 9.2 改善案（PokeLLMon研究に基づく）

1. **Knowledge-Augmented Generation (KAG)**
   - 現状: `KnowledgeService` で基本実装済み
   - 改善: Pokedex全データの統合、能力説明文のNLP解析

2. **In-Context Reinforcement Learning (ICRL)**
   - 現状: 未実装
   - 改善: バトル結果をLLMに入力し、戦略を動的調整

3. **Opponent Modeling**
   - 現状: 相手の技予測は威力ベースのみ
   - 改善: 相手のプレイスタイル（攻撃的/守備的）を推定



## 📚 参考資料

- [PokeLLMon: A Human-Parity Agent for Pokemon Battles with LLMs](https://arxiv.org/abs/2402.01118)
- [PokeAgent Challenge - NeurIPS 2025](https://pokeagent.github.io/)
- [poke-env ドキュメント](https://poke-env.readthedocs.io/)

---

**作成者**: Antigravity (AI Assistant)
