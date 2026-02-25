import type { InspirationImage } from "../api";

interface Props {
  role: "user" | "assistant";
  content: string;
  phase?: string;
  images?: InspirationImage[];
}

export default function ChatMessage({ role, content, phase, images }: Props) {
  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[85%] md:max-w-[70%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-emerald-600 text-white rounded-br-sm"
            : "bg-white text-gray-800 border border-gray-200 rounded-bl-sm shadow-sm"
        }`}
      >
        {!isUser && phase && (
          <div className="text-xs text-emerald-600 font-semibold mb-1 uppercase tracking-wide">
            {phase}
          </div>
        )}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">{content}</div>

        {images && images.length > 0 && (
          <div className="mt-3 border-t border-gray-100 pt-3">
            <div className="text-xs text-gray-500 font-semibold mb-2 uppercase tracking-wide">
              Inspiration Board
            </div>
            <div className="grid grid-cols-3 gap-2">
              {images.map((img) => (
                <a
                  key={img.id}
                  href={img.url_page}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <img
                    src={img.url_small}
                    alt={img.description}
                    className="rounded-lg w-full h-20 object-cover hover:opacity-80 transition-opacity"
                  />
                </a>
              ))}
            </div>
            <div className="text-[10px] text-gray-400 mt-1">
              Photos by Pexels
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
