"use client";

import React, { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface WinRateBarProps {
    p1WinRate: number; // 0-100
    p1Name?: string;
    p2Name?: string;
    className?: string;
}

export const WinRateBar: React.FC<WinRateBarProps> = ({
    p1WinRate,
    p1Name = "PLAYER 1",
    p2Name = "PLAYER 2",
    className
}) => {
    const p2WinRate = 100 - p1WinRate;
    const rootRef = useRef<HTMLDivElement>(null);
    const percentageRef = useRef<HTMLDivElement>(null);
    const barRef = useRef<HTMLDivElement>(null);

    // #region agent log
    useEffect(() => {
        const measure = () => {
            if (rootRef.current) {
                const rect = rootRef.current.getBoundingClientRect();
                fetch('http://127.0.0.1:7242/ingest/3375475e-c3d2-4387-93c1-d0dfa2e31d70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'WinRateBar.tsx:useEffect',message:'WinRateBar root dimensions',data:{height:rect.height,top:rect.top,bottom:rect.bottom,width:rect.width},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch((e)=>console.error('Debug log error:',e));
            }
            if (percentageRef.current) {
                const rect = percentageRef.current.getBoundingClientRect();
                const styles = window.getComputedStyle(percentageRef.current);
                fetch('http://127.0.0.1:7242/ingest/3375475e-c3d2-4387-93c1-d0dfa2e31d70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'WinRateBar.tsx:useEffect',message:'Percentage numbers container',data:{height:rect.height,top:rect.top,bottom:rect.bottom,marginBottom:styles.marginBottom,zIndex:styles.zIndex,position:styles.position},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch((e)=>console.error('Debug log error:',e));
            }
            if (barRef.current) {
                const rect = barRef.current.getBoundingClientRect();
                fetch('http://127.0.0.1:7242/ingest/3375475e-c3d2-4387-93c1-d0dfa2e31d70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'WinRateBar.tsx:useEffect',message:'Bar container dimensions',data:{height:rect.height,top:rect.top,bottom:rect.bottom},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch((e)=>console.error('Debug log error:',e));
            }
        };
        const timeoutId = setTimeout(measure, 100);
        return () => clearTimeout(timeoutId);
    }, [p1WinRate]);
    // #endregion

    return (
        <div 
            ref={rootRef}
            className={cn("w-full flex flex-col pointer-events-none select-none", className)}
        >
            {/* Percentage Numbers */}
            {/* #region agent log */}
            <div 
                ref={percentageRef}
                className="flex justify-between items-end px-4 mb-2 z-10 relative"
            >
                <div className="flex flex-col items-start drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)]">
                    <span className="text-6xl font-black italic text-white tracking-tighter" style={{ fontFamily: 'var(--font-geist-sans), sans-serif' }}>
                        {p1WinRate.toFixed(0)}<span className="text-3xl">%</span>
                    </span>
                </div>

                {/* Center Label */}
                <div className="mb-4 bg-blue-600/90 text-white px-6 py-1 rounded-t-lg skew-x-[-20deg] border-t border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.5)]">
                    <div className="skew-x-[20deg] font-bold italic tracking-wider text-sm flex items-center gap-2">
                        <span>PBS</span>
                        <span className="text-blue-200">形勢判断</span>
                    </div>
                </div>

                <div className="flex flex-col items-end drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)]">
                    <span className="text-6xl font-black italic text-white tracking-tighter" style={{ fontFamily: 'var(--font-geist-sans), sans-serif' }}>
                        {p2WinRate.toFixed(0)}<span className="text-3xl">%</span>
                    </span>
                </div>
            </div>
            {/* #endregion */}

            {/* The Bar */}
            {/* #region agent log */}
            <div 
                ref={barRef}
                className="h-8 w-full flex relative overflow-hidden ring-1 ring-white/20 shadow-2xl"
            >
                {/* P1 Side (Red/Pink gradient based on image) */}
                <motion.div
                    className="h-full bg-gradient-to-r from-[#800000] via-[#c00000] to-[#ff0040] relative"
                    initial={{ width: "50%" }}
                    animate={{ width: `${p1WinRate}%` }}
                    transition={{ duration: 1, ease: "circOut" }}
                >
                    {/* Gloss */}
                    <div className="absolute top-0 left-0 w-full h-[50%] bg-white/20" />

                    {/* Arrow/Chevron Effect at endpoint */}
                    <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-black/20 to-transparent" />
                </motion.div>

                {/* P2 Side (Blue gradient) */}
                <motion.div
                    className="h-full flex-1 bg-gradient-to-l from-[#000060] via-[#0000a0] to-[#0040ff] relative"
                >
                    {/* Gloss */}
                    <div className="absolute top-0 left-0 w-full h-[50%] bg-white/20" />
                </motion.div>

                {/* Divider */}
                <div className="absolute top-0 bottom-0 w-1 bg-white left-1/2 -translate-x-1/2 z-20 shadow-[0_0_10px_white]" />
            </div>
            {/* #endregion */}
        </div>
    );
};
