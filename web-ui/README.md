# VGC AI Spectator - Web UI

Pokemon Showdown観戦UIのNext.jsフロントエンド。

---

## 🚀 起動方法

```bash
npm install  # 初回のみ
npm run dev
```

ブラウザで `http://localhost:3000` を開く

---

## 📁 ファイル構造

```
web-ui/
├── app/
│   ├── page.tsx          # メインSpectatorPage
│   ├── layout.tsx        # ルートレイアウト
│   └── globals.css       # Tailwind + カスタムCSS + フォント
│
├── components/
│   ├── BroadcastCandidateList.tsx  # ダブルバトル候補手
│   ├── VisualReasoningView.tsx     # 戦術図解モード
│   ├── WinRateBar.tsx              # PBS風勝率バー
│   ├── PlayerPanel.tsx             # プレイヤー情報パネル
│   ├── EffectOverlay.tsx           # VFX演出
│   ├── DebugPad.tsx                # デバッグコントロール
│   ├── ShowdownFrame.tsx           # Showdown iframe
│   ├── ReasoningView.tsx           # テキスト推論ビュー
│   ├── WinRateChart.tsx            # 勝率推移チャート
│   ├── CandidateList.tsx           # 旧候補手リスト
│   └── ui/
│       └── GlassCard.tsx           # 汎用ガラスカード
│
├── hooks/
│   └── useGameState.ts   # WebSocket接続・状態管理
│
├── lib/
│   └── utils.ts          # ユーティリティ (cn関数)
│
└── public/               # 静的ファイル
```

---

## 🎨 デザインシステム

### カラーパレット (globals.css)

```css
--color-neon-blue: #0ea5e9;
--color-neon-purple: #a855f7;
--color-neon-rose: #f43f5e;
--color-neon-green: #22c55e;
```

### フォント

- `Geist` - UI用サンセリフ
- `Geist Mono` - 数値・コード用
- `Yuji Syuku` - 毛筆（Fate Turn演出）
- `Zen Dots` - テックスタイル

---

## 🔌 バックエンド連携

WebSocket URL: `ws://localhost:8000/ws/spectator`

### 受信データ形式

```typescript
interface GameState {
  turn: number;
  winRate: number;
  winRateHistory: WinRatePoint[];
  p1: PlayerInfo;
  p2: PlayerInfo;
  candidates: {
    p1: CandidateMove[];
    p2: CandidateMove[];
  };
  explanation: {
    playerStrategy: string;
    opponentThreat: string;
  };
}
```

---

## 🎬 VFX演出

`EffectOverlay.tsx` で管理:

| Effect | 説明 |
|--------|------|
| `nice-play` | 読み成功時 |
| `fate-turn` | 勝率大変動時 |
| `critical-hit` | 急所命中 |
| `ohko` | 一撃必殺 |
| `danger` | 敗着警告 |

デバッグパッド（右下⚙️）からテスト可能。

---

## 📦 依存パッケージ

```json
{
  "next": "^16.0.0",
  "react": "^19.0.0",
  "framer-motion": "^11.15.0",
  "lucide-react": "^0.468.0",
  "clsx": "^2.1.1",
  "tailwind-merge": "^2.5.5",
  "recharts": "^2.15.0"
}
```

---

## 🔧 Tailwind CSS v4

設定は `globals.css` 内の `@theme` ディレクティブで管理:

```css
@import "tailwindcss";

@theme {
  --color-neon-blue: #0ea5e9;
  /* ... */
}
```

`tailwind.config.ts` は使用しない（v4はCSS-firstアプローチ）。
