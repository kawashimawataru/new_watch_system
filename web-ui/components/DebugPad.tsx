"use client";

import React, { useState } from "react";
import { GlassCard } from "@/components/ui/GlassCard";
import { Settings, Sparkles, AlertTriangle, RefreshCw, Star, Sword, Skull } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { EffectType } from "./EffectOverlay";

interface DebugPadProps {
    onTriggerEffect: (effect: EffectType) => void;
    onUpdateData: () => void;
}

export const DebugPad: React.FC<DebugPadProps> = ({ onTriggerEffect, onUpdateData }) => {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div className="fixed bottom-6 right-6 z-[100] flex flex-col items-end gap-2">
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 20, scale: 0.9 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 10, scale: 0.9 }}
                        className="flex flex-col gap-2 mb-2"
                    >
                        <GlassCard className="p-2 gap-1 flex flex-col min-w-[180px]" variant="cyber-blue">
                            <div className="text-[10px] text-gray-500 font-mono uppercase border-b border-white/5 pb-1 mb-1">
                                Events
                            </div>
                            <button
                                onClick={() => onTriggerEffect("nice-play")}
                                className="flex items-center gap-2 px-3 py-1.5 text-xs text-neon-green hover:bg-neon-green/10 rounded transition-colors text-left"
                            >
                                <Sparkles className="w-3 h-3" /> Nice Play
                            </button>
                            <button
                                onClick={() => onTriggerEffect("fate-turn")}
                                className="flex items-center gap-2 px-3 py-1.5 text-xs text-yellow-400 hover:bg-yellow-400/10 rounded transition-colors text-left"
                            >
                                <Star className="w-3 h-3" /> Fate Turn (運命)
                            </button>
                            <button
                                onClick={() => onTriggerEffect("critical-hit")}
                                className="flex items-center gap-2 px-3 py-1.5 text-xs text-orange-500 hover:bg-orange-500/10 rounded transition-colors text-left"
                            >
                                <Sword className="w-3 h-3" /> Critical Hit!
                            </button>
                            <button
                                onClick={() => onTriggerEffect("ohko")}
                                className="flex items-center gap-2 px-3 py-1.5 text-xs text-red-500 hover:bg-red-500/10 rounded transition-colors text-left"
                            >
                                <Skull className="w-3 h-3" /> One Hit KO
                            </button>
                            <button
                                onClick={() => onTriggerEffect("danger")}
                                className="flex items-center gap-2 px-3 py-1.5 text-xs text-neon-rose hover:bg-neon-rose/10 rounded transition-colors text-left"
                            >
                                <AlertTriangle className="w-3 h-3" /> Danger Mode
                            </button>

                            <div className="text-[10px] text-gray-500 font-mono uppercase border-b border-white/5 pb-1 mb-1 mt-2">
                                System
                            </div>
                            <button
                                onClick={onUpdateData}
                                className="flex items-center gap-2 px-3 py-1.5 text-xs text-neon-blue hover:bg-neon-blue/10 rounded transition-colors text-left"
                            >
                                <RefreshCw className="w-3 h-3" /> Update Data
                            </button>
                        </GlassCard>
                    </motion.div>
                )}
            </AnimatePresence>

            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-12 h-12 rounded-full bg-black/80 border border-neon-blue/50 text-neon-blue flex items-center justify-center hover:bg-neon-blue/20 hover:scale-105 active:scale-95 transition-all shadow-[0_0_20px_rgba(14,165,233,0.3)]"
            >
                <Settings className={`w-6 h-6 transition-transform ${isOpen ? "rotate-90" : ""}`} />
            </button>
        </div>
    );
};
