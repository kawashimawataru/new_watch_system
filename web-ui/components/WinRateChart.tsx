"use client";

import React from "react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
    Area,
    AreaChart,
    ComposedChart
} from "recharts";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/GlassCard";

export interface WinRatePoint {
    turn: number;
    winRate: number; // 0.0 to 1.0 or 0 to 100
}

interface WinRateChartProps {
    data: WinRatePoint[];
    className?: string;
}

export const WinRateChart: React.FC<WinRateChartProps> = ({ data, className }) => {
    // Normalize
    const normalizedData = data.map((d) => ({
        ...d,
        winRate: d.winRate <= 1.0 ? d.winRate * 100 : d.winRate,
    }));

    return (
        <GlassCard className={cn("flex flex-col h-full", className)} noPadding variant="cyber-blue">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-black/20">
                <h3 className="text-xs font-bold text-neon-blue tracking-widest uppercase">
                    Win Prediction
                </h3>
                <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-neon-green" />
                    <span className="text-[10px] text-gray-400 font-mono">AI CONFIDENCE</span>
                </div>
            </div>

            <div className="flex-1 w-full min-h-0 pl-0 pr-4 pt-4 pb-2">
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={normalizedData}>
                        <defs>
                            <linearGradient id="colorWinRate" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                        <XAxis
                            dataKey="turn"
                            stroke="#6b7280"
                            tick={{ fontSize: 10, fontFamily: 'monospace' }}
                            tickLine={false}
                            axisLine={false}
                        />
                        <YAxis
                            domain={[0, 100]}
                            stroke="#6b7280"
                            tick={{ fontSize: 10, fontFamily: 'monospace' }}
                            tickLine={false}
                            axisLine={false}
                            unit="%"
                            width={35}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: "rgba(5, 11, 20, 0.9)",
                                border: "1px solid rgba(16, 185, 129, 0.3)",
                                borderRadius: "4px",
                                color: "#e5e7eb",
                                fontFamily: "monospace",
                                fontSize: "12px",
                                backdropFilter: "blur(4px)"
                            }}
                            formatter={(value: number) => [`${value.toFixed(1)}%`, "Win Rate"]}
                            labelStyle={{ color: "#9ca3af" }}
                        />
                        <ReferenceLine y={50} stroke="#4B5563" strokeDasharray="5 5" />
                        <Area
                            type="monotone"
                            dataKey="winRate"
                            stroke="none"
                            fillOpacity={1}
                            fill="url(#colorWinRate)"
                        />
                        <Line
                            type="monotone"
                            dataKey="winRate"
                            stroke="#10b981"
                            strokeWidth={2}
                            dot={{ r: 3, fill: "#050b14", stroke: "#10b981", strokeWidth: 2 }}
                            activeDot={{ r: 5, fill: "#10b981" }}
                            animationDuration={500}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </GlassCard>
    );
};
