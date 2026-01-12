"""
Spectator Analyzer - 観戦AI統合サービス

CandidateScorer + ExplanationGenerator を統合し、
観戦UI向けの候補手と解説を生成する。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from src.domain.services.candidate_scorer import (
    get_candidate_scorer, CandidateScorer, ScoredCandidate
)
from src.domain.services.board_evaluator import (
    get_board_evaluator, BoardEvaluator, BoardScore
)
from src.application.services.explanation_generator import (
    get_explanation_generator, ExplanationGenerator, BattleExplanation
)


@dataclass
class SpectatorAnalysis:
    """観戦AI分析結果"""
    turn: int
    win_rate: float                          # 勝率 (0.0-1.0)
    board_score: BoardScore                  # 盤面評価
    candidates: List[ScoredCandidate]        # スコア付き候補手
    explanation: BattleExplanation           # LLM解説
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "winRate": self.win_rate,
            "boardScore": self.board_score.to_dict(),
            "candidates": [c.to_dict() for c in self.candidates],
            "explanation": self.explanation.to_dict(),
        }
    
    def to_broadcast_format(self) -> Dict[str, Any]:
        """WebSocket送信用フォーマット"""
        return {
            "type": "game_update",
            "data": {
                "turn": self.turn,
                "winRate": self.win_rate,
                "boardScore": self.board_score.total,
                "candidates": {
                    "p1": [
                        {
                            "move1": c.move1,
                            "target1": c.target1,
                            "type1": c.type1,
                            "move2": c.move2,
                            "target2": c.target2,
                            "type2": c.type2,
                            "score": int(c.score),
                        }
                        for c in self.candidates
                    ],
                    "p2": [],  # 観戦モードでは相手の候補は生成しない
                },
                "explanation": {
                    "playerStrategy": self.explanation.recommended_strategy,
                    "opponentThreat": self.explanation.opponent_prediction,
                    "topCandidateReason": self.explanation.top_candidate_reason,
                    "riskAnalysis": self.explanation.risk_analysis,
                    "currentSituation": self.explanation.current_situation,
                },
            },
        }


class SpectatorAnalyzer:
    """
    観戦AI分析サービス
    
    盤面を受け取り、候補手のスコアリングとLLM解説を生成する。
    """
    
    def __init__(self, use_llm: bool = True):
        self.candidate_scorer = get_candidate_scorer()
        self.board_evaluator = get_board_evaluator()
        self.explanation_generator = get_explanation_generator()
        self.explanation_generator.use_openai = use_llm
    
    def analyze(
        self,
        player_active: List[Dict[str, Any]],
        opponent_active: List[Dict[str, Any]],
        player_bench: List[Dict[str, Any]] = None,
        opponent_bench: List[Dict[str, Any]] = None,
        field_state: Dict[str, Any] = None,
        turn: int = 1,
    ) -> SpectatorAnalysis:
        """
        盤面を分析
        
        Args:
            player_active: 自分の場のポケモン
            opponent_active: 相手の場のポケモン
            player_bench: 自分の控え
            opponent_bench: 相手の控え
            field_state: フィールド状態
            turn: 現在のターン
        
        Returns:
            SpectatorAnalysis
        """
        player_bench = player_bench or []
        opponent_bench = opponent_bench or []
        field_state = field_state or {}
        
        # 1. 盤面評価
        all_player = player_active + player_bench
        all_opponent = opponent_active + opponent_bench
        board_score = self.board_evaluator.evaluate(all_player, all_opponent, field_state)
        
        # 2. 勝率に変換（boardスコアを0.5中心に調整）
        win_rate = (board_score.total + 1.0) / 2.0  # -1~1 → 0~1
        win_rate = max(0.1, min(0.9, win_rate))  # 極端な値を避ける
        
        # 3. 候補手スコアリング
        candidates = self.candidate_scorer.score_candidates(
            player_active, opponent_active,
            player_bench, opponent_bench, field_state
        )
        
        # 4. LLM解説生成
        explanation = self.explanation_generator.generate(
            candidates, player_active, opponent_active, turn
        )
        
        return SpectatorAnalysis(
            turn=turn,
            win_rate=win_rate,
            board_score=board_score,
            candidates=candidates,
            explanation=explanation,
        )


# Singleton
_spectator_analyzer = None

def get_spectator_analyzer(use_llm: bool = True) -> SpectatorAnalyzer:
    global _spectator_analyzer
    if _spectator_analyzer is None:
        _spectator_analyzer = SpectatorAnalyzer(use_llm=use_llm)
    return _spectator_analyzer
