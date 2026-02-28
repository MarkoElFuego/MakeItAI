interface Props {
  role: "user" | "assistant";
  content: string;
  uploadedImage?: string;
  onQuickReply?: (text: string) => void;
}

// ── Detect quick reply options ───────────────────────────────────────────────
interface QuickReply {
  emoji: string;
  label: string;
  description: string;
}

function extractQuickReplies(text: string): QuickReply[] {
  const replies: QuickReply[] = [];
  const lines = text.split("\n");

  for (const line of lines) {
    // Match: emoji **Bold Text** — description  OR  emoji Bold Text — description
    const match = line.match(
      /^([\u{1F300}-\u{1FAD6}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{1F900}-\u{1F9FF}\u{200D}\u{20E3}\u{E0020}-\u{E007F}][\uFE0F\u200D]*)\s*\*?\*?(.+?)\*?\*?\s*[—\-–]\s*(.+)$/u
    );
    if (match) {
      replies.push({
        emoji: match[1],
        label: match[2].trim(),
        description: match[3].trim(),
      });
    }
  }

  return replies;
}

// ── Render markdown-like text (bold, italic) ─────────────────────────────────
function renderText(text: string) {
  const html = text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, '<code class="bg-gray-100 px-1 rounded text-xs">$1</code>');
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

// ── Main Component ───────────────────────────────────────────────────────────
export default function ChatMessage({
  role,
  content,
  uploadedImage,
  onQuickReply,
}: Props) {
  const isUser = role === "user";
  const quickReplies = !isUser ? extractQuickReplies(content) : [];

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[85%] md:max-w-[70%] rounded-2xl px-4 py-3 ${isUser
          ? "bg-[#F4845F] text-white rounded-br-sm shadow-md"
          : "bg-white text-[#3E2723] border border-[#FDDCB5]/50 rounded-bl-sm shadow-sm"
          }`}
      >
        {/* Content blocks */}
        <div className="whitespace-pre-wrap text-[0.95rem] leading-relaxed font-quicksand">
          {renderText(content)}
        </div>

        {/* Uploaded User Image Preview */}
        {uploadedImage && (
          <div className="mt-3">
            <img
              src={uploadedImage}
              alt="Uploaded Frame"
              className="rounded-xl max-w-full shadow-md w-full h-auto object-cover border border-[#FDDCB5]/50"
            />
          </div>
        )}

        {/* Quick reply buttons */}
        {quickReplies.length > 0 && onQuickReply && (
          <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-[#FDDCB5]/50">
            {quickReplies.map((qr, i) => (
              <button
                key={i}
                onClick={() => onQuickReply(qr.label)}
                className="text-xs px-3 py-2 rounded-lg bg-white border border-[#F4845F] text-[#F4845F] hover:bg-[#F4845F] hover:text-white transition-colors shadow-sm"
              >
                {qr.emoji} {qr.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
