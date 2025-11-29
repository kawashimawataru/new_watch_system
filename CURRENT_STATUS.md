## 現状サマリ（スナップショット）

作成日: 2025-11-19

このファイルは作業中の現状を短くまとめたスナップショットです。

### 概要

- プロジェクト: PBS-AI / new_watch_game_system
- 目的: ポケモン対戦の盤面から勝率推定と推奨行動を返すハイブリッド戦略器（Fast-Lane / Slow-Lane / AlphaZero）を可視化する

### 直近の主要変更

- フロントエンドを React（`frontend/web/`）へ完全移行

  - Streamlit ベースの `frontend/streamlit_app.py` を廃止し、React 側に Fast / Slow / AlphaZero レーン切り替え UI を実装
  - `convert_sample_to_battle_state()` を React のユーティリティに移植し、`teams` / `state` 形式から `p1/p2` 形式への変換と `legal_actions` 補完を行う
  - AlphaZero rollouts や HybridStrategist パラメータを React 側のコントロールで設定
  - これにより、フロントエンドは JS/TS スタックのみを使用し、Python は ML 推論 API に専念

- 新規ファイル: `ForAgentRead.md`（プロジェクト概要と実行手順）を作成済み

### テスト／実行状況（現時点）

- ユニットテスト: `tests/test_hybrid_strategist.py` を実行して全テストが通る状態（ローカルで pytest/pytest-asyncio を導入してパス）
- React アプリ: `cd frontend/web && npm run dev` で起動。サンプルデータ読み込み時に active の moves が補完され、`legal_actions` が空でなくなることを確認済み。

### 未解決の課題 / 注意点

1. species 重複のマッチング
   - 現行の補完ロジックは species 名で最初に見つかった team entry を使う（大文字小文字無視）。同一種族が複数いるケースでは誤補完の可能性あり。
2. ActionCandidate のターゲット情報
   - 現在は `target=None` など簡易的な構成。ターゲット推定（相手のどのスロットを狙うか）を入れると推奨行動の質が向上する。
3. AlphaZero の UI 実行
   - 現状は同期的／ブロッキングで呼び出している。長時間処理のため UI をブロックする。バックグラウンド化と進捗表示が望ましい。
4. React 版のコンポーネント設計
   - hooks の責務分担、ストリーム処理などを整理し、Next.js への移行をスムーズにする。

### 次のアクション（優先度順）

1. `convert_sample_to_battle_state()` のマッチ精度向上: slot/HP/順序でのマッチングを導入（必須度: 高）
2. AlphaZero を非ブロッキングで実行し、UI に進捗インジケータを追加（必須度: 中）
3. ActionCandidate の target と追加メタ情報を充実させ、evaluate の出力を改善（必須度: 中）
4. デプロイ手順書（Docker / Procfile）と CI の整備（必須度: 低）

### 作業履歴（短縮）

- 2025-11-19: React UI でのサンプル変換ロジックを強化し、active の moves 補完と legal_actions 生成を実装

---

ファイル作成者: 自動エージェント（作業補助）
