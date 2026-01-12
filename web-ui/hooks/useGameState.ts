"use client";

import { useState, useEffect, useRef } from "react";

// Types matching backend data structure
interface ActivePokemon {
    name: string;
    hp: number;
    status?: "burn" | "paralysis" | "freeze" | "sleep" | "poison" | "toxic" | null;
    atkBoost?: number;
    defBoost?: number;
    spaBoost?: number;
    spdBoost?: number;
    speBoost?: number;
}

interface PlayerInfo {
    name: string;
    rating: number;
    pokemon: string[];
    activePokemon?: ActivePokemon[];
}

interface CandidateMove {
    move1: string;
    target1: string;
    type1: string;
    move2: string;
    target2: string;
    type2: string;
    score: number;
    // Phase 24: Damage preview
    damagePreview1?: {
        minPercent: number;
        maxPercent: number;
        koChance: number;
        nHitsToKo: number;
    };
    damagePreview2?: {
        minPercent: number;
        maxPercent: number;
        koChance: number;
        nHitsToKo: number;
    };
}

interface Explanation {
    playerStrategy: string;
    opponentThreat: string;
}

interface WinRatePoint {
    turn: number;
    winRate: number;
}

// Phase 24: Field conditions for battle mechanics
interface FieldConditions {
    weather?: "sun" | "rain" | "sand" | "snow" | null;
    terrain?: "electric" | "grassy" | "psychic" | "misty" | null;
    playerTailwind?: boolean;
    opponentTailwind?: boolean;
    trickRoom?: boolean;
    playerReflect?: boolean;
    playerLightScreen?: boolean;
    opponentReflect?: boolean;
    opponentLightScreen?: boolean;
}

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
    explanation: Explanation;
    fieldConditions?: FieldConditions;  // Phase 24
}

interface UseGameStateReturn {
    isConnected: boolean;
    gameState: GameState | null;
    winRateHistory: WinRatePoint[];
    candidates: {
        p1: CandidateMove[];
        p2: CandidateMove[];
    } | null;
    explanation: Explanation | null;
    fieldConditions: FieldConditions | null;  // Phase 24
}

const WEBSOCKET_URL = "ws://localhost:8000/ws/spectator";

export function useGameState(): UseGameStateReturn {
    const [isConnected, setIsConnected] = useState(false);
    const [gameState, setGameState] = useState<GameState | null>(null);
    const [winRateHistory, setWinRateHistory] = useState<WinRatePoint[]>([]);
    const [candidates, setCandidates] = useState<{ p1: CandidateMove[], p2: CandidateMove[] } | null>(null);
    const [explanation, setExplanation] = useState<Explanation | null>(null);
    const [fieldConditions, setFieldConditions] = useState<FieldConditions | null>(null);  // Phase 24

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        connect();
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
        };
    }, []);

    const connect = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        console.log("Connecting to WebSocket...", WEBSOCKET_URL);
        const ws = new WebSocket(WEBSOCKET_URL);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log("WebSocket Connected");
            setIsConnected(true);
        };

        ws.onclose = () => {
            console.log("WebSocket Disconnected");
            setIsConnected(false);
            // 再接続試行 (3秒後)
            reconnectTimeoutRef.current = setTimeout(() => {
                connect();
            }, 3000);
        };

        ws.onerror = () => {
            // Keep error log quiet for connection refused (common during startup)
            console.warn("WebSocket Connection Error (Server likely offline)");
            ws.close(); // Triggers onclose
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                if (message.type === "game_update") {
                    const data = message.data as GameState;
                    setGameState(data);

                    // 勝率履歴更新 (バックエンドから送られてくる場合はそれを使用)
                    if (data.winRateHistory && data.winRateHistory.length > 0) {
                        setWinRateHistory(data.winRateHistory);
                    } else {
                        // フォールバック: ローカルで追跡
                        setWinRateHistory((prev) => {
                            const existingIndex = prev.findIndex((p) => p.turn === data.turn);
                            if (existingIndex !== -1) {
                                const newHistory = [...prev];
                                newHistory[existingIndex] = { turn: data.turn, winRate: data.winRate };
                                return newHistory;
                            } else {
                                return [...prev, { turn: data.turn, winRate: data.winRate }].sort((a, b) => a.turn - b.turn);
                            }
                        });
                    }

                    // 候補手の更新
                    if (data.candidates) {
                        setCandidates(data.candidates);
                    }

                    // 解説の更新
                    if (data.explanation) {
                        setExplanation(data.explanation);
                    }

                    // Phase 24: フィールド状態の更新
                    if (data.fieldConditions) {
                        setFieldConditions(data.fieldConditions);
                    }
                }
            } catch (e) {
                console.error("Message Parse Error:", e);
            }
        };
    };

    return {
        isConnected,
        gameState,
        winRateHistory,
        candidates,
        explanation,
        fieldConditions,  // Phase 24
    };
}

// Export types for use in components
export type { GameState, PlayerInfo, CandidateMove, Explanation, WinRatePoint, ActivePokemon };
