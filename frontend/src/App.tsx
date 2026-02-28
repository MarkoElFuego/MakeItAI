import { useState, useRef, useEffect } from "react";
import ChatMessage from "./components/ChatMessage";
import ChatInput from "./components/ChatInput";
import TutorialCanvas from "./components/TutorialCanvas";
import {
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
  const [statusText, setStatusText] = useState("Elfy is thinking...");
  const [occasions, setOccasions] = useState(ALL_OCCASIONS.slice(0, 3));

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setOccasions(getRandomOccasions(3));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (message: string) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setLoading(true);
    setStatusText("Elfy is thinking...");

    try {
      const res = await sendChat(message, history, {}, tutorialData, latestImage);

      if (res.tutorial_data) {
        setTutorialData(res.tutorial_data);
      }
      if (res.generated_image) {
        setLatestImage(res.generated_image);
      }

      setHistory(res.conversation_history);

      // Add response
      if (res.response) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: res.response,
            action: res.action,
          },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Error connecting to server. Is the backend running?",
        },
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
    setStatusText("Elfy is analyzing...");

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
    // Show clean message in chat but send full metadata to backend
    const cleanMsg = question.includes("|") ? question.split("|").pop()!.trim() : question;
    setMessages((prev) => [...prev, { role: "user", content: cleanMsg }]);
    setLoading(true);
    setStatusText("Elfy is thinking...");

    sendChat(question, history, {}, tutorialData, latestImage)
      .then((res) => {
        if (res.tutorial_data) setTutorialData(res.tutorial_data);
        setHistory(res.conversation_history);
        if (res.response) {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: res.response, action: res.action },
          ]);
        }
      })
      .catch(() => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Error connecting to server." },
        ]);
      })
      .finally(() => setLoading(false));
  };

  return (
    <div className="flex flex-col h-screen max-w-xl mx-auto font-quicksand bg-[#FFF8F0]">
      {/* Header */}
      <header className="flex items-center justify-between px-5 py-4 sticky top-0 z-10 bg-[#FFF8F0]/90 backdrop-blur-md">
        <div className="font-caveat text-3xl font-semibold text-[#F4845F]">
          Elfy <span className="text-[#6BAB73]">✿</span>
        </div>
        <div className="bg-[#E8F5E9] text-[#6BAB73] text-xs font-bold px-3 py-1.5 rounded-full tracking-wide">
          🌸 Crafter
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {/* Welcome Screen */}
        {messages.length === 0 && !tutorialData && (
          <div className="text-center mt-12 bg-white rounded-3xl p-8 shadow-sm border border-[#FDDCB5]/40">
            <h2 className="font-caveat text-4xl text-[#3E2723] mb-3">Hi! I'm Elfy</h2>
            <p className="text-[#6D4C41] mb-8">
              Your friendly craft companion. What are we making today?
            </p>
            <div className="flex flex-col gap-3 max-w-xs mx-auto">
              {occasions.map((o) => (
                <button
                  key={o.label}
                  onClick={() => handleSend(`I want to make something for ${o.label}`)}
                  className="px-5 py-3 rounded-2xl bg-[#FEF0E1] text-[#8D6E63] font-semibold hover:bg-[#FDDCB5] transition-colors shadow-sm"
                >
                  {o.emoji} {o.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-4">
          {messages.map((msg, i) => (
            <div key={i}>
              <ChatMessage {...msg} onQuickReply={handleSend} />
              {/* Render tutorial canvas inline right after the tutorial_gen_node message */}
              {msg.action === "tutorial_gen_node" && tutorialData && (
                <div className="fade-in mt-4 mb-2">
                  <TutorialCanvas tutorialData={tutorialData} onAskHelp={handleAskHelp} />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Loading Indicator */}
        {loading && (
          <div className="flex justify-start mb-6">
            <div className="bg-white border border-[#FDDCB5]/50 text-[#6BAB73] text-sm font-semibold rounded-2xl rounded-bl-sm px-5 py-3 shadow-sm flex items-center gap-3">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#6BAB73] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-[#6BAB73]"></span>
              </span>
              {statusText}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      {/* Input Footer */}
      <footer className="px-5 py-4 bg-[#FFF8F0] sticky bottom-0">
        <ChatInput
          onSend={handleSend}
          onImageUpload={handleImageUpload}
          disabled={loading}
        />
      </footer>
    </div>
  );
}
