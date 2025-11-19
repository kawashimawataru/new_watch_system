# 🎮 Streamlit UI 使用ガイド

## 起動方法

```bash
# プロジェクトルートから実行
streamlit run frontend/streamlit_app.py

# または仮想環境を明示的に指定
.venv/bin/streamlit run frontend/streamlit_app.py
```

起動後、ブラウザで **http://localhost:8501** にアクセス

---

## 使い方（簡易版）

### 1️⃣ サンプルデータで試す（推奨）

1. **サイドバー**の「📂 サンプルデータを読み込む」ボタンをクリック
2. **「📝 入力データ」タブ**に移動
3. 2 つのボタンから選択:
   - **⚡ Fast-Lane 評価（即時）**: ~3ms で即座に結果表示
   - **🎯 統合評価（Fast + Slow）**: Fast + MCTS 精密計算（~600ms）
4. **「📊 リアルタイム表示」タブ**で結果を確認

---

## 使い方（カスタムデータ）

### 2️⃣ 自分のバトルデータで試す

**「📝 入力データ」タブ**で以下を入力:

#### Battle Log (JSON 形式)

```json
{
  "turn": 5,
  "p1": {
    "name": "Player A",
    "active": [
      {
        "species": "Rillaboom",
        "level": 50,
        "hp": 85,
        "maxhp": 100,
        "status": null,
        "ability": "Grassy Surge",
        "item": "Assault Vest",
        "moves": ["Fake Out", "Grassy Glide", "Wood Hammer", "U-turn"],
        "boosts": { "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0 }
      }
    ],
    "reserves": []
  },
  "p2": {
    "name": "Player B",
    "active": [
      {
        "species": "Zacian-Crowned",
        "level": 50,
        "hp": 70,
        "maxhp": 100,
        "status": null,
        "ability": "Intrepid Sword",
        "item": "Rusted Sword",
        "moves": ["Behemoth Blade", "Play Rough", "Sacred Sword", "Protect"],
        "boosts": { "atk": 1, "def": 0, "spa": 0, "spd": 0, "spe": 0 }
      }
    ],
    "reserves": []
  },
  "weather": "Rain",
  "terrain": null
}
```

---

## 表示内容の見方

### ⚡ Fast-Lane 予測結果

- **勝率ゲージ**: Player A / Player B の推定勝率
- **⚡ FAST prediction**: 高速推論（~3ms）
- **🎲 Confidence: 60%**: 信頼度（Fast-Lane は 0.6 固定）
- **⏱️ Inference: 2.75ms**: 推論時間

### 🎯 Slow-Lane 精密予測結果

- **勝率ゲージ**: MCTS による精密計算
- **🎯 SLOW prediction**: 精密推論（~600ms, 100 rollouts）
- **🎲 Confidence: 90%**: 信頼度（Slow-Lane は 0.9 固定）
- **⏱️ Inference: 590.85ms**: 推論時間

### 📊 Fast vs Slow 比較

- **勝率差**: Fast と Slow の予測差
- **速度比**: Slow が Fast の何倍時間がかかるか
- **判定**: ✅ 一致 / ⚠️ 不一致（差が 10%未満なら一致）

---

## トラブルシューティング

### ❌ モデルが見つからない

```
⚠️ Fast-Laneモデルが見つかりません: models/fast_lane.pkl
```

**解決方法**: Fast-Lane モデルを訓練してください

```bash
.venv/bin/python scripts/train_fast_lane.py
```

### ❌ HybridStrategist 初期化エラー

エラーログを確認して、不足しているモジュールをインストール:

```bash
.venv/bin/pip install lightgbm numpy pandas
```

### ⚠️ Streamlit が起動しない

```bash
# Streamlitをインストール
.venv/bin/pip install streamlit plotly

# 再起動
.venv/bin/streamlit run frontend/streamlit_app.py
```

---

## パフォーマンス目標

| レーン                   | 目標   | 実測値 | 状態 |
| ------------------------ | ------ | ------ | ---- |
| Fast-Lane                | <1ms   | 2.75ms | ✅   |
| Slow-Lane (100 rollouts) | <100ms | 590ms  | ⚠️   |
| 統合                     | <100ms | 593ms  | ⚠️   |

**Note**: Slow-Lane は 100 rollouts で約 600ms。本番では 10 rollouts で約 60ms に短縮可能。

---

## 次のステップ

1. ✅ **サンプルデータで動作確認**
2. 🔄 **自分のバトルログで試す**
3. 📊 **Fast vs Slow の判定精度を確認**
4. 🎯 **MCTS rollouts を調整してパフォーマンス最適化**

---

## 参考リンク

- HybridStrategist 実装: `predictor/player/hybrid_strategist.py`
- テストスクリプト: `scripts/test_hybrid_ui.py`
- サンプルデータ: `tests/data/simple_battle_state.json`
