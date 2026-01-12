"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { ShieldAlert, Swords, X, Target } from "lucide-react";

import { BattleConditionsPanel } from "./BattleConditionsPanel";

interface VisualReasoningViewProps {
    p1Pokemon: string[];
    p2Pokemon: string[];
    playerStrategy?: string;
    opponentThreat?: string;
    currentSituation?: string;  // 現在の状況説明
    topCandidateReason?: string;  // トップ候補の理由
    riskAnalysis?: string;  // リスク分析
    battleType?: "single" | "double";  // バトル形式
    fieldConditions?: any; // Phase 25
    className?: string;
    onClose?: () => void;
}

export const VisualReasoningView: React.FC<VisualReasoningViewProps> = ({
    p1Pokemon,
    p2Pokemon,
    playerStrategy = "分析中...",
    opponentThreat = "相手の動きを予測中...",
    currentSituation,
    topCandidateReason,
    riskAnalysis,
    battleType = "double",
    fieldConditions,
    className,
    onClose
}) => {
    const isSingle = battleType === "single";
    const activeP1 = isSingle ? p1Pokemon.slice(0, 1) : p1Pokemon.slice(0, 2);
    const activeP2 = isSingle ? p2Pokemon.slice(0, 1) : p2Pokemon.slice(0, 2);

    // Shortened names for display
    const shortenName = (name: string) => name.substring(0, 5);

    return (
        <div className={cn("w-full h-full bg-black/95 backdrop-blur-md flex flex-col p-4 relative", className)}>
            {/* Close Button */}
            {onClose && (
                <button
                    onClick={onClose}
                    className="absolute top-3 right-3 p-1.5 bg-white/10 hover:bg-white/20 rounded-full z-50 text-white transition-colors"
                    title="閉じる"
                >
                    <X className="w-5 h-5" />
                </button>
            )}

            <div className="text-center border-b border-white/10 pb-2 mb-2 shadow-sm shrink-0 flex flex-col items-center gap-2">
                <h3 className="text-lg font-bold text-yellow-500 tracking-widest uppercase flex items-center justify-center gap-2">
                    <Swords className="w-5 h-5" />
                    戦術交差図解 (Tactical Diagram)
                </h3>

                {/* Field Conditions Panel */}
                {fieldConditions && (
                    <BattleConditionsPanel conditions={fieldConditions} className="scale-90" />
                )}
            </div>

            <div className="flex-1 flex items-center justify-between gap-16 px-20 relative min-h-0 bg-cyber-grid/20 rounded-lg border border-white/5 my-2">

                {/* Left Side (Self) */}
                <div className="flex flex-col gap-12 justify-center z-10">
                    <div className="text-center mb-[-15px]">
                        <span className="text-xs text-green-400 font-bold border border-green-500/50 px-3 py-0.5 rounded-full bg-green-500/10 tracking-wider">PLAYER SIDE</span>
                    </div>
                    {activeP1.map((poke, i) => (
                        <motion.div
                            key={i}
                            className="w-20 h-20 rounded-full border-[3px] border-green-500 bg-gray-900 flex items-center justify-center relative shadow-[0_0_20px_rgba(34,197,94,0.4)] group cursor-help transition-transform hover:scale-110"
                            initial={{ x: -30, opacity: 0 }}
                            animate={{ x: 0, opacity: 1 }}
                            transition={{ delay: i * 0.1 }}
                        >
                            <span className="text-xs font-bold text-center leading-none px-1">{shortenName(poke)}</span>
                        </motion.div>
                    ))}
                </div>

                {/* Arrows Layer (Bidirectional) */}
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <svg className="w-full h-full absolute inset-0">
                        <defs>
                            <marker id="arrow-p1-atk-lg" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                                <polygon points="0 0, 10 3.5, 0 7" fill="#ef4444" />
                            </marker>
                            <marker id="arrow-p2-atk-lg" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                                <polygon points="0 0, 10 3.5, 0 7" fill="#3b82f6" />
                            </marker>
                        </defs>

                        {/* P1 Actions (Red) */}
                        <motion.path
                            d="M 280 80 Q 500 50 720 80"
                            fill="none"
                            stroke="#ef4444"
                            strokeWidth="3"
                            markerEnd="url(#arrow-p1-atk-lg)"
                            vectorEffect="non-scaling-stroke"
                            initial={{ pathLength: 0 }}
                            animate={{ pathLength: 1 }}
                            transition={{ duration: 0.8, delay: 0.3 }}
                        />
                        <foreignObject x="40%" y="30" width="100" height="30">
                            <div className="bg-red-900/90 text-red-100 text-[10px] font-bold px-2 py-0.5 rounded text-center border border-red-500 shadow-md">
                                攻撃優先
                            </div>
                        </foreignObject>

                        {/* P2 Actions (Blue) */}
                        <motion.path
                            d="M 720 80 Q 500 130 280 180"
                            fill="none"
                            stroke="#3b82f6"
                            strokeWidth="3"
                            strokeDasharray="4,2"
                            markerEnd="url(#arrow-p2-atk-lg)"
                            vectorEffect="non-scaling-stroke"
                            initial={{ pathLength: 0 }}
                            animate={{ pathLength: 1 }}
                            transition={{ duration: 0.8, delay: 0.6 }}
                        />
                        <foreignObject x="60%" y="120" width="100" height="30">
                            <div className="bg-blue-900/90 text-blue-100 text-[10px] font-bold px-2 py-0.5 rounded text-center border border-blue-500 shadow-md">
                                集中狙い
                            </div>
                        </foreignObject>
                    </svg>
                </div>

                {/* Right Side (Opponent) */}
                <div className="flex flex-col gap-12 justify-center z-10">
                    <div className="text-center mb-[-15px]">
                        <span className="text-xs text-red-400 font-bold border border-red-500/50 px-3 py-0.5 rounded-full bg-red-500/10 tracking-wider">OPPONENT SIDE</span>
                    </div>
                    {activeP2.map((poke, i) => (
                        <motion.div
                            key={i}
                            className="w-20 h-20 rounded-full border-[3px] border-red-500 bg-gray-900 flex items-center justify-center relative shadow-[0_0_20px_rgba(239,68,68,0.4)] group cursor-help transition-transform hover:scale-110"
                            initial={{ x: 30, opacity: 0 }}
                            animate={{ x: 0, opacity: 1 }}
                            transition={{ delay: 0.1 + i * 0.1 }}
                        >
                            <span className="text-xs font-bold text-center leading-none px-1">{shortenName(poke)}</span>
                            {i === 0 && (
                                <div className="absolute -top-5 left-1/2 -translate-x-1/2 animate-bounce">
                                    <Target className="w-6 h-6 text-yellow-500 drop-shadow-md" />
                                </div>
                            )}
                        </motion.div>
                    ))}
                </div>
            </div>

            {/* Dual Perspective Explanation - Dynamic from props */}
            <div className="mt-2 flex flex-col gap-2 shrink-0 max-h-[200px] overflow-y-auto">
                {/* Current Situation */}
                {currentSituation && (
                    <div className="bg-yellow-900/10 border border-yellow-500/30 rounded-lg p-2">
                        <h4 className="text-xs font-bold text-yellow-400 mb-1 flex items-center gap-2">
                            <span className="flex w-2 h-2 rounded-full bg-yellow-500 shadow-[0_0_5px_yellow]" />
                            現在の状況
                        </h4>
                        <p className="text-[11px] text-gray-200 leading-snug">
                            {currentSituation}
                        </p>
                    </div>
                )}
                
                <div className="flex gap-4">
                    {/* Player Logic */}
                    <div className="flex-1 bg-green-900/10 border border-green-500/30 rounded-lg p-3 overflow-y-auto hover:bg-green-900/20 transition-colors">
                        <h4 className="text-xs font-bold text-green-400 mb-1 flex items-center gap-2">
                            <span className="flex w-2 h-2 rounded-full bg-green-500 shadow-[0_0_5px_lime]" />
                            PLAYER STRATEGY
                        </h4>
                        <p className="text-[11px] text-gray-200 leading-snug">
                            {playerStrategy}
                        </p>
                    </div>

                    {/* Opponent Anticipation */}
                    <div className="flex-1 bg-blue-900/10 border border-blue-500/30 rounded-lg p-3 overflow-y-auto hover:bg-blue-900/20 transition-colors">
                        <h4 className="text-xs font-bold text-blue-400 mb-1 flex items-center gap-2">
                            <span className="flex w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_5px_cyan]" />
                            OPPONENT THREAT
                        </h4>
                        <p className="text-[11px] text-gray-200 leading-snug">
                            {opponentThreat}
                        </p>
                    </div>
                </div>
                
                {/* Additional Analysis */}
                {(topCandidateReason || riskAnalysis) && (
                    <div className="flex gap-4">
                        {topCandidateReason && (
                            <div className="flex-1 bg-purple-900/10 border border-purple-500/30 rounded-lg p-2">
                                <h4 className="text-xs font-bold text-purple-400 mb-1 flex items-center gap-2">
                                    <span className="flex w-2 h-2 rounded-full bg-purple-500 shadow-[0_0_5px_purple]" />
                                    トップ候補の理由
                                </h4>
                                <p className="text-[11px] text-gray-200 leading-snug">
                                    {topCandidateReason}
                                </p>
                            </div>
                        )}
                        {riskAnalysis && (
                            <div className="flex-1 bg-red-900/10 border border-red-500/30 rounded-lg p-2">
                                <h4 className="text-xs font-bold text-red-400 mb-1 flex items-center gap-2">
                                    <span className="flex w-2 h-2 rounded-full bg-red-500 shadow-[0_0_5px_red]" />
                                    リスク分析
                                </h4>
                                <p className="text-[11px] text-gray-200 leading-snug">
                                    {riskAnalysis}
                                </p>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
