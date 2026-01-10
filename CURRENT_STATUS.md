# VGC AI System - 現在のステータス

**最終更新**: 2025-12-31 17:55

---

## 📊 プロジェクト概要

VGCダブルバトル（ポケモン対戦）においてAIが最適な行動を選択するシステム。

### 主な機能

| 機能 | 説明 |
|---|---|
| **行動予測** | MCTS + Quantal Response による最適行動選択 |
| **勝率計算** | ゲーム理論に基づいた勝率予測 |
| **戦略アドバイス** | LLMによる戦略的判断サポート |
| **試合記録** | SQLiteに全試合データを蓄積 |

---

## 🚀 クイックスタート

```bash
# 1. 仮想環境を有効化
source .venv/bin/activate

# 2. Showdownサーバー起動（別ターミナル）
cd pokemon-showdown && node pokemon-showdown start

# 3. AI起動
PYTHONPATH=. python scripts/run_predictor_trial.py

# 4. 対戦を挑む
# Showdownで: /challenge VGCPred_XXXX gen9vgc2026regfbo3
```

---

## 📈 実装フェーズ

| Phase | 内容 | 状態 |
|---|---|---|
| 1 | 基盤整備（DamageCalc, BattleMemory, OpponentModel） | ✅ |
| 2 | 上位ロジック（BeliefState, RiskAwareSolver, TacticalMixer） | ✅ |
| 3 | 試合データベース（SQLite + BattleRecorder） | ✅ |
| 4 | Protect/テラス反映 | ✅ |
| 5 | 戦略的判断ロジック（リスク管理） | ✅ |
| 6 | シミュレーション強化（超高精度版） | ✅ |
| 7 | 探索最適化（Transposition Table, メモ化, Progressive Widening） | ✅ |
| 8 | 次世代ロジック（StatParticleFilter, FictitiousPlay, LLM補正, 終盤読み切り） | ✅ |

---

## 🆕 Phase 8: 次世代ロジック（論文ベース）

### 8-1. StatParticleFilter（EV/実数値推定）

**目的**: 相手のEV/実数値をオンラインで推定

**仕組み**:
1. 各相手ポケモンに K=30 個の「実数値仮説（粒子）」を初期化
2. 観測（行動順、ダメージ量）で粒子の重みを更新
3. 平均実数値 or 悲観/楽観（分位点）でダメ計に反映

**ファイル**: `src/domain/services/stat_particle_filter.py`

---

### 8-2. FictitiousPlay（ゲーム理論均衡）

**目的**: Quantal Response を均衡解に近づける

**仕組み**:
1. Restricted Game（候補集合）を構築
2. 5〜10 反復で互いの最適応答を更新
3. 最終混合戦略を返す

**ファイル**: `predictor/core/fictitious_play.py`

---

### 8-3. OpponentModelAdvisor（LLM相手モデル）

**目的**: LLM で相手の行動傾向を推定

**出力**:
- `protect_probability`: 守る確率
- `switch_probability`: 交代確率
- `tau_modifier`: τ調整（相手の読みやすさ）

**ファイル**: `predictor/core/opponent_model_advisor.py`

---

### 8-4. EndgameSolver（終盤読み切り）

**目的**: 残りポケモン ≤3体 で詰み探索

**仕組み**:
- 頭数/HP比較で有利不利を判定
- 有利時: secure（安定行動）
- 不利時: gamble（上振れ狙い）

**ファイル**: `predictor/core/endgame_solver.py`

## 🎯 現在の設定値

### SolverConfig（超高精度版）

| パラメータ | 値 | 説明 |
|---|---|---|
| `depth` | **8** | 8ターン先まで探索 |
| `n_samples` | **500** | 乱数サンプル500回 |
| `top_k_self` | **80** | 自分の候補80手 |
| `top_k_opp` | **80** | 相手の候補80手 |

### DeterminizedSolver

| パラメータ | 値 | 説明 |
|---|---|---|
| `n_determinizations` | **10** | 仮説サンプル数（論文推奨値） |

### CandidateGenerator（Progressive Widening）

| パラメータ | 値 | 説明 |
|---|---|---|
| `progressive_widening` | True | 動的候補数増加 |
| `base_k` | 15 | 初期候補数 |
| `widening_interval` | 5 | 5回ごとに増加 |
| `widening_step` | 5 | 増加量 |
| `max_k` | 100 | 最大候補数 |

---

## 🔄 探索最適化（Phase 7）

### Transposition Table

**目的**: 同一局面の再計算を回避

**実装**: `predictor/core/game_solver.py`

```python
# キー: (turn, self_action_key, opp_action_key)
# 値: utility (float)
self._transposition_table: Dict[Tuple, float] = {}
```

**効果**: 同じ行動ペアはキャッシュから返却、計算時間を削減

### DamageCalc メモ化

**目的**: 同じ攻撃計算の再実行を回避

**実装**: `predictor/engine/smogon_calc_wrapper.py`

```python
# キー: (attacker, defender, move, tera, field)
# 値: SmogonDamageResult
self._cache: Dict[tuple, SmogonDamageResult] = {}
```

### Progressive Widening

**目的**: 探索回数に応じて候補数を動的に増加

**実装**: `predictor/core/candidate_generator.py`

```python
# n回目の呼び出しで候補数 = base_k + (n // interval) * step
top_k = min(base_k + additional, max_k)
```

---

## 💾 試合データベース（Phase 3）

### テーブル構成

| テーブル | 内容 |
|---|---|
| `battles` | 試合情報、チーム、ゲームプラン、結果 |
| `turns` | ターンごとの予測・実際の動き |
| `pokemon_snapshots` | ポケモン詳細（HP、技、状態） |

### 記録タイミング

| メソッド | 記録内容 |
|---|---|
| `teampreview` | 試合開始（my_team, opp_team, game_plan） |
| `choose_move` | ターン開始（win_prob, risk_mode, advisor_recommendation） |

### データベースファイル

```
data/battles.db
```

### 技術スタック

- **DB**: SQLite
- **ORM**: SQLAlchemy 2.0.45

---

## ⚔️ シミュレーション仕様

### テラスタル火力補正

| 条件 | 倍率 |
|---|---|
| タイプ不一致テラス（元タイプ技） | 1.5倍 |
| タイプ不一致テラス（テラスタイプ技） | 1.5倍 |
| **タイプ一致テラス** | **2.0倍** |

### 2連守確率ペナルティ

| 連続回数 | 成功確率 | 条件 |
|---|---|---|
| 1回目 | 100% | なし |
| 2回目 | 33.3% | 勝率65%以上のみ |
| 3回目 | 11.1% | 強いペナルティ |

---

## 🧠 戦略的判断ロジック

### まもる判断

```
Q1: 守らずに攻撃を受けたら即死か？
    → YES: 守る（バレバレでも守る）
    → NO: Q2へ

Q2: 相手のテラス攻撃をスカせる？
    → YES: 守る価値あり
```

### テラスタル判断

```
Q1: テラスなしで弱点技を受けたら即死か？
    → YES: 迷わずテラス（生存優先）
    → NO: Q2へ

Q2: 今倒さないと返しで負けるか？
    → YES: テラス（遂行優先）
```

### 交代判断

```
Q1: 交代 vs 居座り、被ダメ比較
Q2: 交代後の対面は有利か
Q3: 縛り解除しないか
```

---

## 📦 主要コンポーネント

### 探索・意思決定

| ファイル | 役割 |
|---|---|
| `predictor/core/game_solver.py` | MCTS + Transposition Table |
| `predictor/core/determinized_solver.py` | 不完全情報対応 (K=10) |
| `predictor/core/candidate_generator.py` | 候補生成 + Progressive Widening |
| `predictor/core/risk_aware_solver.py` | Secure/Gamble モード |
| `predictor/core/turn_advisor.py` | LLMによる戦略アドバイス |

### 情報管理

| ファイル | 役割 |
|---|---|
| `src/domain/services/battle_memory.py` | ターン間の状態追跡 |
| `src/domain/services/belief_state.py` | 隠れ情報の確率管理 |
| `src/domain/services/player_style.py` | 相手のプレイスタイル推定 |

### データベース

| ファイル | 役割 |
|---|---|
| `src/infrastructure/database/models.py` | SQLAlchemy モデル |
| `src/infrastructure/database/repository.py` | CRUD操作 |
| `src/application/services/battle_recorder.py` | 試合記録サービス |

### ダメージ計算

| ファイル | 役割 |
|---|---|
| `predictor/engine/smogon_calc_wrapper.py` | ダメ計 + メモ化 |
| `predictor/damage/api.py` | ダメージ計算API |

---

## 📚 論文との整合

| 論文 | 対応機能 |
|---|---|
| VGC-Bench | BeliefState, RiskAware |
| PokéChamp | TurnAdvisor + MCTS |
| PokeLLMon | ConsistentTurnAdvisor |
| ISMCTS | DeterminizedSolver (K=10) |

---

## 🔧 環境変数

| 変数 | 必須 | 説明 |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | LLM機能に必要 |
| `PYTHONPATH` | ✅ | `.` を指定 |

---

## 📝 対戦ログ

```
docs/001_BATTLE_LOG_ANALYSIS_20251231_0425.md
docs/002_BATTLE_LOG_ANALYSIS_20251231_0521.md
docs/003_BATTLE_LOG_ANALYSIS_20251231_0603.md
```

---

## 🎯 次のステップ

| 優先度 | タスク | 状態 |
|---|---|---|
| 1 | 試合を実行してデータを蓄積 | 待機中 |
| 2 | 蓄積データで精度検証（予測 vs 実際） | 未着手 |
| 3 | Phase 4: Policy/Value Network の学習 | 未着手 |

---

## 🐛 既知の問題

| 問題 | 状態 | 対応 |
|---|---|---|
| TurnAdvisor max_hp エラー | ✅ 修正済み | getattr() で安全アクセス |
| Protect 推奨無視 | ✅ 修正済み | should_protect を反映 |
| テラス推奨無視 | ✅ 修正済み | should_tera を反映 |
