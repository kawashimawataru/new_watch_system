# 次世代ロジック実装計画

**作成日**: 2025-12-31

---

## 現状評価

現在の設計は **研究水準にかなり近い**。

### 強み（そのまま武器）

| 機能 | 評価 |
|---|---|
| 候補爆発を抑えた探索（TurnAdvisor + PW + キャッシュ） | ✅ 現実的に勝たせる設計 |
| EGTの入口（Quantal Response） | ✅ 多くの実装はmaxだけ選んで事故る |
| OTS前提（テラ/持ち物/技は確定） | ✅ BeliefStateの焦点を絞れる |

### OTSならではの伸び代

1. **不完全情報の主因が「配分/実数値/ダメ乱数/行動」側に寄る**
2. **「読み＝相手の混合戦略」をより真面目に解く価値が上がる**

---

## 実装優先度

### S: 最優先（OTS最適化）

#### 1. EV/実数値 粒子推定（Particle Filter）

**目的**: OTSでも非公開のEV/実数値を推定

**観測可能な情報**:
- 行動順（S比較）
- 受けたダメージ量（A/D/Cライン）
- 回復量（残飯/再生力の発動量でHP実数が絞れる）

**実装コツ**:
```python
# 1体につき「あり得る実数値」粒子K（例 20〜50）を持つ
class StatParticle:
    hp: int
    atk: int
    def_: int
    spa: int
    spd: int
    spe: int
    weight: float  # 尤度

# ターンごとに
# 1. 重み更新（観測尤度）
# 2. リサンプル
# 3. 探索・ダメ計は「粒子平均」か「分位点」で使う
```

**効果**: 学習データ不要で「試合中に勝手に強くなる」

---

#### 2. Fictitious Play / Double Oracle

**目的**: Quantal Response を「解きに行く」

**現状**: Quantal Response は「効用から確率化」だけ
**改善**: 「相互作用の固定点（均衡）」を探しに行く

**実装（短時間・少反復）**:
```python
def fictitious_play(restricted_game, n_iter=5):
    """Restricted Game 上で Fictitious Play を回す"""
    # 相手分布 π_opp を初期化（一様）
    # 反復:
    #   1. π_opp に対する自分の最適応答 a*
    #   2. 自分分布 π_self を更新
    #   3. π_self に対する相手の最適応答 b*
    #   4. π_opp を更新
    # 最終的な混合戦略を返す
```

**効果**: 探索＋候補爆発対策＋キャッシュがそのまま武器になる

---

### A: 高優先度

#### 3. LLM を OpponentModel / Value 補正にも使う

**PokéChamp の3点セット**:
1. 行動サンプリング（✅ TurnAdvisor で対応済み）
2. **相手モデル（τや switch/protect 確率に反映）** ← 新規
3. **価値推定（プラン遂行度を評価に足す）** ← 新規

**実装**:
```python
# 相手モデルへの prior 反映
def get_opponent_prior(battle, llm_client):
    """相手視点の安定行動確率を LLM で推定"""
    # Q: この盤面、相手の安定行動は？
    # Q: Protect/守備的交代の確率が上がる条件は？
    # → OpponentModel の τ に反映

# 価値補正
def llm_value_correction(battle, plan, llm_client):
    """プラン遂行度を LLM で定性評価"""
    # 「勝ち筋は通ってる / 崩れてる」
    # → 評価関数に少しだけ足す
```

---

#### 4. PokeLLMon 系 Consistency / Self-critique

**現状**: 投票で安定化（✅ 対応済み）

**強化**:
- プランと矛盾する提案は**弾く/減点**
- 「ビビり行動」を検証
  - 「怖いから守る」
  - 「怖いからテラス温存」

**実装**:
```python
def validate_llm_proposal(proposal, plan, battle):
    """LLM提案を検証"""
    # プランと矛盾 → 減点
    # ビビり行動 → cona基準でスコアリング
    if contradicts_plan(proposal, plan):
        penalty += 0.5
    if is_scared_action(proposal):
        penalty += 0.3
```

---

### B: 中優先度

#### 5. 終盤"完全読み切り"モード

**目的**: 残数が少ないとき、詰み探索

**条件**: 残りポケモン ≤ 3体

**実装**:
```python
def endgame_solver(battle):
    """終盤専用の厳密探索"""
    if count_remaining(battle) <= 3:
        return exhaustive_search(battle)  # 分岐限定
    else:
        return mcts_search(battle)
```

---

## 実装順序

| 順序 | 機能 | 優先度 | 難易度 | 効果 |
|---|---|---|---|---|
| 1 | EV/実数値 粒子推定 | S | 高 | ダメ計精度UP |
| 2 | Fictitious Play | S | 中 | 読み精度UP |
| 3 | LLM → OpponentModel | A | 中 | 相手予測UP |
| 4 | LLM → Value補正 | A | 低 | プラン遂行 |
| 5 | Consistency強化 | A | 低 | LLM安定化 |
| 6 | 終盤読み切り | B | 中 | 終盤勝率UP |

---

## 参考実装

| 実装 | 参考ポイント |
|---|---|
| [VGC-Bench](https://arxiv.org/abs/2506.10326) | 評価設計 + EGTベースライン |
| [PokéChamp](https://github.com/sethkarten/pokechamp) | LLM×minimaxの実装方針 |
| [PokeLLMon](https://github.com/git-disl/PokeLLMon) | LLM安定化・一貫性の実装例 |
| [Metamon](https://github.com/UT-Austin-RPL/metamon) | RL・データ・ベースライン群 |
| [PokéAgent Challenge](https://pokeagent.github.io/) | 競技ベースライン |

---

## 次のアクション

- [ ] Phase 8-1: StatParticleFilter 実装（EV/実数値推定）
- [ ] Phase 8-2: FictitiousPlay 実装（restricted game上で5反復）
- [ ] Phase 8-3: LLM OpponentModel 補正
