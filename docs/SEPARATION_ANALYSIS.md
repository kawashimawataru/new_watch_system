# 観戦AIと戦闘AIの分離状況分析

**作成日**: 2026-01-12

---

## 🔍 現状の問題

### 1. 重複ファイルの存在

| ファイル | 場所 | クラス | 行数 | 状態 |
|---------|------|--------|------|------|
| `VGCAIPlayer` | `frontend/vgc_ai_player.py` | VGCAIPlayer | 1030行 | ⚠️ 完全版（ActionFilterService等） |
| `VGCAIPlayer` | `src/application/players/vgc_ai_player.py` | VGCAIPlayer | 323行 | ⚠️ シンプル版 |

**問題**: 2つのファイルが存在し、機能が異なる

### 2. インポートパスの不整合

```python
# scripts/run_vgc_ai.py
from frontend.vgc_ai_player import VGCAIPlayer  # ❌ frontend/ を参照

# しかし src/application/players/vgc_ai_player.py も存在
```

### 3. 観戦AIと戦闘AIの分離状況

#### ✅ 観戦AI（正しく分離されている）
- **場所**: `src/application/players/spectator.py`
- **クラス**: `Spectator`
- **役割**: バトルを観戦し、WebSocket経由で分析結果を配信
- **特徴**: 行動を選択しない（`choose_move` は `/choose default` を返す）

#### ⚠️ 戦闘AI（重複あり）
- **場所1**: `src/application/players/vgc_ai_player.py` (323行)
- **場所2**: `frontend/vgc_ai_player.py` (1030行) ← より機能が豊富
- **クラス**: `VGCAIPlayer`
- **役割**: 実際に対戦し、行動を選択

---

## 📋 推奨される構造

```
src/application/players/
├── spectator.py          # 観戦AI (Spectator) ✅
├── vgc_ai_player.py      # VGC戦闘AI (VGCAIPlayer) ← 完全版に統一
└── battle_ai_player.py   # 汎用戦闘AI (AIPlayer)

frontend/
└── (vgc_ai_player.py は削除または廃止)
```

---

## ✅ 修正が必要な箇所

1. **重複ファイルの統合**
   - `frontend/vgc_ai_player.py` の内容を `src/application/players/vgc_ai_player.py` に統合
   - 完全版（1030行）を採用

2. **インポートパスの統一**
   - `scripts/run_vgc_ai.py` のインポートを修正
   - すべて `src.application.players` からインポート

3. **観戦AIと戦闘AIの明確な分離**
   - 観戦AIは `Spectator` クラスのみ
   - 戦闘AIは `VGCAIPlayer` と `AIPlayer` に分離
   - 両者は独立して動作可能

---

## 🔍 分離チェックリスト

- [x] 観戦AIは `src/application/players/spectator.py` に存在
- [x] 観戦AIは行動を選択しない（`choose_move` はデフォルト）
- [x] 観戦AIはWebSocket経由で配信
- [ ] 戦闘AIは1つの場所に統一されている
- [ ] 戦闘AIは実際に行動を選択する
- [ ] 両者のインポートパスが統一されている
