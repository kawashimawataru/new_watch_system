"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/GlassCard";
import { motion } from "framer-motion";

export interface CandidateMove {
    move: string;
    score: number;
    type: string; // "attack", "protect", "switch"
    reasoning?: string;
}

interface CandidateListProps {
    candidates: CandidateMove[];
    className?: string;
}

export const CandidateList: React.FC<CandidateListProps> = ({ candidates, className }) => {
    return (
        <GlassCard className={cn("flex flex-col h-full", className)} noPadding variant="cyber-blue">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-black/20">
                <h3 className="text-xs font-bold text-neon-blue tracking-widest uppercase flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-neon-blue animate-pulse-fast rounded-full" />
                    AI Candidates
                </h3>
                <span className="text-[10px] text-gray-500 font-mono">SCANNING...</span>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
                {candidates.map((cand, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, x: 10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className="group flex flex-col gap-1 bg-white/5 hover:bg-white/10 p-2 rounded border border-white/5 hover:border-neon-blue/30 transition-all cursor-default"
                    >
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <span className={cn(
                                    "px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider font-mono",
                                    cand.type === "protect" ? "bg-blue-500/20 text-blue-300 border border-blue-500/30" :
                                        cand.type === "switch" ? "bg-purple-500/20 text-purple-300 border border-purple-500/30" :
                                            "bg-red-500/20 text-red-300 border border-red-500/30"
                                )}>
                                    {cand.type}
                                </span>
                                <span className="font-mono text-xs text-gray-200 group-hover:text-white transition-colors">
                                    {cand.move}
                                </span>
                            </div>
                            <div className="flex flex-col items-end">
                                <div className="flex items-baseline gap-0.5">
                                    <span className="text-sm font-bold text-neon-green tabular-nums">
                                        {cand.score.toFixed(1)}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {cand.reasoning && (
                            <div className="relative pl-2 border-l border-gray-700">
                                <p className="text-[10px] text-gray-400 font-mono leading-tight line-clamp-2">
                                    {cand.reasoning}
                                </p>
                            </div>
                        )}
                    </motion.div>
                ))}

                {candidates.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-8 text-gray-500 gap-2">
                        <div className="w-8 h-8 border-2 border-t-neon-blue border-r-transparent border-b-transparent border-l-transparent rounded-full animate-spin" />
                        <span className="text-xs font-mono">Calculating...</span>
                    </div>
                )}
            </div>
        </GlassCard>
    );
};
