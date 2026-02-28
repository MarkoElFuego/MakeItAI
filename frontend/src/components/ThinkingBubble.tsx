import { useState, useEffect } from "react";

// LOTR-style thinking messages that rotate while Elfy processes
const THINKING_ANIMATIONS = [
    "🧝 Elfy is crafting...",
    "⚒️ Elfy is forging...",
    "📜 Elfy is writing the sacred scroll...",
    "🌿 Elfy is gathering ideas...",
    "✨ Elfy is dreaming up projects...",
    "🔨 Elfy is hammering out details...",
    "🧝 Elfy is preparing the workshop...",
    "🔍 Elfy is studying the craft...",
    "📸 Elfy is inspecting your work...",
    "🔧 Elfy is diagnosing the problem...",
    "💰 Elfy is researching the market...",
];

interface ThinkingBubbleProps {
    text?: string;
    isVisible: boolean;
    showCoT?: string; // Chain-of-thought text to show in expandable
}

export default function ThinkingBubble({ text, isVisible, showCoT }: ThinkingBubbleProps) {
    const [currentMsg, setCurrentMsg] = useState(text || THINKING_ANIMATIONS[0]);
    const [dots, setDots] = useState("");
    const [cotExpanded, setCotExpanded] = useState(false);

    // Rotate messages every 3 seconds
    useEffect(() => {
        if (!isVisible) return;
        if (text) {
            setCurrentMsg(text);
            return;
        }
        const interval = setInterval(() => {
            const idx = Math.floor(Math.random() * THINKING_ANIMATIONS.length);
            setCurrentMsg(THINKING_ANIMATIONS[idx]);
        }, 3000);
        return () => clearInterval(interval);
    }, [isVisible, text]);

    // Animate dots
    useEffect(() => {
        if (!isVisible) return;
        const interval = setInterval(() => {
            setDots((prev) => (prev.length >= 3 ? "" : prev + "."));
        }, 500);
        return () => clearInterval(interval);
    }, [isVisible]);

    if (!isVisible) return null;

    return (
        <div className="thinking-bubble">
            <div className="thinking-bubble-content">
                <div className="thinking-dots">
                    <span className="dot" />
                    <span className="dot" />
                    <span className="dot" />
                </div>
                <span className="thinking-text">
                    {currentMsg}{dots}
                </span>
            </div>

            {showCoT && (
                <div className="thinking-cot">
                    <button
                        className="cot-toggle"
                        onClick={() => setCotExpanded(!cotExpanded)}
                    >
                        {cotExpanded ? "▼ Hide reasoning" : "▶ Show Elfy's reasoning"}
                    </button>
                    {cotExpanded && (
                        <div className="cot-content">
                            {showCoT}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
