import { useState, useRef, useEffect } from "react";
import ChatMessage from "./components/ChatMessage";
import ChatInput from "./components/ChatInput";
import PhaseIndicator from "./components/PhaseIndicator";
import { sendChat, analyzeImage, type ChatMessage as ChatMsg, type InspirationImage } from "./api";

interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  phase?: string;
  images?: InspirationImage[];
}

export default function App() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [history, setHistory] = useState<ChatMsg[]>([]);
  const [phase, setPhase] = useState("MASTER");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (message: string) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setLoading(true);

    try {
      const res = await sendChat(message, history);
      setPhase(res.phase);
      setHistory(res.conversation_history);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.response,
          phase: res.phase,
          images: res.inspiration_images,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error connecting to server. Is the backend running?" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleImageUpload = async (base64: string, mediaType: string) => {
    setMessages((prev) => [...prev, { role: "user", content: "[Image uploaded for analysis]" }]);
    setLoading(true);

    try {
      const res = await analyzeImage(base64, mediaType);
      setPhase(res.phase);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.analysis, phase: res.phase },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error analyzing image." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen max-w-3xl mx-auto">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white sticky top-0 z-10">
        <div>
          <h1 className="text-xl font-bold text-gray-800">
            Make<span className="text-emerald-600">It</span>Ai
          </h1>
          <p className="text-xs text-gray-400">Your AI craft mentor</p>
        </div>
        <PhaseIndicator phase={phase} />
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto px-4 py-6 space-y-1">
        {messages.length === 0 && (
          <div className="text-center mt-20">
            <div className="text-5xl mb-4">&#128736;</div>
            <h2 className="text-lg font-semibold text-gray-700 mb-2">
              Welcome to MakeItAi
            </h2>
            <p className="text-sm text-gray-400 max-w-md mx-auto">
              Ask me what to make, how to make it, upload a photo for feedback,
              or create an Etsy listing when you're done.
            </p>
            <div className="flex flex-wrap justify-center gap-2 mt-6">
              {[
                "What should I make to sell?",
                "How to make a paper flower?",
                "Help me create an Etsy listing",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  className="text-xs px-3 py-2 rounded-lg bg-white border border-gray-200 text-gray-600 hover:border-emerald-500 hover:text-emerald-600 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatMessage key={i} {...msg} />
        ))}

        {loading && (
          <div className="flex justify-start mb-4">
            <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce [animation-delay:0.1s]" />
                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce [animation-delay:0.2s]" />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      {/* Input */}
      <footer className="px-4 py-3 border-t border-gray-200 bg-white sticky bottom-0">
        <ChatInput onSend={handleSend} onImageUpload={handleImageUpload} disabled={loading} />
      </footer>
    </div>
  );
}
