# 論文分析と改善ロードマップ

**作成日**: 2025-12-31

---

## 1. 現在の到達点

### 現在の構成

**「学習データなしで強くする」路線として、論文勢の"良いとこ取り"にかなり近い**

| コンポーネント | 状態 |
|---|---|
| BeliefState | ✅ 実装済み |
| リスク管理 (Secure/Gamble) | ✅ 実装済み |
| LLM候補絞り (TurnAdvisor) | ✅ 実装済み |
| 確率相手モデル (OpponentModel) | ✅ 実装済み |
| 深い探索 (depth=8, n_samples=500) | ✅ 実装済み |

---

## 2. 論文との比較

### VGC-Bench (2025)

- VGC特化の評価基盤（ヒューリスティック/LLM/BC/RL/EGT）
- **現状との相性**: TacticalMixer / RiskAware / BeliefState が VGC-Bench の経験的ゲーム理論と相性良い
- **次のステップ**: VGC-Bench流の測り方（generalization / exploitability）で強さを可視化
- [arXiv](https://arxiv.org/abs/2506.10326) | [GitHub](https://github.com/cameronangliss/vgc-bench)

### PokéChamp (2025)

- LLMで行動候補をサンプリング + ゲーム理論探索
- **現状との類似**: TurnAdvisorで候補爆発を抑えて探索精度を上げる → かなり近い
- **差分**: PokéChamp は minimax寄り（最悪ケース）、現状は Quantal/リスクモードで「人間っぽい混合」
- [arXiv](https://arxiv.org/abs/2503.04094) | [GitHub](https://github.com/sethkarten/pokechamp)

### PokeLLMon (2024)

- KAG + In-Context RL、consistent action generation
- **参考**: LLM出力の"ブレ"を抑える仕組み
- [arXiv](https://arxiv.org/abs/2402.01118)

### Metamon (2025)

- オフラインRL + Transformer（データがある前提）
- **現状との関係**: 今の目標（データ無しで強い）と真逆 → 思想の参考程度
- [Paper](https://rlj.cs.umass.edu/2025/papers/RLJ_RLC_2025_340.pdf)

---

## 3. 追加すると伸びやすいロジック

### A. BeliefState → Determinization（最重要）

BeliefStateを「探索に直結」させる：

1. 相手の「持ち物/努力値/テラス/技」の仮説を BeliefState から K個サンプル
2. 各サンプルで depth=8 探索 → 期待値を平均して手を選ぶ
3. 「相手がスカーフかどうか」「耐久振りかどうか」を探索側が自然に吸収

**実装済み**: `DeterminizedSolver` で K=5 のサンプリングを実装
**改善余地**: サンプル数の増加、仮説の多様性向上

### B. LLMの自己整合（PokeLLMon寄せ）

TurnAdvisor の候補品質を安定化：

1. 同一入力で 3回 TurnAdvisor を呼び、上位候補を投票で採用
2. `plan_alignment` が低い回は重みを下げる
3. 結果を top_k のフィルタに使う

**実装済み**: `ConsistentTurnAdvisor` で 3回呼び・投票を実装
**改善余地**: plan_alignment の重み調整

### C. Minimax寄せの安全策（PokéChamp寄せ）

Secure mode の中で「最悪ケース」を少しだけ見る：

1. Secure 判定のときだけ、OpponentModel の分布のうち「最悪に近い行動」を混ぜる
2. 確率は低いが即死に繋がるルートだけ、評価でペナルティを増やす

**実装状況**: 部分的（RiskAwareSolver の Secure mode）
**改善余地**: 最悪ケース評価の明示的な組み込み

### D. 探索最適化（速度維持で精度向上）

現在の depth=8 / n_samples=500 / top_k=80 は強いが、速度が課題：

| 最適化 | 効果 |
|---|---|
| Transposition Table | 同一局面の再計算を避ける |
| Progressive Widening | 探索回数が増えるほど候補を広げる |
| DamageCalc メモ化 | 攻撃側/防御側/技/テラス/場でキー化 |

**実装状況**: 未実装
**優先度**: 中（実戦タイマー対応時に必要）

---

## 4. シミュレーション数ゴリ押し戦略

**現在の設定（超高精度版）**:

| パラメータ | 値 | 計算量 |
|---|---|---|
| depth | 8 | 8ターン先まで |
| n_samples | 500 | 乱数500回 |
| top_k_self | 80 | 自分候補80手 |
| top_k_opp | 80 | 相手候補80手 |

**さらなるゴリ押し案**:

| パラメータ | 現在 | 最大版 | 計算量倍率 |
|---|---|---|---|
| depth | 8 | 10 | 1.25x |
| n_samples | 500 | 1000 | 2x |
| top_k_self | 80 | 120 | 1.5x |
| top_k_opp | 80 | 120 | 1.5x |

**注意**: 計算時間が 5〜10倍になる可能性あり

---

## 5. 参考 GitHub

### VGC（ダブル）

- **VGC-Bench**: VGC特化ベンチ＋複数ベースライン ([GitHub](https://github.com/cameronangliss/vgc-bench))

### LLM＋探索

- **PokéChamp**: minimax/探索にLLMを組み込む設計 ([GitHub](https://github.com/sethkarten/pokechamp))

### 基盤

- **poke-env**: Showdownボット基盤の定番 ([GitHub](https://github.com/hsahovic/poke-env))

### RL/自己対戦

- **metagrok**: 自己対戦RLの古典実装 ([GitHub](https://github.com/yuzeh/metagrok))
- **poke_RL**: 複数RL手法まとめ ([GitHub](https://github.com/leolellisr/poke_RL))

### MCTS

- **MCTS-Pokemon-Battle-Policy**: MCTS＋ヒューリスティック ([GitHub](https://github.com/leonardocrociani/MCTS-Pokemon-Battle-Policy))

---

## 6. 次のアクション（優先順）

1. **BeliefState → Determinization の強化**
   - サンプル数 K=5 → K=10
   - 仮説の多様性向上

2. **LLM自己整合の調整**
   - plan_alignment 閾値の最適化
   - 投票アルゴリズムの改善

3. **VGC-Bench での評価**
   - winrate / turns / Exploitability / チーム一般化
   - 定期的なベンチマーク実行

4. **探索最適化（速度対応）**
   - Transposition Table の実装
   - DamageCalc メモ化

---

## 7. 所感

- **方向性は論文最前線と整合**（特に VGC-Bench と相性良い）
- いまの"超高精度版"は **パラメータ増で殴っている** → 次は構造的改善
- 最優先: **(1) Determinization強化 (2) LLM自己整合 (3) 探索最適化**
