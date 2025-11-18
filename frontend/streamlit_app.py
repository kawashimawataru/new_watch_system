"""
🎮 PBS-AI Ultimate: Streamlit MVP

リアルタイム勝率表示と推奨行動を可視化する最小実装。

起動方法:
    streamlit run frontend/streamlit_app.py
"""

import json
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path
from typing import Dict, Any, List, Optional

# ページ設定
st.set_page_config(
    page_title="PBS-AI Ultimate",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .big-font {
        font-size: 48px !important;
        font-weight: bold;
    }
    .win-rate-player-a {
        color: #4CAF50;
    }
    .win-rate-player-b {
        color: #FF5722;
    }
    .excitement-badge {
        background-color: #FF0000;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        animation: pulse 1s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    .action-card {
        border: 2px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .recommended {
        border-color: #4CAF50;
        background-color: #E8F5E9;
    }
</style>
""", unsafe_allow_html=True)


def load_sample_data() -> Dict[str, Any]:
    """サンプルデータを読み込む"""
    sample_path = Path(__file__).parent.parent / "frontend/web/public/sample-data.json"
    if sample_path.exists():
        with open(sample_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def call_evaluate_position(team_a: str, team_b: str, battle_log: Dict, estimated_evs: Optional[Dict] = None) -> Dict[str, Any]:
    """evaluate_position を呼び出す（モック実装）"""
    try:
        from predictor.core.position_evaluator import evaluate_position
        result = evaluate_position(
            team_a_pokepaste=team_a,
            team_b_pokepaste=team_b,
            battle_log=battle_log,
            estimated_evs=estimated_evs or {},
            algorithm="heuristic"
        )
        return result
    except Exception as e:
        st.error(f"評価エラー: {e}")
        return {}


def render_win_rate_gauge(player_a_rate: float, player_b_rate: float):
    """勝率ゲージを表示"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.markdown(f'<p class="big-font win-rate-player-a">{player_a_rate:.1%}</p>', unsafe_allow_html=True)
        st.markdown("**Player A**")
    
    with col2:
        # プログレスバー
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=player_a_rate * 100,
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "darkgreen"},
                'steps': [
                    {'range': [0, 40], 'color': "lightcoral"},
                    {'range': [40, 60], 'color': "lightyellow"},
                    {'range': [60, 100], 'color': "lightgreen"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 50
                }
            },
            title={'text': "勝率"}
        ))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
    
    with col3:
        st.markdown(f'<p class="big-font win-rate-player-b">{player_b_rate:.1%}</p>', unsafe_allow_html=True)
        st.markdown("**Player B**")


def render_turn_history(history: List[Dict[str, Any]]):
    """ターン履歴を表示（モック）"""
    st.subheader("📊 ターン推移")
    
    if not history:
        st.info("ターン履歴データがありません")
        return
    
    # 勝率推移グラフ
    turns = [h["turn"] for h in history]
    player_a_rates = [h.get("playerA_winrate", 0.5) for h in history]
    player_b_rates = [h.get("playerB_winrate", 0.5) for h in history]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=turns, y=player_a_rates, mode='lines+markers', name='Player A', line=dict(color='green', width=3)))
    fig.add_trace(go.Scatter(x=turns, y=player_b_rates, mode='lines+markers', name='Player B', line=dict(color='red', width=3)))
    fig.update_layout(
        title="勝率推移",
        xaxis_title="ターン",
        yaxis_title="勝率",
        yaxis=dict(range=[0, 1]),
        hovermode='x unified',
        height=300
    )
    st.plotly_chart(fig, use_container_width=True)


def render_action_recommendations(player_name: str, active_pokemon: List[Dict[str, Any]]):
    """推奨行動を表示"""
    st.subheader(f"🎯 {player_name} の推奨行動")
    
    for pokemon in active_pokemon:
        with st.expander(f"**{pokemon['name']}**", expanded=True):
            moves = pokemon.get("suggestedMoves", [])
            if not moves:
                st.info("推奨技なし")
                continue
            
            for i, move in enumerate(moves):
                is_best = i == 0
                card_class = "action-card recommended" if is_best else "action-card"
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{move['move']}**")
                    if move.get('target'):
                        st.caption(f"対象: {move['target']}")
                with col2:
                    score_percent = move['score'] * 100
                    st.metric("スコア", f"{score_percent:.0f}%")
                
                if is_best:
                    st.success("✅ 最推奨")
                
                st.progress(move['score'])
                st.divider()


def render_battle_state(state: Dict[str, Any]):
    """盤面状態を表示"""
    st.subheader("⚔️ 現在の盤面")
    
    col1, col2 = st.columns(2)
    
    for player_key, col in [("A", col1), ("B", col2)]:
        player = state.get(player_key, {})
        with col:
            st.markdown(f"### {player.get('name', f'Player {player_key}')}")
            
            active = player.get("active", [])
            for pokemon in active:
                with st.container():
                    st.markdown(f"**{pokemon.get('name', '不明')}**")
                    hp = pokemon.get('hp', '???')
                    status = pokemon.get('status')
                    boosts = pokemon.get('boosts', {})
                    
                    st.caption(f"HP: {hp}" + (f" / 状態: {status}" if status else ""))
                    if boosts:
                        boost_text = ", ".join([f"{k}:{v:+d}" for k, v in boosts.items()])
                        st.caption(f"ランク補正: {boost_text}")
                    st.divider()
            
            reserves = player.get("reserves", [])
            if reserves:
                st.caption(f"控え: {', '.join(reserves)}")


def main():
    st.title("🎮 PBS-AI Ultimate: Visualization MVP")
    st.markdown("---")
    
    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")
        
        # サンプルデータ読み込み
        if st.button("📂 サンプルデータを読み込む", use_container_width=True):
            sample = load_sample_data()
            if sample:
                st.session_state["team_a"] = sample.get("teamA", "")
                st.session_state["team_b"] = sample.get("teamB", "")
                st.session_state["battle_log"] = json.dumps(sample.get("battleLog", {}), indent=2, ensure_ascii=False)
                st.session_state["estimated_evs"] = json.dumps(sample.get("estimatedEvs", {}), indent=2, ensure_ascii=False)
                st.success("✅ サンプルデータを読み込みました")
            else:
                st.error("サンプルデータが見つかりません")
        
        st.markdown("---")
        
        # アルゴリズム選択
        algorithm = st.selectbox(
            "評価アルゴリズム",
            ["heuristic", "mcts (未実装)", "ml (未実装)"],
            disabled=True
        )
        
        st.markdown("---")
        st.caption("Phase 2: Visualization MVP")
        st.caption("Version 0.1.0")
    
    # メインエリア
    tab1, tab2, tab3 = st.tabs(["📊 リアルタイム表示", "📝 入力データ", "ℹ️ 使い方"])
    
    with tab1:
        # 評価結果の表示
        if "evaluation_result" in st.session_state and st.session_state["evaluation_result"]:
            result = st.session_state["evaluation_result"]
            
            # 勝率表示
            player_a = result.get("playerA", {})
            player_b = result.get("playerB", {})
            
            win_rate_a = player_a.get("winRate", 0.5)
            win_rate_b = player_b.get("winRate", 0.5)
            
            # 重要ターン判定（モック）
            excitement = abs(win_rate_a - win_rate_b) > 0.3
            if excitement:
                st.markdown('<div class="excitement-badge">🔥 CRITICAL TURN!</div>', unsafe_allow_html=True)
            
            render_win_rate_gauge(win_rate_a, win_rate_b)
            
            st.markdown("---")
            
            # 推奨行動
            col1, col2 = st.columns(2)
            with col1:
                render_action_recommendations("Player A", player_a.get("active", []))
            with col2:
                render_action_recommendations("Player B", player_b.get("active", []))
            
            st.markdown("---")
            
            # 盤面状態（バトルログから取得）
            if "battle_log" in st.session_state:
                try:
                    battle_log = json.loads(st.session_state["battle_log"])
                    if "state" in battle_log:
                        render_battle_state(battle_log["state"])
                except:
                    pass
            
            st.markdown("---")
            
            # ターン履歴（モック）
            mock_history = [
                {"turn": 1, "playerA_winrate": 0.50, "playerB_winrate": 0.50},
                {"turn": 2, "playerA_winrate": 0.55, "playerB_winrate": 0.45},
                {"turn": 3, "playerA_winrate": 0.48, "playerB_winrate": 0.52},
                {"turn": 4, "playerA_winrate": 0.62, "playerB_winrate": 0.38},
                {"turn": 5, "playerA_winrate": win_rate_a, "playerB_winrate": win_rate_b},
            ]
            render_turn_history(mock_history)
        else:
            st.info("👈 サイドバーから「サンプルデータを読み込む」→「入力データ」タブで「評価実行」してください")
    
    with tab2:
        st.subheader("📝 入力データ")
        
        # Pokepaste
        col1, col2 = st.columns(2)
        with col1:
            team_a = st.text_area(
                "Team A (Pokepaste)",
                value=st.session_state.get("team_a", ""),
                height=200,
                key="team_a_input"
            )
        with col2:
            team_b = st.text_area(
                "Team B (Pokepaste)",
                value=st.session_state.get("team_b", ""),
                height=200,
                key="team_b_input"
            )
        
        # バトルログ
        battle_log_str = st.text_area(
            "Battle Log (JSON)",
            value=st.session_state.get("battle_log", "{}"),
            height=200,
            key="battle_log_input"
        )
        
        # 推定EV
        estimated_evs_str = st.text_area(
            "Estimated EVs (JSON, 任意)",
            value=st.session_state.get("estimated_evs", "{}"),
            height=100,
            key="estimated_evs_input"
        )
        
        # 評価実行ボタン
        if st.button("🚀 評価を実行", use_container_width=True, type="primary"):
            if not team_a or not team_b or not battle_log_str:
                st.error("Team A, Team B, Battle Log を入力してください")
            else:
                with st.spinner("評価中..."):
                    try:
                        battle_log = json.loads(battle_log_str)
                        estimated_evs = json.loads(estimated_evs_str) if estimated_evs_str.strip() else None
                        
                        # 評価実行
                        result = call_evaluate_position(team_a, team_b, battle_log, estimated_evs)
                        
                        if result:
                            st.session_state["evaluation_result"] = result
                            st.session_state["team_a"] = team_a
                            st.session_state["team_b"] = team_b
                            st.session_state["battle_log"] = battle_log_str
                            st.session_state["estimated_evs"] = estimated_evs_str
                            st.success("✅ 評価完了！「リアルタイム表示」タブで結果を確認してください")
                            st.rerun()
                        else:
                            st.error("評価に失敗しました")
                    except json.JSONDecodeError as e:
                        st.error(f"JSON パースエラー: {e}")
                    except Exception as e:
                        st.error(f"エラー: {e}")
        
        # Raw JSON 表示
        if "evaluation_result" in st.session_state and st.session_state["evaluation_result"]:
            with st.expander("🔍 評価結果 (Raw JSON)"):
                st.json(st.session_state["evaluation_result"])
    
    with tab3:
        st.subheader("ℹ️ 使い方")
        
        st.markdown("""
        ### 🎯 このアプリについて
        
        **PBS-AI Ultimate** の可視化MVPです。ポケモン対戦の盤面から勝率と推奨行動を表示します。
        
        ### 📖 使い方
        
        1. **サイドバー** の「サンプルデータを読み込む」をクリック
        2. **「入力データ」タブ** に移動
        3. **「評価を実行」** ボタンをクリック
        4. **「リアルタイム表示」タブ** で結果を確認
        
        ### 🔧 機能
        
        - **勝率ゲージ**: Player A / Player B の推定勝率をリアルタイム表示
        - **推奨行動**: 各ポケモンの最適な技とスコアを表示
        - **盤面状態**: 現在のHP、状態異常、ランク補正を表示
        - **ターン推移**: 勝率の時系列変化をグラフ化
        - **重要ターン検知**: 勝率が大きく変動したターンをハイライト
        
        ### 📊 データ形式
        
        - **Pokepaste**: Showdown形式のチーム情報
        - **Battle Log**: 現在の盤面状態を含むJSON
        - **Estimated EVs**: 努力値推定値（オプション）
        
        ### 🚀 次のステップ
        
        - Phase 1.1: Detective Engine（EV推定）の統合
        - Phase 1.3: Strategist（勝率予測モデル）の学習
        - Phase 3: LLM による実況解説の追加
        """)


if __name__ == "__main__":
    main()
