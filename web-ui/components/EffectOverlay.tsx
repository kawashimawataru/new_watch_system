"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sword, Skull } from "lucide-react";

export type EffectType = "nice-play" | "danger" | "fate-turn" | "critical-hit" | "ohko" | "prediction-success" | null;

interface EffectOverlayProps {
    effect: EffectType;
}

export const EffectOverlay: React.FC<EffectOverlayProps> = ({ effect }) => {
    return (
        <AnimatePresence>
            {/* 1. Nice Play (Green/Yellow) */}
            {effect === "nice-play" && (
                <motion.div
                    key="nice-play"
                    className="absolute inset-0 z-[200] flex items-center justify-center pointer-events-none"
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 1.5, filter: "blur(10px)" }}
                    transition={{ duration: 0.4, ease: "backOut" }}
                >
                    <div className="relative">
                        <h1 className="text-6xl md:text-8xl font-black italic text-transparent bg-clip-text bg-gradient-to-r from-yellow-300 via-neon-green to-yellow-300 stroke-text drop-shadow-[0_0_30px_rgba(16,185,129,0.8)] skew-x-[-12deg]">
                            NICE READ!
                        </h1>
                    </div>
                </motion.div>
            )}

            {/* 2. Fate Turn (Calligraphy Style) */}
            {effect === "fate-turn" && (
                <motion.div
                    key="fate-turn"
                    className="absolute inset-0 z-[200] flex items-center justify-center pointer-events-none bg-black/40 backdrop-blur-[2px]"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, transition: { duration: 0.5 } }}
                >
                    <div className="relative flex flex-col items-center">
                        <motion.div
                            className="absolute -inset-20 bg-gradient-radial from-purple-600/40 to-transparent blur-3xl opacity-50"
                            animate={{ scale: [1, 1.2, 1] }}
                            transition={{ duration: 3, repeat: Infinity }}
                        />

                        {/* Calligraphy Text */}
                        <div className="relative flex flex-col items-center">
                            <motion.span
                                className="text-[120px] leading-none text-white drop-shadow-[0_0_15px_rgba(255,215,0,0.6)]"
                                style={{ fontFamily: 'var(--font-calligraphy)' }}
                                initial={{ opacity: 0, scale: 2, filter: "blur(20px)" }}
                                animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                                transition={{ duration: 0.5, ease: "circOut" }}
                            >
                                運命
                            </motion.span>
                            <motion.div
                                className="h-1 w-64 bg-gradient-to-r from-transparent via-yellow-500 to-transparent my-4"
                                initial={{ scaleX: 0 }}
                                animate={{ scaleX: 1 }}
                                transition={{ delay: 0.3, duration: 0.4 }}
                            />
                            <motion.span
                                className="text-4xl text-yellow-100 tracking-[0.5em] font-bold"
                                style={{ fontFamily: 'var(--font-geist-mono)' }}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.5, duration: 0.4 }}
                            >
                                FATE TURN
                            </motion.span>
                        </div>
                    </div>
                </motion.div>
            )}

            {/* 3. Critical Hit (Sharp, Impact) */}
            {effect === "critical-hit" && (
                <motion.div
                    key="critical-hit"
                    className="absolute inset-0 z-[200] flex items-center justify-center pointer-events-none"
                    initial={{ opacity: 0, scale: 0.5, rotate: -10 }}
                    animate={{ opacity: 1, scale: 1, rotate: 0 }}
                    exit={{ opacity: 0, scale: 1.2, rotate: 10 }}
                    transition={{ type: "spring", stiffness: 300, damping: 15 }}
                >
                    <div className="relative flex items-center justify-center">
                        {/* Starburst BG */}
                        <div className="absolute inset-0 bg-yellow-500/20 rotate-45 scale-150 blur-xl" />

                        <div className="relative flex flex-col items-center">
                            <Sword className="w-32 h-32 text-red-500 drop-shadow-[0_0_20px_red] mb-[-20px] z-10 animate-pulse" strokeWidth={2.5} />
                            <h1 className="text-8xl font-black italic text-transparent bg-clip-text bg-gradient-to-b from-yellow-200 to-red-600 stroke-text drop-shadow-[0_5px_10px_rgba(0,0,0,0.8)] -skew-x-12 z-20">
                                CRITICAL!
                            </h1>
                        </div>
                    </div>
                </motion.div>
            )}

            {/* 4. One Hit KO (Dark, Dramatic) */}
            {effect === "ohko" && (
                <motion.div
                    key="ohko"
                    className="absolute inset-0 z-[200] flex items-center justify-center pointer-events-none bg-red-900/30 mix-blend-hard-light"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                >
                    <div className="relative flex flex-col items-center gap-4">
                        <motion.div
                            initial={{ scale: 5, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            transition={{ type: "spring", stiffness: 400, damping: 20 }}
                        >
                            <Skull className="w-48 h-48 text-gray-100 drop-shadow-[0_0_50px_black]" strokeWidth={1.5} />
                        </motion.div>
                        <motion.div
                            className="bg-black text-white px-8 py-2 border-y-4 border-red-600"
                            initial={{ width: 0, opacity: 0 }}
                            animate={{ width: "auto", opacity: 1 }}
                            transition={{ delay: 0.2 }}
                        >
                            <h1 className="text-6xl font-black tracking-tighter text-red-500 animate-pulse">
                                ONE HIT KO
                            </h1>
                        </motion.div>
                    </div>
                </motion.div>
            )}

            {/* 5. Danger (Minimalist Warning) */}
            {effect === "danger" && (
                <motion.div
                    key="danger"
                    className="absolute inset-0 z-[200] pointer-events-none flex items-start justify-center pt-24"
                    initial={{ opacity: 0, y: -50 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                >
                    <div className="relative bg-red-600/90 text-white px-8 py-2 skew-x-[-20deg] border-2 border-white/20 shadow-[0_0_30px_rgba(220,38,38,0.6)] flex items-center gap-4">
                        <div className="skew-x-[20deg] flex items-center gap-3">
                            <div className="w-3 h-3 bg-white rounded-full animate-ping" />
                            <span className="text-2xl font-black tracking-[0.2em]">DANGER</span>
                        </div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};
