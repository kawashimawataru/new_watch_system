"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/GlassCard";
import { motion } from "framer-motion";
import { BrainCircuit, ChevronRight } from "lucide-react";

interface ReasoningViewProps {
    thoughtProcess: string;
    turn: number;
    currentSituation?: string;  // 現在の状況説明
    topCandidateReason?: string;  // トップ候補の理由
    riskAnalysis?: string;  // リスク分析
    className?: string;
}

export const ReasoningView: React.FC<ReasoningViewProps> = ({ 
    thoughtProcess, 
    turn, 
    currentSituation,
    topCandidateReason,
    riskAnalysis,
    className 
}) => {
    return (
        <GlassCard className={cn("flex flex-col h-full", className)} noPadding variant="cyber-blue">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-black/20">
                <h3 className="text-xs font-bold text-neon-blue tracking-widest uppercase flex items-center gap-2">
                    <BrainCircuit className="w-4 h-4" />
                    Strategic Intelligence
                </h3>
                <span className="text-[10px] text-gray-500 font-mono">LOG: TURN_{turn}</span>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-xs leading-relaxed text-gray-300">
                {currentSituation && (
                    <div className="flex items-start gap-2">
                        <ChevronRight className="w-3 h-3 text-neon-green mt-0.5 shrink-0" />
                        <div>
                            <h4 className="text-neon-green font-bold mb-1">Situation Analysis</h4>
                            <p>{currentSituation}</p>
                        </div>
                    </div>
                )}

                {riskAnalysis && (
                    <div className="flex items-start gap-2">
                        <ChevronRight className="w-3 h-3 text-neon-blue mt-0.5 shrink-0" />
                        <div>
                            <h4 className="text-neon-blue font-bold mb-1">Risk Assessment</h4>
                            <p>{riskAnalysis}</p>
                        </div>
                    </div>
                )}

                {topCandidateReason && (
                    <div className="flex items-start gap-2">
                        <ChevronRight className="w-3 h-3 text-purple-400 mt-0.5 shrink-0" />
                        <div>
                            <h4 className="text-purple-400 font-bold mb-1">Top Candidate Reason</h4>
                            <p>{topCandidateReason}</p>
                        </div>
                    </div>
                )}

                <div className="flex items-start gap-2">
                    <ChevronRight className="w-3 h-3 text-neon-rose mt-0.5 shrink-0" />
                    <div>
                        <h4 className="text-neon-rose font-bold mb-1">Conclusion</h4>
                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ duration: 0.5 }}
                            className="typing-effect"
                        >
                            {thoughtProcess}
                        </motion.p>
                    </div>
                </div>
            </div>
        </GlassCard>
    );
};
