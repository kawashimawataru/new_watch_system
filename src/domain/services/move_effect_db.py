"""
Move Effect Database - LLM用技効果データベース

VGCでよく使われる技の効果を簡潔に説明するデータベース。
LLMが技の効果を正確に理解するために使用。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class MoveInfo:
    """技の情報"""
    name: str               # 英語名
    japanese_name: str      # 日本語名
    type: str               # タイプ
    category: str           # "physical" | "special" | "status"
    power: Optional[int]    # 威力 (status技はNone)
    accuracy: int           # 命中率
    priority: int           # 優先度 (-7 ~ +5)
    target: str             # "normal", "all", "ally", "self", etc.
    effect: str             # 効果の簡潔な説明
    key_notes: List[str]    # 重要な注意点
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "japanese_name": self.japanese_name,
            "type": self.type,
            "category": self.category,
            "power": self.power,
            "accuracy": self.accuracy,
            "priority": self.priority,
            "target": self.target,
            "effect": self.effect,
            "key_notes": self.key_notes,
        }
    
    def to_summary_text(self) -> str:
        """LLM用の簡潔な説明"""
        lines = [f"{self.japanese_name} ({self.name})"]
        lines.append(f"  タイプ: {self.type}, 威力: {self.power or '-'}, 優先度: {self.priority:+d}")
        lines.append(f"  効果: {self.effect}")
        if self.key_notes:
            lines.append(f"  注意: {'; '.join(self.key_notes)}")
        return "\n".join(lines)


# VGCで重要な技のデータベース
MOVE_DATABASE: Dict[str, MoveInfo] = {
    # --- 優先度技 ---
    "protect": MoveInfo(
        name="protect", japanese_name="まもる", type="Normal", category="status",
        power=None, accuracy=100, priority=4, target="self",
        effect="このターン、自分への攻撃を完全に防ぐ",
        key_notes=["連続使用で成功率低下", "フェイント等で貫通される"]
    ),
    "detect": MoveInfo(
        name="detect", japanese_name="みきり", type="Fighting", category="status",
        power=None, accuracy=100, priority=4, target="self",
        effect="まもると同じ効果",
        key_notes=["まもると併用で連続使用リセット回避"]
    ),
    "fakeout": MoveInfo(
        name="fakeout", japanese_name="ねこだまし", type="Normal", category="physical",
        power=40, accuracy=100, priority=3, target="normal",
        effect="相手を必ず怯ませる。出た最初のターンのみ使用可能",
        key_notes=["インナーフォーカスやせいしんりょくで無効", "まもる貫通しない"]
    ),
    "extremespeed": MoveInfo(
        name="extremespeed", japanese_name="しんそく", type="Normal", category="physical",
        power=80, accuracy=100, priority=2, target="normal",
        effect="ほぼ必ず先制できる",
        key_notes=["アクアジェット(+1)より優先"]
    ),
    "suckerpunch": MoveInfo(
        name="suckerpunch", japanese_name="ふいうち", type="Dark", category="physical",
        power=70, accuracy=100, priority=1, target="normal",
        effect="相手が攻撃技を選んでいる場合のみ成功",
        key_notes=["相手が交代・守る・変化技なら失敗"]
    ),
    "aquajet": MoveInfo(
        name="aquajet", japanese_name="アクアジェット", type="Water", category="physical",
        power=40, accuracy=100, priority=1, target="normal",
        effect="先制攻撃",
        key_notes=[]
    ),
    "feint": MoveInfo(
        name="feint", japanese_name="フェイント", type="Normal", category="physical",
        power=30, accuracy=100, priority=2, target="normal",
        effect="まもる・みきりを貫通して攻撃",
        key_notes=["まもるを解除する"]
    ),
    
    # --- 全体技 ---
    "heatwave": MoveInfo(
        name="heatwave", japanese_name="ねっぷう", type="Fire", category="special",
        power=95, accuracy=90, priority=0, target="allAdjacentFoes",
        effect="相手2体を攻撃。10%でやけど",
        key_notes=["ダブルでは威力0.75倍"]
    ),
    "rockslide": MoveInfo(
        name="rockslide", japanese_name="いわなだれ", type="Rock", category="physical",
        power=75, accuracy=90, priority=0, target="allAdjacentFoes",
        effect="相手2体を攻撃。30%で怯み",
        key_notes=["素早さが高いほど怯みが強い"]
    ),
    "earthquake": MoveInfo(
        name="earthquake", japanese_name="じしん", type="Ground", category="physical",
        power=100, accuracy=100, priority=0, target="allAdjacent",
        effect="自分以外の場にいる全員を攻撃",
        key_notes=["味方も巻き込む", "ひこうタイプ・ふゆうに無効"]
    ),
    "dazzlinggleam": MoveInfo(
        name="dazzlinggleam", japanese_name="マジカルシャイン", type="Fairy", category="special",
        power=80, accuracy=100, priority=0, target="allAdjacentFoes",
        effect="相手2体を攻撃",
        key_notes=[]
    ),
    "astralbarrage": MoveInfo(
        name="astralbarrage", japanese_name="アストラルビット", type="Ghost", category="special",
        power=120, accuracy=100, priority=0, target="allAdjacentFoes",
        effect="相手2体を攻撃",
        key_notes=["黒馬バドレックス専用技", "ノーマルタイプに無効"]
    ),
    "surgingstrikes": MoveInfo(
        name="surgingstrikes", japanese_name="すいりゅうれんだ", type="Water", category="physical",
        power=25, accuracy=100, priority=0, target="normal",
        effect="3回連続攻撃、必ず急所に当たる",
        key_notes=["きあいのタスキ貫通", "威力合計75"]
    ),
    
    # --- 重要な変化技 ---
    "trickroom": MoveInfo(
        name="trickroom", japanese_name="トリックルーム", type="Psychic", category="status",
        power=None, accuracy=100, priority=-7, target="all",
        effect="5ターン、素早さが遅いほど先に行動できる",
        key_notes=["最後に発動", "再使用で解除"]
    ),
    "tailwind": MoveInfo(
        name="tailwind", japanese_name="おいかぜ", type="Flying", category="status",
        power=None, accuracy=100, priority=0, target="allySide",
        effect="4ターン、味方の素早さ2倍",
        key_notes=[]
    ),
    "ragepowder": MoveInfo(
        name="ragepowder", japanese_name="いかりのこな", type="Bug", category="status",
        power=None, accuracy=100, priority=2, target="self",
        effect="このターン、相手の単体技を自分に向ける",
        key_notes=["くさタイプ・ぼうじんゴーグルに無効", "ねこだましより遅い(+2)"]
    ),
    "followme": MoveInfo(
        name="followme", japanese_name="このゆびとまれ", type="Normal", category="status",
        power=None, accuracy=100, priority=2, target="self",
        effect="このターン、相手の単体技を自分に向ける",
        key_notes=["いかりのこなと同効果だがタイプ無視"]
    ),
    "helpinghand": MoveInfo(
        name="helpinghand", japanese_name="てだすけ", type="Normal", category="status",
        power=None, accuracy=100, priority=5, target="adjacentAlly",
        effect="味方の技の威力を1.5倍にする",
        key_notes=["まもるより速い"]
    ),
    "spore": MoveInfo(
        name="spore", japanese_name="キノコのほうし", type="Grass", category="status",
        power=None, accuracy=100, priority=0, target="normal",
        effect="相手をねむり状態にする（命中100%）",
        key_notes=["くさタイプ・ぼうじんゴーグル・ラムのみで防がれる"]
    ),
    
    # --- テラスタル関連 ---
    "teracluster": MoveInfo(
        name="teracluster", japanese_name="テラクラスター", type="Normal", category="special",
        power=120, accuracy=100, priority=0, target="allAdjacentFoes",
        effect="テラパゴス専用。テラスタル時にステラタイプになる",
        key_notes=["ステラテラスで全タイプに等倍+威力上昇"]
    ),
    
    # --- 格闘技 ---
    "closecombat": MoveInfo(
        name="closecombat", japanese_name="インファイト", type="Fighting", category="physical",
        power=120, accuracy=100, priority=0, target="normal",
        effect="高火力だが自分の防御・特防が1段階下がる",
        key_notes=["素早さの高いアタッカー向け"]
    ),
    "drainpunch": MoveInfo(
        name="drainpunch", japanese_name="ドレインパンチ", type="Fighting", category="physical",
        power=75, accuracy=100, priority=0, target="normal",
        effect="与えたダメージの半分を回復",
        key_notes=["ガオガエンの主力技"]
    ),
    "sacredsword": MoveInfo(
        name="sacredsword", japanese_name="せいなるつるぎ", type="Fighting", category="physical",
        power=90, accuracy=100, priority=0, target="normal",
        effect="相手の能力変化を無視してダメージ計算",
        key_notes=["積み技を無視できる"]
    ),
    
    # --- あく技 ---
    "knockoff": MoveInfo(
        name="knockoff", japanese_name="はたきおとす", type="Dark", category="physical",
        power=65, accuracy=100, priority=0, target="normal",
        effect="相手の道具をはたき落とす。道具を持っていると威力1.5倍",
        key_notes=["実質威力97.5、道具破壊が強力"]
    ),
    "darkpulse": MoveInfo(
        name="darkpulse", japanese_name="あくのはどう", type="Dark", category="special",
        power=80, accuracy=100, priority=0, target="normal",
        effect="20%で怯み",
        key_notes=[]
    ),
    
    # --- ゴースト技 ---
    "shadowball": MoveInfo(
        name="shadowball", japanese_name="シャドーボール", type="Ghost", category="special",
        power=80, accuracy=100, priority=0, target="normal",
        effect="20%で特防1段階ダウン",
        key_notes=[]
    ),
    
    # --- ドラゴン技 ---
    "dracometeor": MoveInfo(
        name="dracometeor", japanese_name="りゅうせいぐん", type="Dragon", category="special",
        power=130, accuracy=90, priority=0, target="normal",
        effect="使用後、自分の特攻が2段階下がる",
        key_notes=["最高威力のドラゴン技"]
    ),
    
    # --- フェアリー技 ---
    "moonblast": MoveInfo(
        name="moonblast", japanese_name="ムーンフォース", type="Fairy", category="special",
        power=95, accuracy=100, priority=0, target="normal",
        effect="30%で相手の特攻1段階ダウン",
        key_notes=["ドラゴン・あく・かくとうに抜群"]
    ),
    "playrough": MoveInfo(
        name="playrough", japanese_name="じゃれつく", type="Fairy", category="physical",
        power=90, accuracy=90, priority=0, target="normal",
        effect="10%で相手の攻撃1段階ダウン",
        key_notes=[]
    ),
}


class MoveEffectDB:
    """
    技効果データベースサービス
    """
    
    @classmethod
    def get_move_info(cls, move_name: str) -> Optional[MoveInfo]:
        """
        技名から情報を取得
        """
        # 正規化
        key = move_name.lower().replace(" ", "").replace("-", "")
        return MOVE_DATABASE.get(key)
    
    @classmethod
    def get_relevant_effects(
        cls,
        moves: List[str],
    ) -> List[MoveInfo]:
        """
        使用可能な技のうち、重要な効果を持つものを返す
        """
        result = []
        for move in moves:
            info = cls.get_move_info(move)
            if info:
                result.append(info)
        return result
    
    @classmethod
    def get_priority_moves(cls, moves: List[str]) -> List[MoveInfo]:
        """優先度が0以外の技を抽出"""
        result = []
        for move in moves:
            info = cls.get_move_info(move)
            if info and info.priority != 0:
                result.append(info)
        return result
    
    @classmethod
    def summarize_for_llm(cls, moves: List[str]) -> str:
        """LLM用に技効果をまとめる"""
        lines = []
        
        priority_moves = cls.get_priority_moves(moves)
        if priority_moves:
            lines.append("【優先度技】")
            for m in priority_moves:
                lines.append(f"  {m.japanese_name}: 優先度{m.priority:+d}, {m.effect}")
        
        other_moves = [cls.get_move_info(move) for move in moves]
        other_moves = [m for m in other_moves if m and m.priority == 0]
        
        if other_moves:
            lines.append("【その他の重要技】")
            for m in other_moves:
                if m.key_notes:
                    notes = "; ".join(m.key_notes)
                    lines.append(f"  {m.japanese_name}: {m.effect} ({notes})")
        
        return "\n".join(lines) if lines else "技効果情報なし"


# Singleton
_move_effect_db = None

def get_move_effect_db() -> MoveEffectDB:
    global _move_effect_db
    if _move_effect_db is None:
        _move_effect_db = MoveEffectDB()
    return _move_effect_db
