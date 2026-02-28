import { useState, useRef, useEffect } from "react";
import ChatMessage from "./components/ChatMessage";
import ChatInput from "./components/ChatInput";
import TutorialCanvas from "./components/TutorialCanvas";
import ThinkingBubble from "./components/ThinkingBubble";
import {
  sendChatStream,
  sendChat,
  analyzeImage,
  type ChatMessage as ChatMsg,
  type TutorialData,
} from "./api";

interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  uploadedImage?: string;
  action?: string;
  thinking?: string;
}

const ALL_OCCASIONS = [
  { emoji: "🎂", label: "Birthday" },
  { emoji: "🎄", label: "Christmas" },
  { emoji: "💝", label: "Valentine's" },
  { emoji: "🏠", label: "Home Decor" },
  { emoji: "🎁", label: "Gift Idea" },
  { emoji: "✨", label: "Just for Fun" },
];

function getRandomOccasions(count: number) {
  const shuffled = [...ALL_OCCASIONS].sort(() => 0.5 - Math.random());
  return shuffled.slice(0, count);
}

export default function App() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [history, setHistory] = useState<ChatMsg[]>([]);
  const [tutorialData, setTutorialData] = useState<TutorialData | null>(null);
  const [latestImage, setLatestImage] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [thinkingText, setThinkingText] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [occasions, setOccasions] = useState(ALL_OCCASIONS.slice(0, 3));

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setOccasions(getRandomOccasions(3));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, streamingContent]);

  // ── Streaming Send ──────────────────────────────────────────
  const handleSend = async (message: string) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setLoading(true);
    setThinkingText("");
    setStreamingContent("");

    try {
      await sendChatStream(
        message,
        {
          onThinking: (text) => {
            setThinkingText(text);
          },
          onToken: (text) => {
            setLoading(false); // Stop thinking, start streaming
            setStreamingContent((prev) => prev + text);
          },
          onDone: (data) => {
            setStreamingContent(""); // Clear streaming buffer

            if (data.tutorial_data) {
              setTutorialData(data.tutorial_data);
            }
            setHistory(data.conversation_history || []);

            if (data.response) {
              setMessages((prev) => [
                ...prev,
                {
                  role: "assistant",
                  content: data.response,
                  action: data.action,
                  thinking: data.thinking,
                },
              ]);
            }
            setLoading(false);
          },
          onError: () => {
            // Fallback to non-streaming
            handleSendFallback(message);
          },
        },
        history,
        {},
        tutorialData,
      );
    } catch {
      handleSendFallback(message);
    }
  };

  // Fallback for when streaming fails
  const handleSendFallback = async (message: string) => {
    try {
      const res = await sendChat(message, history, {}, tutorialData, latestImage);
      if (res.tutorial_data) setTutorialData(res.tutorial_data);
      setHistory(res.conversation_history);
      if (res.response) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: res.response, action: res.action },
        ]);
      }
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
    const dataUri = `data:${mediaType};base64,${base64}`;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: "I uploaded this image:", uploadedImage: dataUri },
    ]);
    setLoading(true);
    setThinkingText("🔍 Elfy is studying the craft...");

    try {
      const res = await analyzeImage(base64, mediaType);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.analysis, action: "analyze_node" },
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

  const handleAskHelp = (_stepIndex: number, question: string) => {
    const cleanMsg = question.includes("|") ? question.split("|").pop()!.trim() : question;
    setMessages((prev) => [...prev, { role: "user", content: cleanMsg }]);
    handleSend(question);
  };

  const handleTutorialComplete = () => {
    // Trigger market surprise!
    handleSend("I just finished my project! 🎉");
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-logo">
          Elfy <span className="logo-accent">✿</span>
        </div>
        <div className="header-badge">🧝 Premium</div>
      </header>

      {/* Main Content */}
      <main className="app-main">
        {/* Welcome Screen */}
        {messages.length === 0 && !tutorialData && (
          <div className="welcome-screen">
            <h2 className="welcome-title">Hi! I'm Elfy</h2>
            <p className="welcome-subtitle">
              Your AI craft companion. What are we making today?
            </p>
            <div className="occasion-buttons">
              {occasions.map((o) => (
                <button
                  key={o.label}
                  onClick={() => handleSend(`I want to make something for ${o.label}`)}
                  className="occasion-btn"
                >
                  {o.emoji} {o.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="messages-container">
          {messages.map((msg, i) => (
            <div key={i}>
              <ChatMessage {...msg} onQuickReply={handleSend} />
              {msg.action === "tutorial_gen_node" && tutorialData && (
                <div className="fade-in tutorial-inline">
                  <TutorialCanvas
                    tutorialData={tutorialData}
                    onAskHelp={handleAskHelp}
                    onComplete={handleTutorialComplete}
                  />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Streaming content (text appearing word by word) */}
        {streamingContent && (
          <div className="streaming-message">
            <div className="chat-bubble assistant">
              {streamingContent}
              <span className="cursor-blink">|</span>
            </div>
          </div>
        )}

        {/* Thinking Bubble */}
        <ThinkingBubble
          text={thinkingText}
          isVisible={loading}
        />

        <div ref={bottomRef} />
      </main>

      {/* Input Footer */}
      <footer className="app-footer">
        <ChatInput
          onSend={handleSend}
          onImageUpload={handleImageUpload}
          disabled={loading}
        />
      </footer>
    </div>
  );
}
