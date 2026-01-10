# 📘 Project PBS-AI Ultimate: "The AI Caster" 統合開発計画書

**Version:** 3.0  
**Date:** 2025 年 11 月 19 日  
**Status:** Active Development

---

## 🌟 1. プロジェクト・ビジョン

**"Ignite the Heat" (熱狂を言語化せよ)**

- **Mission:** ポケモン VGC（ダブルバトル）の高度な読み合いを可視化・言語化し、初心者でもプロと同じ興奮を味わえる観戦体験を作る。
- **Core Value:** 単なる勝率表示（PBS）を超え、**「なぜその一手が凄いのか？」** を AI が解説するストーリーテリング・システム。

---

## 🏗 2. システムアーキテクチャ (The 4-Layer Brain)

「正確な計算」と「豊かな表現」を両立させるため、役割の異なる 4 つのエンジンを直列に接続します。

| Layer  | 名称                         | 役割                                                                                                 | 技術スタック                                     | データソース                           |
| :----- | :--------------------------- | :--------------------------------------------------------------------------------------------------- | :----------------------------------------------- | :------------------------------------- |
| **L1** | **Detective**<br>(名探偵)    | **「見えないステータスを暴く」**<br>行動順やダメージから、相手の努力値(EV)・性格・持ち物を特定する。 | **ベイズ推定**<br>(Python 独自実装)              | **Smogon Stats**<br>(Chaos JSON)       |
| **L2** | **Simulator**<br>(物理演算)  | **「確定数を算出する」**<br>L1 で特定したステータスを元に、次の攻撃のダメージ％を計算する。          | **Damage Calc**<br>(@smogon/calc)                | **Showdown Data**<br>(Pokedex/Moves)   |
| **L3** | **Strategist**<br>(戦術参謀) | **「勝率と最適手を読む」**<br>現在の盤面から勝率を予測し、プロが選ぶであろう手を提示する。           | **MCTS + ML Hybrid**<br>(Monte Carlo + LightGBM) | **Smogon Replays**<br>(High Rate Logs) |
| **L4** | **Narrator**<br>(実況解説)   | **「文脈を語る」**<br>L1〜L3 の数値を元に、「今の『まもる』がなぜ天才的か」を言語化する。            | **LLM**<br>(Gemini 1.5 / GPT-4o)                 | **L1~L3 の出力結果**                   |

---

## 🧱 3. 詳細フェーズ計画 (Scope & Phasing)

### 📍 Phase 0: Infrastructure (基盤構築) ✅

**目標:** データが流れる水道管を作る。

- **0.1 ローカルサーバー環境:** ✅

  - Node.js 版 `pokemon-showdown` を Localhost:8000 で稼働。
  - フォーマット: **`gen9vgc2024regh` (Regulation H)**。

- **0.2 Python 観戦 Bot (Listener):** ✅
  - Lib: `poke-env`
  - 機能: 観戦者として入室し、対戦ログをリアルタイムで取得する。
  - **【重要】VGC 特化パーサー:** シングルとは異なる「2 体同時選出」「守る/ワイガ」「集中攻撃」のログを正しく構造化データ（Class）に変換する処理の実装。
  - **実装状況:** `scripts/phase1_test_connection.py` で動作確認済み。

### 📍 Phase 1: Logic Core MVP (論理エンジンの実装) 🔄

**目標:** AI が「嘘をつかない数値」を出せるようにする。**※最重要・最大工数**

- **1.1 Detective Engine (配分予測):** 🚧 Next

  - **Input:** `Smogon Chaos JSON` (統計データ)。
  - **Prior (事前確率):** 「ハバタクカミの 72%は C ブースト」という初期値をロード。
  - **Update (事後確率):**
    - 「S 判定」: 相手より先に動いた → S 実数値の最低ライン確定。
    - 「被ダメ判定」: A187 ゴリランダーの GF グラスラを耐えた → B 耐久指数の下限確定。
  - **Output:** 推定 EV 分布リスト。
  - **実装ファイル:** `predictor/core/detective_engine.py` (未作成)

- **1.2 Simulator Integration:** ✅ **完了 (2025/11/19)**

  - **実装:** @smogon/calc v0.10.0 を統合。Python → Node.js ブリッジ経由で呼び出し。
  - **機能:** L1 の推定 EV を入力し、「確定 1 発」「乱数 30%」を返す API 作成。
  - **精度:** Pokémon Showdown 公式実装のため計算 100%正確。Multiscale、テラスタル等すべて対応。
  - **実装ファイル:**
    - `smogon-calc-bridge/calc_server.js` - Node.js ブリッジサーバー
    - `predictor/engine/smogon_calc_wrapper.py` - Python ラッパー
  - **非推奨化:** 独自実装の `predictor/engine/damage_calculator.py` は精度問題により非推奨。
  - **詳細:** `docs/phase1_2_smogon_calc_integration.md` 参照

- **1.3 Strategist (Win Rate Model):** 🔄 **戦略変更 (2025/11/19)** 🔥

  - **❌ 旧計画 (廃止):** Neural Network でディープラーニング

    - 理由: データ不足 (N=760 < 10,000) で精度不足

  - **✅ 新戦略: MCTS + Expert System ハイブリッド** 🔥

    - **Fast-Lane (P1-3-A):** LightGBM/ロジスティック回帰 (10ms 即時応答)
      - データ: 760 件のリプレイで訓練可能 ✅
      - 目的: ターン開始時に瞬時に勝率を UI 表示
    - **Slow-Lane (P1-3-B):** Monte Carlo Tree Search (2-5 秒精密計算) 🔥 最優先
      - データ: **0 件で動作可能** (シミュレーションベース) ✅
      - 目的: 1000 rollouts で最適手と確定勝率を算出
      - 評価関数: 既存の `PositionEvaluator` を活用
    - **統合 (P1-3-C):** Fast→Slow→LLM の 3 層パイプライン
    - **UI (P1-3-D):** リアルタイム勝率表示 + 最適手ハイライト

  - **データ収集完了:** ✅ (2025/11/19)

    - Smogon Stats: 80 ファイル (6 ヶ月分、Reg C/D/G/H/I/J)
    - 高レートリプレイ: 508 件 (1500+)
    - 汎用リプレイ: 252 件
    - 合計: **760 件** (`data/replays/`, `data/smogon_stats/`)
    - 詳細: `docs/251119_phase1_3_data_collection_report.md`

  - **次のステップ:**
    1. **P1-3-B 実装 (Week 1):** `predictor/player/monte_carlo_strategist.py` 作成 🔥
    2. P1-3-A 実装 (Week 2): 特徴量抽出 + LightGBM 訓練
    3. P1-3-C/D 統合 (Week 3): パイプライン構築 + UI 統合

- **1.4 Excitement Detector (盛り上がり判定):** ⏳

  - ロジック: `abs(前ターンの勝率 - 今ターンの勝率) >= 15%` を検知フラグとする。
  - **実装場所:** Strategist 内部または Visualization 層で実装予定。

### 📍 Phase 2: Visualization (可視化 UI) ✅

**目標:** Figma のデザインを具現化する。

- **Tech:** `Streamlit` (プロトタイプ) → `React/Next.js` (最終版)。
- **Layout:**

  - **Main:** リアルタイム勝率バー（推移グラフ付き）。✅
  - **Overlay:** ポケモンの横に「推定ステータス（AS, HB 等）」のバッジ表示。⏳
  - **Action:** 技ごとのダメージ予測％と、推奨行動のハイライト。✅

- **実装状況:**
  - `frontend/streamlit_app.py` で MVP 完成 ✅
  - アクセス: http://localhost:8501
  - 機能: 勝率ゲージ、ターン推移グラフ、推奨行動表示、盤面状態表示、CRITICAL TURN 検知

### 📍 Phase 3: The "Soul" Integration (LLM & 演出) ⏳

**目標:** システムに魂（実況）を吹き込む。

- **3.1 Prompt Engineering:**

  - LLM への入力: 「勝率 60%→80%に上昇」「要因：相手のトリル読み守る成功」「相手はこだわりメガネ持ち」
  - LLM への指示: 「上記の状況を、熱血実況アナウンサーの口調で 30 文字以内で叫べ」

- **3.2 Visual FX:**
  - 重要ターン（Excitement Flag が True）の際、画面枠を赤く発光させたり、"CRITICAL TURN" のカットインを入れる。
  - **Streamlit MVP:** 基本的な CRITICAL TURN バッジ実装済み ✅

---

## 🛠 4. データ・リソース指定 (Specifics)

開発に必要な「現物」のリストです。

### A. データセット (Source of Truth)

1. **Usage Stats (推論の根拠):**

   - Source: `https://www.smogon.com/stats/`
   - File: `[最新年月]/chaos/gen9vgc2024regh-1760.json` (高レート帯の Chaos データ必須)
   - **Status:** 未取得 ⏳

2. **Replays (学習の教科書):**
   - Source: `https://replay.pokemonshowdown.com/?format=gen9vgc2024regh`
   - Method: `.json` を付加して生ログを DL。
   - **Status:** 10 件テスト済み ✅、大量収集は未実施 ⏳
   - **保存先:** `data/replays/`

### B. ライブラリ (Library)

1. **Core:** `poke-env` (Python) - Showdown 通信用 ✅
2. **Calc:** `radon-h/pokemon-showdown-engine` (Python) または `@smogon/calc` (Node) ⏳
3. **ML:** `PyTorch` (Python) - 勝率予測モデル ⏳
4. **LLM API:** `Gemini API` or `OpenAI API` ⏳

**インストール済みパッケージ:**

```bash
poke-env
streamlit
plotly
pandas
requests
beautifulsoup4
aiohttp
lxml
```

---

## 📅 5. 開発フローと Next Action

この計画書に基づき、以下の順序で実装します。

### 完了済み ✅

1. **Phase 0.1:** ローカル Showdown サーバー構築
2. **Phase 0.2:** Python 観戦 Bot（poke-env 接続テスト）
3. **Phase 2 MVP:** Streamlit 可視化 UI
4. **Phase 1.3 準備:** リプレイダウンローダー（10 件テスト）

### 現在進行中 🔄

**[Now] Phase 1.1: Detective Engine (名探偵) の開発**

- **理由:** これが全ての基礎データになるため。
- **最初のステップ:**
  1. Smogon Chaos JSON をダウンロード
  2. データ読み込みスクリプト作成
  3. 「ハバタクカミ」の確率分布を出力するテストプログラム

### 次のマイルストーン 🎯

1. **Detective Engine コア実装** (Phase 1.1)
2. **大量リプレイ収集** (Phase 1.3 データ準備)
3. **Simulator 統合** (Phase 1.2)
4. **勝率予測モデル学習** (Phase 1.3)
5. **LLM 実況解説統合** (Phase 3.1)

---

## 📊 進捗状況サマリー

```
Phase 0: Infrastructure       ████████████████████ 100% ✅
Phase 1: Logic Core           ███████████░░░░░░░░░  55% 🔄
  ├─ 1.1 Detective Engine     ████████████████████ 100% ✅
  ├─ 1.2 Simulator            ████████████████████ 100% ✅
  ├─ 1.3 Strategist           ███████░░░░░░░░░░░░░  35% 🔨 (Data: 760件 ✅, MCTS実装中)
  └─ 1.4 Excitement Detector  ░░░░░░░░░░░░░░░░░░░░   0% ⏳
Phase 2: Visualization        ████████████████░░░░  80% 🔄
Phase 3: Soul Integration     ██░░░░░░░░░░░░░░░░░░  10% ⏳
```

---

## 🔗 重要なファイルパス

### スクリプト

- `scripts/phase1_test_connection.py` - poke-env 接続テスト ✅
- `scripts/phase2_download_replays.py` - リプレイダウンローダー ✅
- `scripts/fetch_showdown_data.py` - Showdown データ同期
- `scripts/verify_showdown_data.py` - データ検証

### コア実装

- `predictor/core/position_evaluator.py` - メインエントリーポイント
- `predictor/core/eval_algorithms/heuristic_eval.py` - ヒューリスティック評価 ✅
- `predictor/core/detective_engine.py` - EV 推定エンジン（未作成）🚧
- `predictor/engine/damage_calculator.py` - ダメージ計算
- `predictor/engine/state_rebuilder.py` - 盤面再構築

### UI

- `frontend/streamlit_app.py` - Streamlit MVP ✅
- `frontend/web/` - React UI（既存）

### データ

- `data/showdown/` - ポケモン/技/道具データ
- `data/replays/` - ダウンロード済みリプレイ
- `data/ev_priors.json` - EV 事前分布（要作成）

---

## 📝 開発ガイドライン

### コーディング規約

- Python: PEP 8 準拠
- Type Hints 必須（`from typing import ...`）
- Docstring: Google Style

### テスト

- 各モジュールに対応するテストを `tests/` に配置
- `pytest` で実行
- 重要な関数は必ずユニットテスト追加

### コミット規約

- feat: 新機能
- fix: バグ修正
- docs: ドキュメント更新
- refactor: リファクタリング
- test: テスト追加/修正

---

## 🎯 成功の定義

このプロジェクトは以下の条件を満たした時、成功とみなす：

1. **精度:** EV 推定の正解率 > 70%
2. **速度:** 1 ターンの評価時間 < 500ms
3. **勝率:** AI の勝率予測精度 > 75%
4. **体験:** 初心者テスターが「プロの試合が面白くなった」と評価

---

## 📚 参考リンク

- [Pokemon Showdown Server](https://github.com/smogon/pokemon-showdown)
- [poke-env Documentation](https://poke-env.readthedocs.io/)
- [Smogon Usage Stats](https://www.smogon.com/stats/)
- [Damage Calculator](https://calc.pokemonshowdown.com/)
- [VGC Rule Set](https://www.pokemon.com/us/pokemon-news/2024-video-game-championship-series-regulations)

---

**Last Updated:** 2025 年 11 月 19 日 00:45  
**Next Review:** Phase 1.1 完了時
