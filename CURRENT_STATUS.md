# VGC AI System - 現在の実装状況

最終更新: 2026-01-10

---

## ✅ 完了済み機能

### Phase 1-10: AI基盤
- ダメージ計算API (smogon-calc連携)
- ターン間状態追跡 (BattleMemory)
- 相手行動予測 (OpponentModel)
- 隠れ情報管理 (BeliefState)
- Fast-Lane (LightGBM) + Slow-Lane (MCTS) 統合
- HybridStrategist

### Phase 11: Spectator UI
- [x] Next.js 16.1.1 + Tailwind v4 セットアップ
- [x] 放送風UIレイアウト (プレイヤーパネル、勝率バー)
- [x] ダブルバトル候補手表示 (2匹同時行動)
- [x] 戦術図解モード (VisualReasoningView)
- [x] VFX演出 (Nice Play, Fate Turn, Critical, OHKO, Danger)
- [x] 毛筆フォント (Yuji Syuku) 導入

### Phase 12: Backend-Frontend Integration
- [x] `Spectator._broadcast_state` 拡張
  - 候補手送信
  - AI解説送信
  - 勝率履歴送信
- [x] `useGameState` フック更新
- [x] ライブデータ表示 (モックフォールバック付き)

### Phase 13: ドキュメント整備
- [x] README.md 更新
- [x] web-ui/README.md 作成
- [x] 引き継ぎドキュメント作成

---

## ⏳ 今後の課題

### UI改善
- [ ] ポケモン画像/アイコン表示
- [ ] テラスタル予測の可視化
- [ ] 急所/OHKOの自動検出トリガー
- [ ] モバイル対応

### AI強化
- [ ] Policy/Value Network (AlphaZero-Lane)
- [ ] 相手プレイスタイル推定
- [ ] ログからの学習

---

## 🔧 既知の問題

1. **観戦モードでのポケモン情報取得**
   - poke-envの制限により、観戦者視点でのチーム情報取得が困難
   - 現在はダミーデータでフォールバック

2. **WebSocket再接続**
   - サーバー再起動時に自動再接続に3秒のラグ

---

## 📊 ファイル統計

| ディレクトリ | ファイル数 | 主な内容 |
|-------------|-----------|---------|
| `src/` | 52 | Pythonバックエンド |
| `predictor/` | 46 | AI予測エンジン |
| `web-ui/` | 30 | Next.jsフロントエンド |
| `docs/` | 29 | ドキュメント |
| `scripts/` | 35 | 起動・テストスクリプト |
