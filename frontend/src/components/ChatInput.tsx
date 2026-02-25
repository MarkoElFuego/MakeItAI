import { useState, useRef, type FormEvent } from "react";

interface Props {
  onSend: (message: string) => void;
  onImageUpload: (base64: string, mediaType: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, onImageUpload, disabled }: Props) {
  const [text, setText] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText("");
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Remove data:image/xxx;base64, prefix
      const base64 = result.split(",")[1];
      const mediaType = file.type || "image/jpeg";
      onImageUpload(base64, mediaType);
    };
    reader.readAsDataURL(file);
    // Reset so same file can be uploaded again
    e.target.value = "";
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-end">
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={disabled}
        className="p-3 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors disabled:opacity-50 shrink-0"
        title="Upload image"
      >
        📷
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        onChange={handleFile}
        className="hidden"
      />
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Ask about crafting..."
        disabled={disabled}
        className="flex-1 px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 text-sm disabled:opacity-50 bg-white"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="p-3 rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50 shrink-0"
      >
        ➤
      </button>
    </form>
  );
}
