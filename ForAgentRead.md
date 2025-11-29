## ForAgentRead — 最終まとめ（エージェント向け）

このファイルは、プロジェクト「new_watch_game_system」の最終まとめと開発者（エージェント含む）向けの実行ガイドです。
主に日本語で記載しています。

---

## 概要

- プロジェクト名: new_watch_game_system
- 目的: Pokémon Showdown のリプレイ等のデータを用いて戦略モデル（HybridStrategist）を構築し、Fast-Lane（LightGBM）、Slow-Lane（重めの特徴ベース）、AlphaZero-Lane（Policy/Value ネットワーク + MCTS）を統合する。
- 現在: リプレイパース・BC データ生成・PyTorch による Policy/Value ネットワーク実装・LightGBM による Fast-Lane 実装・HybridStrategist の統合・統合テストを完了。

モデルや主要成果物の配置:

- 学習済みポリシーネットワーク: `models/policy_value_v1.pt`（プロジェクトルートまたは `models/`）
- Fast-Lane モデル: `models/fast_lane.pkl`
- トレーニングデータ・中間ファイル: `data/` 以下（例: `expert_trajectories.json`, `training_features.csv`）

---

## 🆕 最新サマリ（2025-11-19）

### 主要アップデート

- **AlphaZero-Lane（Phase 2-5）完了**: `docs/251119_week4_phase2-5_complete.md` に記載の通り、3545 サンプルで学習した `models/policy_value_v1.pt` を `predictor/player/alphazero_strategist.py`・`predictor/player/hybrid_strategist.py` に統合し、`tests/test_hybrid_strategist.py` で 3 レーン構成を検証。
- **React UI への完全移行**: Streamlit ベースの `frontend/streamlit_app.py` を廃止し、`frontend/web/` の React（Vite）クライアントをメイン UI として運用。Fast / Slow / AlphaZero の 3 レーン可視化に加えて、ヒーロー・ステップガイド・勝率スコアカードなど視覚的な誘導を実装し、Python は ML 推論 API のみで使用する。
- **Hybrid API ブリッジ**: `/evaluate-position` に `include_hybrid=true` を指定すると `hybridLanes` フィールドが返り、Fast-Lane/Slow-Lane/AlphaZero の勝率・推奨行動・実行時間が React UI のスコアボードと同期表示される。
- **データ／評価アーティファクト整理**: 高レート 508 件を含む 760 件のリプレイと 80 件の Smogon 統計を `data/replays/`・`data/smogon_stats/` に配置（詳細は `docs/251119_phase1_3_data_collection_report.md`）。AlphaZero の評価結果を `data/evaluation/`、Fast-Lane 特徴量を `data/training/`・`data/training_features.csv` に保存し、`scripts/evaluate_alphazero.py`・`scripts/quick_test_model.py` で再現できる状態。

### テスト / 実行状況

- `pytest tests/test_hybrid_strategist.py -v` を想定テストコマンドとして継続運用（`pytest-asyncio` 必須）。`CURRENT_STATUS.md` 時点でローカル実行済み。
- フロントエンドは `frontend/web/`（React/Vite）で提供し、`npm install && npm run dev` で起動。環境変数 `VITE_PREDICTOR_URL` を設定し、Python サイドの推論 API と通信する。バックエンドを `uvicorn predictor.api.server:app --reload` で起動し、`include_hybrid=true` で 3 レーンが描画される。

### 未解決の課題 / 次アクション

1. React 側で `convert_sample_to_battle_state()`（utility 化予定）に slot/HP ベースの disambiguation を実装。
2. AlphaZero 推論 API を非同期化し、長時間 rollouts の進捗表示を React UI に追加。
3. `ActionCandidate` に target 等のメタ情報を拡充し、推奨行動の説明力を高める。
4. React/Next.js CI（Lint/Build）と Docker/Vercel デプロイ手順を docs に追記。

### 参考ドキュメント

- `CURRENT_STATUS.md` – 直近スナップショット（テスト状況 / TODO）。
- `docs/251119_week4_phase2-5_complete.md` – AlphaZero 統合レポート。
- `docs/251119_phase1_3_data_collection_report.md` – Phase 1.3 データ収集まとめ。
- `docs/PBS-AI_Ultimate_Master_Plan.md` – 全体計画と進捗バー。

---

## 重要ファイル構成（抜粋）

- `predictor/player/` : 各種ストラテジスト（`alphazero_strategist.py`, `hybrid_strategist.py`, `policy_value_network_pytorch.py`）
- `scripts/` : データ生成・特徴抽出・学習スクリプト（`parse_replay_to_training_data.py`, `extract_features.py`, `train_fast_lane.py`など）
- `frontend/web/` : React（Vite/Next.js）ベースの UI。Python 推論 API と HTTP 経由で連携。
- `tests/` : 単体・統合テスト（`test_hybrid_strategist.py` など）
- `docs/` : 設計や統合手順のドキュメント

---

## 開発環境セットアップ（ローカル・macOS / zsh 想定）

1. Python 仮想環境の作成（推奨: `.venv`）

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

2. 必要パッケージのインストール

（requirements.txt がある場合）

```bash
pip install -r requirements.txt
```

主要に使用するパッケージ:

- torch（PyTorch）
- lightgbm
- pytest, pytest-asyncio
- React / Next.js / Vite（フロントエンド）

3. テスト実行

```bash
pytest tests/test_hybrid_strategist.py -v
```

テストは `pytest-asyncio` を使っているため、プラグインが必要です（インストール済みであることを確認）。

---

## 主要な実行手順（開発時）

- React UI を起動してハイブリッド戦略を可視化:

```bash
cd frontend/web
npm install
VITE_PREDICTOR_URL=http://localhost:8000/evaluate-position npm run dev
```

- 迅速なモデル確認:

```bash
python scripts/quick_test_model.py
```

---

## モデル学習・再現（簡易メモ）

1. リプレイ -> 転移データ生成

```bash
python scripts/parse_replay_to_training_data.py --input data/showdown --output data/expert_trajectories.json
```

2. 特徴抽出（Fast-Lane 用）

```bash
python scripts/extract_features.py --input data/expert_trajectories.json --output data/training_features.csv
```

3. Fast-Lane 学習

```bash
python scripts/train_fast_lane.py --input data/training_features.csv --output models/fast_lane.pkl
```

4. Policy/Value ネットワーク学習（PyTorch）

```bash
python predictor/player/policy_value_network_pytorch.py --train --data data/bc_training_data.pt --out models/policy_value_v1.pt
```

（各スクリプトは実行時のオプション名に依存するため、ヘルプ `--help` を確認してください）

---

## テストと品質ゲート

- 変更を加えたらまず `pytest` を走らせること。
- 非同期テストがあるため `pytest-asyncio` を必ず入れてください。
- 重要なテスト: `tests/test_hybrid_strategist.py`（Fast/Slow/AlphaZero の統合動作を確認）

---

## フロントエンド UI（React）

- 現状: `frontend/web/` に React ベースの UI を集約。Vite Dev Server で動作し、Fast / Slow / AlphaZero の 3 レーン表示と rollouts 調整 UI を提供。
- `/evaluate-position` に `include_hybrid=true` を付与して呼び出すと `hybridLanes` が返り、UI のスコアボードで Fast-Lane / Slow-Lane / AlphaZero の勝率・信頼度・推奨行動・推論時間を視覚化できる。
- 次の作業（優先）: Next.js への移行（SSR/SSG や API Routes の活用）、AlphaZero 非同期表示、ActionCandidate メタ情報拡充、UI/UX 改善。

---

## 本番デプロイの注意点

- モデルファイル（特に `policy_value_v1.pt`）はサイズが大きくなる可能性があるため、別ストレージ（S3 等）に置き、起動時に取得するのが望ましい。
- 推論環境では GPU/MPS の有無で挙動が変わるため、デグレ検出のための簡易ベンチ（`scripts/quick_test_model.py` 等）を CI に組み込むこと。

---

## 既知の課題 / リスク

- Self-Play によるデータ増強は未完了（現状はエキスパートデータ中心）。
- AlphaZero の MCTS は計算負荷が高く、レイテンシ要件次第では Fast/Slow の補助的利用が必須。
- Streamlit の UI はデプロイ時に認証やリソース制限を考慮する必要あり。

---

## 今後の推奨ステップ（短期）

1. React/Next.js UI の機能拡張（AlphaZero レーン非同期化、ActionCandidate 説明強化）
2. Self-Play 用ジョブを小規模で起動してデータを収集
3. CI に `pytest` と `scripts/quick_test_model.py`、およびフロントエンド Lint/Build を組み込み（モデルロード検証）

---

## 連絡先・参照

- 開発者: kawashimawataru（リポジトリ所有者）
- 主要ドキュメント: `docs/` 下の各ファイル（`showdown_integration_plan.md` など）

---

最終更新: 2025-11-19

# For Agent Read: プロジェクト概要と作業ガイドライン

**最終更新**: 2025 年 11 月 19 日  
**プロジェクト名**: PBS-AI (Pokémon Battle Spectator AI)  
**目的**: VGC バトルの勝率予測とリアルタイム実況 AI の開発

---

## 📁 このフォルダについて

### プロジェクト構造

```
new_watch_game_system/
├── predictor/              # AIコアロジック（4層アーキテクチャ）
│   ├── core/              # Detective Engine, Position Evaluator
│   ├── engine/            # Damage Calculator, Smogon Calc Wrapper
│   ├── data/              # Data Loaders (Showdown, Smogon)
│   └── player/            # AI Player実装
├── frontend/              # UIと入出力
│   ├── battle_ai_player.py  # CLI/操作系
│   └── web/              # React/Next.js フロントエンド
├── smogon-calc-bridge/    # Node.js ↔ Python ブリッジ
├── pokemon-showdown/      # Showdownサーバー (localhost:8000)
├── data/                  # データストレージ
│   ├── smogon_stats/     # Smogon統計データ (JSON)
│   ├── replays/          # ダウンロードしたリプレイ
│   └── showdown/         # Showdown静的データ (pokedex, moves, etc)
├── scripts/               # ユーティリティスクリプト
├── tests/                 # テストコード
└── docs/                  # ドキュメント（最重要！）
    ├── PBS-AI_Ultimate_Master_Plan.md  # 📜 プロジェクトの憲法
    └── phase1_2_smogon_calc_integration.md  # フェーズ完了報告
```

---

## 🎯 プロジェクトの計画

### アーキテクチャ: "The 4-Layer Brain"

| Layer  | 名前                | 役割                                      | 状態    |
| ------ | ------------------- | ----------------------------------------- | ------- |
| **L1** | 🕵️ Detective Engine | EV 推定（ベイズ推論）                     | ✅ 100% |
| **L2** | ⚙️ Simulator        | ダメージ計算 (@smogon/calc)               | ✅ 100% |
| **L3** | 🧠 Strategist       | **勝率予測 (MCTS + Expert System)** 🔥NEW | 🔨 35%  |
| **L4** | 🎙️ Narrator         | LLM 実況生成                              | ⏳ 0%   |

### 開発フェーズ

```
Phase 0: Infrastructure       ████████████████████ 100% ✅
Phase 1: Logic Core           ██████████████░░░░░░  70% 🔄
  ├─ 1.1 Detective Engine     ████████████████████ 100% ✅
  ├─ 1.2 Simulator            ████████████████████ 100% ✅
  ├─ 1.3 Strategist           █████████████████░░░  85% �
  └─ 1.4 Excitement Detector  ████████████████░░░░  80% 🔄
Phase 2: Visualization        ████████████████░░░░  80% 🔄
Phase 3: Soul Integration     ██░░░░░░░░░░░░░░░░░░  10% ⏳
```

**現在地**: Phase 1.3 Fast-Lane 完了 (85%) → **次: P1-3-C (統合パイプライン)** 🔄 Week 3

---

## 📝 作業終わり時の報告フォーマット

**必ず以下の形式で報告すること！**

### ✅ 完了した作業

````markdown
## ✅ [フェーズ番号] [タスク名] 完了

### 📦 実装内容

- [実装したファイル 1] - [説明]
- [実装したファイル 2] - [説明]

### 🎯 検証結果

- [テストケース 1]: ✅ 成功 / ❌ 失敗
- [主要な発見や問題点]

### 📊 進捗状況（必須！）

\```
Phase 0: Infrastructure ████████████████████ 100% ✅
Phase 1: Logic Core ████████░░░░░░░░░░░░ XX% 🔄
├─ 1.1 Detective Engine ████████████████████ 100% ✅
├─ 1.2 Simulator ████████████████████ 100% ✅
├─ 1.3 Strategist ░░░░░░░░░░░░░░░░░░░░ 0% ⏳
└─ 1.4 Excitement Detector ░░░░░░░░░░░░░░░░░░░░ 0% ⏳
Phase 2: Visualization ████████████████░░░░ 80% 🔄
\```

### 🚀 次のステップ（必須！）

1. [次にやるべきこと 1]
2. [次にやるべきこと 2]
3. [次のフェーズへの移行条件]
````

---

## 🔑 重要な決定事項

### ✅ 採用した技術

1. **@smogon/calc** (2025/11/19 採用)

   - 理由: Pokémon Showdown 公式、100%正確
   - 場所: `smogon-calc-bridge/`, `predictor/engine/smogon_calc_wrapper.py`
   - 既存の `damage_calculator.py` は非推奨（30%誤差）

2. **Smogon Chaos JSON** (1760+レート)

   - 使用率統計 → EV 分布の事前確率
   - 場所: `data/smogon_stats/gen9vgc2024regh-1760.json`

3. **poke-env** + Showdown サーバー
   - ローカルでバトルシミュレーション
   - サーバー起動: `cd pokemon-showdown && node pokemon-showdown start`

### ❌ 非推奨・廃止

1. **predictor/engine/damage_calculator.py**

   - 理由: Multiscale 未実装、計算誤差 30%以上
   - 代替: `smogon_calc_wrapper.py` を使用

2. **Phase 1.3 当初のディープラーニング計画** ❌ 廃止 (2025/11/19)
   - 理由: データ不足 (N=760 < 10,000 件) で NN 学習は困難
   - 代替: **MCTS + Expert System のハイブリッド戦略** 🔥NEW

---

## 🔥 Phase 1.3 新戦略: MCTS 中心アプローチ (2025/11/19 決定)

### 🎯 戦略変更の理由

- **データ不足**: 760 件のリプレイではディープラーニングに不十分
- **計算で補う**: MCTS は**データ 0 件**で動作可能
- **リアルタイム性**: Fast-Lane (10ms) + Slow-Lane (数秒) の 2 層構造

### 🏗️ 新アーキテクチャ: "Fast + Slow Dual System"

| レイヤー      | 名称              | 実装                        | 応答時間   | 精度     | データ依存         |
| :------------ | :---------------- | :-------------------------- | :--------- | :------- | :----------------- |
| **Fast-Lane** | **Expert System** | LightGBM/ロジスティック回帰 | **10ms**   | 中       | 760 件で訓練 ✅    |
| **Slow-Lane** | **Monte Carlo**   | MCTS (1000 rollouts)        | **2-5 秒** | **最高** | **0 件 (不要)** ✅ |
| **Narrator**  | **LLM 解説**      | GPT-4 / Claude              | 1-2 秒     | -        | -                  |

### 📋 Phase 1.3 新タスク構成

| タスク ID  | 名称                 | 実装内容                                  | 優先度          | 状態  |
| :--------- | :------------------- | :---------------------------------------- | :-------------- | :---- |
| **P1-3-A** | **Fast-Lane 実装**   | 特徴量抽出 + LightGBM 訓練 (即時勝率推定) | HIGH            | ⏳ 0% |
| **P1-3-B** | **Slow-Lane 実装**   | MCTS Engine (`MonteCarloStrategist`)      | **CRITICAL** 🔥 | ⏳ 0% |
| **P1-3-C** | **統合パイプライン** | Fast→Slow→LLM の 3 層処理                 | HIGH            | ⏳ 0% |
| **P1-3-D** | **UI 統合**          | リアルタイム勝率表示 + 最適手ハイライト   | MEDIUM          | ⏳ 0% |

### 🚀 実装スケジュール (3 週間計画)

```
Week 1: MCTS Engine実装 (P1-3-B) 🔥最優先
├─ Day 1-2: MonteCarloStrategist基本実装
│   └─ predictor/player/monte_carlo_strategist.py
├─ Day 3-4: Rolloutパフォーマンス最適化
└─ Day 5: テスト & デバッグ

Week 2: Fast-Lane実装 (P1-3-A)
├─ Day 1-2: 特徴量エンジニアリング (760件使用)
│   └─ predictor/player/feature_extractor.py
├─ Day 3-4: LightGBM訓練 & 評価
│   └─ predictor/player/fast_strategist.py
└─ Day 5: 10ms以内レスポンス検証

Week 3: 統合 & UI (P1-3-C/D)
├─ Day 1-2: Fast/Slow並列処理パイプライン
├─ Day 3-4: フロントエンド統合
└─ Day 5: エンドツーエンドテスト
```

### 🎓 技術詳細: MCTS Engine

**基本アルゴリズム**:

```python
def monte_carlo_search(state, n_rollouts=1000):
    """
    現在の盤面からn_rollouts回ランダムプレイアウトを実行
    最も勝率の高い行動を返す
    """
    for action in legal_actions:
        win_count = 0
        for _ in range(n_rollouts // len(legal_actions)):
            # Layer 2 Simulator でバトルを最後まで実行
            result = simulate_battle(state, action)
            if result == "win":
                win_count += 1
        win_rates[action] = win_count / n_rollouts

    return max(win_rates, key=win_rates.get)
```

**評価関数**: 既存の `PositionEvaluator` を活用
**シミュレーション**: `poke-env` + Showdown サーバー

---

## 📚 重要ドキュメント（必読）

### 最重要

- **`docs/PBS-AI_Ultimate_Master_Plan.md`** - プロジェクトの憲法

  - 全フェーズの詳細計画
  - 進捗トラッキング
  - 技術選定の記録

- **`docs/P1_technical_spec_verification.md`** - Phase 1 技術仕様・検証レポート 🔥NEW
  - P1 全体の実装完成度 (55%)
  - 各コンポーネントの対応表
  - P1-3-B (MCTS) 実装仕様
  - Week 1-3 の詳細アクションプラン

### フェーズ完了報告

- `docs/phase1_2_smogon_calc_integration.md` - Phase 1.2 完了報告

### README

- `smogon-calc-bridge/README.md` - @smogon/calc の使い方
- `docs/startup_guide.md` - プロジェクトセットアップ手順

---

## 🛠️ 開発ワークフロー

### 1. タスク開始前

```bash
# 1. マスタープランを確認
cat docs/PBS-AI_Ultimate_Master_Plan.md

# 2. 現在のフェーズを確認
grep -A 10 "Phase 1:" docs/PBS-AI_Ultimate_Master_Plan.md

# 3. TODOリストを確認
# VS Code の TODO パネルを開く
```

### 2. 実装中

```python
# 必ずテストを書く
# 必ずドキュメントを書く
# 既存コードを壊さない
```

### 3. タスク完了時（必須！）

#### A. 進捗バーを更新

`docs/PBS-AI_Ultimate_Master_Plan.md` の進捗バーを更新

#### B. 完了報告を作成

```markdown
## ✅ Phase X.Y: [タスク名] 完了

### 📊 進捗状況

[進捗バーをコピペ]

### 🚀 次のステップ

1. [次のタスク]
2. [その次のタスク]
```

#### C. ユーザーに報告

- 何を実装したか
- どう検証したか
- 次に何をするか

**報告例**:

```
✅ Phase 1.2完了: @smogon/calc統合

📦 実装内容:
- smogon-calc-bridge/calc_server.js
- predictor/engine/smogon_calc_wrapper.py

🎯 検証結果:
- Gholdengo vs Dragonite: 85-101ダメージ ✅
- 既存実装との差分: 30% (Multiscale未実装が原因)

📊 進捗: Phase 1は40%完了

🚀 次: Detective Engineにダメージ判定機能追加
```

---

## 📊 最新データ収集状況 (2025/11/19 更新)

### Smogon 統計データ ✅

- **保存先**: `data/smogon_stats/`
- **期間**: 2025 年 5 月～ 10 月 (6 ヶ月分)
- **合計**: 80 ファイル
- **レギュレーション**: Gen9 VGC (Reg C, D, G, H, I, J)
- **レート帯**: 0, 1500, 1630, 1760

### VGC リプレイデータ ✅

- **保存先**: `data/replays/`
- **高レート帯 (1500+)**: 508 件 🎯
  - `vgc_high_rating_1500plus_20251119_031953.json` (204 件)
  - `vgc_high_rating_1500plus_20251119_033735.json` (304 件)
  - レート分布: 1500-1600 (495 件), 1600-1700 (16 件), 1700-1800 (1 件)
- **全レート帯**: 252 件
  - `vgc_replays_20251119_030759.json` (99 件)
  - `vgc_replays_20251119_030922.json` (99 件)
  - `vgc_replays_20251119_030956.json` (149 件)
- **合計**: 760 件のリプレイ

### データ収集スクリプト

- **Smogon 統計**: `scripts/fetch_smogon_stats.py`
- **VGC リプレイ (汎用)**: `scripts/download_vgc_replays.py`
- **高レート特化**: `scripts/download_high_rating_replays.py` ⭐ 新規

詳細レポート: `docs/251119_phase1_3_data_collection_report.md`

---

## ⚠️ 注意事項

### DO

✅ マスタープランを常に参照する  
✅ 進捗バーを必ず更新する  
✅ 完了報告を必ず書く  
✅ テストを書く  
✅ 既存コードとの互換性を保つ

### DON'T

❌ マスタープランを無視しない  
❌ 進捗報告を忘れない  
❌ ドキュメントを書かずにコードだけ書かない  
❌ 既存の動作するコードを壊さない  
❌ "とりあえず動く"で満足しない

---

## 🔗 クイックリンク

- **マスタープラン**: `docs/PBS-AI_Ultimate_Master_Plan.md`
- **現在のタスク**: TODO リスト参照
- **React UI 起動**: `cd frontend/web && npm run dev`
- **Showdown 起動**: `cd pokemon-showdown && node pokemon-showdown start`
- **テスト実行**: `pytest tests/`

---

## 📞 困ったときは

1. `docs/PBS-AI_Ultimate_Master_Plan.md` を読む
2. 関連する `docs/phase*` ドキュメントを読む
3. `smogon-calc-bridge/README.md` 等の README を読む
4. ユーザーに質問する

---

**Remember**: このプロジェクトは「VGC 観戦体験を革新する」ことが目的です。  
全ての実装は、この目的に向かって進んでいます。

**Good luck, Agent! 🚀**
