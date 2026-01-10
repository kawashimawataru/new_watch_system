# VGC AI System - アーキテクチャ仕様書

**最終更新**: 2025-12-31 17:55

---

## 📋 目次

1. [システム概要](#1-システム概要)
2. [アーキテクチャ図](#2-アーキテクチャ図)
3. [コンポーネント詳細](#3-コンポーネント詳細)
4. [Phase 7: 探索最適化](#4-phase-7-探索最適化)
5. [Phase 3: 試合データベース](#5-phase-3-試合データベース)
6. [データフロー](#6-データフロー)
7. [判断ロジック](#7-判断ロジック)
8. [ファイル構成](#8-ファイル構成)
9. [論文との整合](#9-論文との整合)

---

## 1. システム概要

### 目的

VGCダブルバトル（ポケモン対戦）において、AIが勝率最大化のための最適行動を選択するシステム。

### 設計思想

1. **リスク管理重視**: 「読み」ではなく「安定行動」を基本とする
2. **探索ベース**: MCTS + Quantal Response によるゲーム理論的アプローチ
3. **LLM補助**: 戦略的判断の補助にLLMを活用（主処理はシミュレーション）
4. **データ蓄積**: 全試合をSQLiteに記録し、後の分析・学習に活用

---

## 2. アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        VGCPredictorPlayer                                │
│                  (scripts/run_predictor_trial.py)                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
     ┌───────────────────────────┼───────────────────────────┐
     ▼                           ▼                           ▼
┌─────────────┐          ┌─────────────────┐          ┌─────────────────┐
│ TurnAdvisor │          │   GameSolver    │          │ BattleRecorder  │
│   (LLM)     │          │  (MCTS+TT)      │          │   (SQLite)      │
└──────┬──────┘          └────────┬────────┘          └────────┬────────┘
       │                          │                            │
       │              ┌───────────┴───────────┐                │
       │              ▼                       ▼                ▼
       │    ┌──────────────────┐    ┌──────────────────┐  ┌───────────┐
       │    │ CandidateGenerator│   │ SmogonCalcWrapper│  │   SQLite  │
       │    │ (Progressive W)  │    │   (メモ化)       │  │   DB      │
       │    └──────────────────┘    └──────────────────┘  └───────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        行動選択ロジック                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │  Protect   │  │   Tera     │  │   Switch   │  │  Attack    │        │
│  │ 即死回避優先 │  │ 生存/遂行  │  │ 被ダメ比較  │  │ MCTS最善手 │        │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 依存関係サマリー

```
VGCPredictorPlayer
├── TurnAdvisor (LLM候補絞り込み)
│   └── ConsistentTurnAdvisor (投票で安定化)
├── VGCPredictor
│   └── GameSolver (MCTS探索)
│       ├── CandidateGenerator (候補生成 + Progressive Widening)
│       ├── Evaluator (局面評価)
│       ├── SimulatorAdapter (盤面遷移)
│       ├── Transposition Table (キャッシュ)
│       └── SmogonCalcWrapper (ダメ計 + メモ化)
├── DeterminizedSolver (K=10 仮説)
│   └── BeliefState (隠れ情報確率)
├── RiskAwareSolver (Secure/Gamble)
├── TacticalMixer (戦術テンプレ)
├── BattleMemory (状態追跡)
├── StyleUpdater (相手スタイル推定)
├── BattleRecorder (試合記録)
│   └── SQLite DB (battles, turns, pokemon_snapshots)
├── StatParticleFilter (EV/実数値推定) ← Phase 8-1
├── FictitiousPlay (ゲーム理論均衡) ← Phase 8-2
├── OpponentModelAdvisor (LLM相手モデル) ← Phase 8-3
└── EndgameSolver (終盤読み切り) ← Phase 8-4
```

---

## 3. コンポーネント詳細

### 3.1 VGCPredictorPlayer

**役割**: poke-env ベースの対戦プレイヤー。全コンポーネントを統合。

**初期化コンポーネント**:
- TurnAdvisor (LLM)
- BattleMemory
- BeliefState
- StyleUpdater
- RiskAwareSolver
- TacticalMixer
- BattleRecorder (Phase 3)
- **StatParticleFilter** (Phase 8-1)
- **OpponentModelAdvisor** (Phase 8-3)
- **EndgameSolver** (Phase 8-4)

**主な処理フロー**:

1. `teampreview()`: 選出 + ゲームプラン策定 + **試合開始記録**
2. `choose_move()`: 行動選択 + **ターン記録**
3. 試合終了時: **結果記録**

### 3.2 GameSolver (探索エンジン)

**設定** (SolverConfig - 超高精度版):

| パラメータ | 値 | 説明 |
|---|---|---|
| `depth` | **8** | 8ターン先まで探索 |
| `n_samples` | **500** | 乱数サンプル500回 |
| `top_k_self` | **80** | 自分の候補80手 |
| `top_k_opp` | **80** | 相手の候補80手 |
| `tau` | 0.3 | 相手の合理性温度 |
| `tau_self` | 0.1 | 自分の合理性温度 |

**新機能** (Phase 7):
- **Transposition Table**: 同一局面のキャッシュ（`_transposition_table`）
- **clear_cache()**: ターン開始時にリセット

### 3.3 CandidateGenerator (候補生成)

**設定** (CandidateConfig):

| パラメータ | 値 | 説明 |
|---|---|---|
| `top_k` | 25 | 基本候補数 |
| `progressive_widening` | **True** | 動的候補数増加 |
| `base_k` | **15** | 初期候補数 |
| `widening_interval` | **5** | 5回ごとに増加 |
| `widening_step` | **5** | 増加量 |
| `max_k` | **100** | 最大候補数 |

**Progressive Widening 効果**:
```
call_count=1  → top_k=15
call_count=10 → top_k=25
call_count=20 → top_k=35
...
call_count=85 → top_k=100 (上限)
```

### 3.4 SmogonCalcWrapper (ダメージ計算)

**機能**:
- Node.js `@smogon/calc` をPythonから呼び出し
- **メモ化キャッシュ** (Phase 7 追加)

**キャッシュキー**:
```python
(attacker_name, nature, evs, item, ability, tera_type,
 defender_name, nature, evs, item, ability, tera_type,
 move_name, field_hash)
```

### 3.5 DeterminizedSolver (不完全情報対応)

**設定**:

| パラメータ | 以前 | 現在 | 説明 |
|---|---|---|---|
| `n_determinizations` | 3 | **10** | 仮説サンプル数 |

**動作**:
1. BeliefState から K=10 個の仮説をサンプル
2. 各仮説で GameSolver.solve() を実行
3. 結果を平均して最終決定

---

## 4. Phase 7: 探索最適化

### 4.1 Transposition Table

**目的**: 同一局面の再計算を回避

**実装箇所**: `predictor/core/game_solver.py`

```python
class GameSolver:
    def __init__(self):
        self._transposition_table: Dict[Tuple, float] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def _estimate_utility(self, battle, action_self, action_opp, ...):
        cache_key = (battle.turn, self_key, opp_key)
        if cache_key in self._transposition_table:
            return cached_value  # ヒット
        # 計算してキャッシュに保存
```

### 4.2 DamageCalc メモ化

**目的**: 同じ攻撃計算の再実行を回避

**実装箇所**: `predictor/engine/smogon_calc_wrapper.py`

**効果**: SmogonCalcWrapper インスタンス生存中、同一組み合わせはキャッシュから返却

### 4.3 Progressive Widening

**目的**: 探索回数に応じて候補数を動的に増加

**実装箇所**: `predictor/core/candidate_generator.py`

**効果**: 序盤は少ない候補で高速に、中盤以降は多くの候補で精度向上

---

## 5. Phase 3: 試合データベース

### 5.1 技術スタック

| 項目 | 選択 |
|---|---|
| DB | SQLite |
| ORM | SQLAlchemy 2.0.45 |
| ファイル | `data/battles.db` |

### 5.2 テーブル構成

```
battles (試合情報)
├── id: battle_tag
├── format: gen9vgc2026regfbo3
├── opponent_name
├── my_team_json / opp_team_json
├── game_plan_json
├── result: win/lose/tie
├── total_turns
└── final_my_remaining / final_opp_remaining

turns (ターン情報)
├── battle_id (FK)
├── turn_number
├── my_active_json / opp_active_json
├── predicted_win_prob
├── predicted_my_action_json / predicted_opp_action_json
├── risk_mode: secure/neutral/gamble
├── advisor_recommendation_json
├── actual_my_action_json / actual_opp_action_json
└── ko_happened, prediction_time_ms

pokemon_snapshots (ポケモン詳細)
├── turn_id (FK)
├── slot: my_0, opp_0, bench_0...
├── species, hp_current, hp_percent
├── status, item, ability
├── tera_type, tera_used
└── moves_json, stats_json
```

### 5.3 統合箇所 (run_predictor_trial.py)

| メソッド | 記録内容 |
|---|---|
| `__init__` | BattleRecorder 初期化 |
| `teampreview` | 試合開始（チーム、ゲームプラン） |
| `choose_move` | ターン開始（勝率予測、推奨行動） |

---

## 6. Phase 8: 次世代ロジック（論文ベース強化）

研究論文（VGC-Bench, PokéChamp, PokeLLMon）に基づく高度な機能。

### 6.1 StatParticleFilter（EV/実数値推定）

**目的**: OTS（テラ/持ち物/技は確定）でも非公開の EV/実数値 をオンライン推定

**ファイル**: `src/domain/services/stat_particle_filter.py`

**仕組み（粒子フィルター）**:

```
1. 初期化: 各相手ポケモンに K=30 個の「実数値仮説（粒子）」を生成
2. 観測:
   - 行動順 → 相手が先に動いた場合、Sが高い粒子の重みUP
   - 受けダメ → 予想より低ければ耐久が高い粒子の重みUP
   - 回復量 → HP実数が絞れる
3. リサンプル: 重みが偏りすぎたら再サンプリング
4. 出力: 平均実数値 or 分位点（悲観/楽観）
```

**使用例**:
```python
filter.observe_speed("Garchomp", my_speed=150, was_faster=True)
# → Sライン推定: 122〜169

mean_stats = filter.get_mean_stats("Garchomp")
# → {"hp": 192, "atk": 160, "def": 125, ...}
```

### 6.2 FictitiousPlay（ゲーム理論均衡）

**目的**: Quantal Response を「解きに行く」（均衡解に近づける）

**ファイル**: `predictor/core/fictitious_play.py`

**仕組み**:

```
1. Restricted Game（候補集合）を構築 ← 既存の top_k 候補
2. Fictitious Play を 5〜10 反復:
   - 相手分布に対する自分の最適応答を計算
   - 自分分布に対する相手の最適応答を計算
   - 分布を更新
3. 最終的な混合戦略を返す
```

**効果**:
- 囚人のジレンマ: 100% 裏切り（正解）に収束
- じゃんけん: [0.33, 0.33, 0.33]（均衡）に近づく

**関数**:
- `fictitious_play()`: 短時間反復で均衡戦略計算
- `double_oracle()`: 候補を動的に追加して効率化
- `blend_with_quantal()`: QRとブレンド

### 6.3 OpponentModelAdvisor（LLM相手モデル補正）

**目的**: LLM で相手の行動傾向を推定

**ファイル**: `predictor/core/opponent_model_advisor.py`

**出力**:
```python
OpponentPrior(
    protect_probability=0.25,   # 守る確率
    switch_probability=0.15,    # 交代確率
    aggressive_probability=0.50,# 攻撃確率
    style="defensive",          # aggressive / defensive / balanced
    tau_modifier=1.2,           # τ調整（高いほどランダム）
    reasoning="相手不利なので守備的になりやすい"
)
```

**使用**:
- OpponentModel の τ に `tau_modifier` を掛ける
- 相手の Protect 確率を考慮した候補評価

### 6.4 EndgameSolver（終盤読み切り）

**目的**: 残りポケモン少数時（≤3体）で詰み探索

**ファイル**: `predictor/core/endgame_solver.py`

**仕組み**:
```
1. 終盤判定: 両者合計 ≤ 6体 なら発動
2. 戦況分析:
   - 頭数比較スコア
   - HP合計比較スコア
3. 推奨戦略:
   - 有利 (>0.6): secure（安定行動）
   - 不利 (<0.4): gamble（上振れ狙い）
   - 互角: neutral
```

---

## 7. データフロー

### 6.1 試合開始時 (teampreview)

```
1. poke-env から Battle オブジェクト受信
2. GamePlanner でゲームプラン策定
3. 選出順序を決定
4. [NEW] BattleRecorder.start_battle() で記録開始
5. /team コマンド送信
```

### 6.2 ターン開始時 (choose_move)

```
1. BattleMemory に前ターン情報記録
2. BeliefState 更新（見えた技・持ち物から推定）
3. StyleUpdater で相手スタイル推定
4. TurnAdvisor 問い合わせ（LLM）
5. GameSolver で MCTS 探索
6. [NEW] BattleRecorder.record_turn_start() で予測記録
7. 最終行動決定
8. Showdown に送信
```

---

## 8. 判断ロジック

### 7.1 まもる判断

```
Q1: 守らずに攻撃を受けたら即死か？
    ├→ YES: 守る（バレバレでも守る）
    └→ NO: Q2へ

Q2: 相手のテラス攻撃をスカせる？
    ├→ YES: 守る価値あり
    └→ NO: 攻撃
```

**連続守り確率**:

| 回数 | 成功確率 | 条件 |
|---|---|---|
| 1回目 | 100% | なし |
| 2回目 | 33% | 勝率65%以上のみ |
| 3回目 | 11% | 強ペナルティ |

### 7.2 テラスタル判断

```
Q1: テラスなしで弱点技を受けたら即死か？
    ├→ YES: 迷わずテラス（生存優先）
    └→ NO: Q2へ

Q2: 今倒さないと返しで負けるか？
    ├→ YES: テラス（遂行優先）
    └→ NO: 温存
```

**火力補正**:

| 条件 | 倍率 |
|---|---|
| タイプ不一致テラス | 1.5倍 |
| **タイプ一致テラス** | **2.0倍** |

### 7.3 交代判断

```
Q1: 交代 vs 居座り、どちらが被ダメ少ない？
    └→ 交代の方が少ない: 交代候補

Q2: 交代後の対面は有利か？
    ├→ YES: 交代
    └→ NO: 居座り

Q3: 交代で相手の縛りを解除しないか？
    └→ 解除する: 居座り
```

---

## 9. ファイル構成

```
new_watch_game_system/
├── scripts/
│   └── run_predictor_trial.py          # メインエントリーポイント
│
├── predictor/
│   ├── core/
│   │   ├── game_solver.py              # MCTS + Transposition Table
│   │   ├── turn_advisor.py             # LLM戦略アドバイス
│   │   ├── determinized_solver.py      # 不完全情報対応 (K=10)
│   │   ├── candidate_generator.py      # Progressive Widening
│   │   ├── risk_aware_solver.py        # Secure/Gamble モード
│   │   └── tactical_mixer.py           # 戦術テンプレート
│   │
│   ├── damage/
│   │   ├── api.py                      # ダメージ計算API
│   │   └── ko_calc.py                  # KO確率計算
│   │
│   └── engine/
│       ├── smogon_calc_wrapper.py      # ダメ計 + メモ化キャッシュ
│       └── simulator_adapter.py        # 盤面シミュレータ
│
├── src/
│   ├── infrastructure/database/
│   │   ├── models.py                   # Battle, Turn, PokemonSnapshot
│   │   ├── session.py                  # DB接続
│   │   └── repository.py               # CRUD操作
│   │
│   ├── application/services/
│   │   └── battle_recorder.py          # 試合記録サービス
│   │
│   └── domain/services/
│       ├── battle_memory.py            # ターン間状態追跡
│       ├── belief_state.py             # 隠れ情報確率管理
│       └── player_style.py             # プレイスタイル推定
│
├── data/
│   └── battles.db                      # SQLite データベース
│
├── docs/                               # ドキュメント
├── CURRENT_STATUS.md                   # 現在のステータス
└── NEW_ARCHITECTURE_SPEC.md            # このファイル
```

---

## 10. 論文との整合

| 論文 | 概要 | 本システムでの対応 |
|---|---|---|
| **VGC-Bench** | VGC AI評価ベンチマーク | BeliefState, RiskAware, 評価指標設計 |
| **PokéChamp** | LLM + 探索 | TurnAdvisor + MCTS 統合 |
| **PokeLLMon** | Consistent Action | ConsistentTurnAdvisor 投票 |
| **Metamon** | Self-Play | Phase 4 で対応予定 |
| **ISMCTS** | 情報集合MCTS | DeterminizedSolver (K=10) |

### 実装済み手法

| 手法 | 出典 | ファイル |
|---|---|---|
| Determinization (K=10) | ISMCTS | `determinized_solver.py` |
| Quantal Response | ゲーム理論 | `game_solver.py` |
| Transposition Table | 伝統的探索 | `game_solver.py` |
| Progressive Widening | MAB/MCTS | `candidate_generator.py` |
| メモ化キャッシュ | 一般最適化 | `smogon_calc_wrapper.py` |

---

## 参考資料

- [CURRENT_STATUS.md](./CURRENT_STATUS.md) - 現在のステータス
- [docs/027_PAPER_ANALYSIS_AND_ROADMAP.md](./docs/027_PAPER_ANALYSIS_AND_ROADMAP.md) - 論文分析
- [memo.md](./memo.md) - まもる・テラスタルの戦略的判断基準
