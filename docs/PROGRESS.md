# プロジェクト進捗管理

**最終更新**: 2024-12-24

## 現在のフェーズ

### ✅ 完了: VGC AI vs Human 対戦システム (2024-12-24)

人間がブラウザからAIプレイヤーにチャレンジして VGC 形式（gen9vgc2026regf）で対戦できるシステムが動作確認済み。

**実装内容:**
- `frontend/vgc_ai_player.py`: VGCダブルバトル対応AIプレイヤー
- `scripts/run_vgc_ai.py`: 起動スクリプト
- チャレンジ自動受付、チームプレビュー、技選択が動作

**現在の行動選択ロジック（ヒューリスティック）:**
1. 各アクティブポケモンの最高威力技を選択
2. ターゲットは相手の最初の生存ポケモン
3. 技がない場合は交代

> ⚠️ **課題**: 戦略性がなく弱い。HybridStrategist（MCTS + LightGBM）による強化が必要。

---

## アーキテクチャ概要

```
src/
├── domain/           # ドメイン層 (predictor/core/)
│   ├── models.py     # BattleState, PlayerState, ActionCandidate等
│   └── battle_parser.py
├── application/      # ユースケース層 (predictor/player/)
│   ├── hybrid_strategist.py   # Fast/Slow Lane統合
│   ├── monte_carlo_strategist.py  # MCTS実装
│   └── fast_lane_model.py     # LightGBM推論
├── infrastructure/   # インフラ層
│   └── pokemon-showdown/      # Showdownサーバー
└── frontend/         # プレゼンテーション層
    ├── vgc_ai_player.py       # VGC対戦AI
    ├── battle_ai_player.py    # シングル対戦AI
    └── spectator.py           # 観戦システム（開発中）
```

---

## 機能一覧

| 機能 | ステータス | ファイル |
|------|----------|---------|
| VGC AI vs Human (Heuristic) | ✅ 動作 | `frontend/vgc_ai_player.py` |
| VGC AI vs Human (MCTS) | ✅ 動作 | `frontend/vgc_ai_player.py` |
| 対戦観戦システム | ✅ 動作 | `frontend/spectator.py` |
| MCTS勝率予測 | ✅ 動作 | `predictor/player/monte_carlo_strategist.py` |
| FastLane (LightGBM) | ✅ 動作 | `predictor/player/fast_lane_model.py` |
| HybridStrategist | ✅ 動作 | `predictor/player/hybrid_strategist.py` |
| React UI | ⏸️ 一時停止 | `frontend/web/` |

---

## 起動方法

```bash
# 1. Showdownサーバー起動
cd pokemon-showdown && node pokemon-showdown start

# 2. VGC AI起動 (ヒューリスティック版)
python scripts/run_vgc_ai.py --strategy heuristic

# 2b. VGC AI起動 (MCTS版 - より賢い)
python scripts/run_vgc_ai.py --strategy mcts

# 3. 対戦観戦 (別ターミナル)
python scripts/run_battle_spectator.py --target VGC_AI

# 4. ブラウザで http://localhost:8000 にアクセスしてチャレンジ
```

---

## 次のアクション

1. **MCTS行動選択の最適化**: 2体同時の行動選択対応
2. **観戦システムの改良**: より詳細な行動予測表示
3. **React UIとの統合**: リアルタイム勝率グラフ表示

---

## 作業履歴

- **2024-12-24**: VGC AI vs Human 対戦システム完成、チームプレビュー・技選択が動作確認
- **2024-12-07**: AI Spectator システム開発開始、バトル検出のデバッグ
- **2024-11-19**: React UI移行、HybridStrategist統合
