const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface TutorialStep {
  title: string;
  description: string;
  tip?: string;
  materials?: string[];
  youtube_query?: string;
  completed?: boolean;
}

export interface TutorialData {
  project_name: string;
  difficulty: string;
  time_estimate: string;
  materials?: string[];
  ui?: {
    step_label: string;
    of_label: string;
    back_btn: string;
    next_btn: string;
    done_btn: string;
  };
  steps: TutorialStep[];
}

export interface ChatResponse {
  response: string;
  action: string;
  thinking: string;
  generated_image?: string;
  tutorial_data?: TutorialData;
  sources: Record<string, unknown>[];
  conversation_history: ChatMessage[];
}

export interface StreamCallbacks {
  onThinking: (text: string, node: string) => void;
  onToken: (text: string) => void;
  onDone: (data: ChatResponse) => void;
  onError: (error: string) => void;
}

// ── Standard Chat (non-streaming) ──────────────────────────────────────────

export async function sendChat(
  message: string,
  conversationHistory: ChatMessage[] = [],
  projectContext: Record<string, unknown> = {},
  tutorialData: TutorialData | null = null,
  generatedImage: string | null = null,
): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
      project_context: projectContext,
      tutorial_data: tutorialData || undefined,
      generated_image: generatedImage || undefined,
    }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ── Streaming Chat (SSE) ────────────────────────────────────────────────────

export async function sendChatStream(
  message: string,
  callbacks: StreamCallbacks,
  conversationHistory: ChatMessage[] = [],
  projectContext: Record<string, unknown> = {},
  tutorialData: TutorialData | null = null,
): Promise<void> {
  const res = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
      project_context: projectContext,
      tutorial_data: tutorialData || undefined,
    }),
  });

  if (!res.ok) {
    callbacks.onError(`API error: ${res.status}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError("No response body");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let eventType = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ") && eventType) {
        try {
          const data = JSON.parse(line.slice(6));
          switch (eventType) {
            case "thinking":
              callbacks.onThinking(data.text, data.node);
              break;
            case "token":
              callbacks.onToken(data.text);
              break;
            case "done":
              callbacks.onDone(data as ChatResponse);
              break;
          }
        } catch {
          // Skip malformed JSON
        }
        eventType = "";
      }
    }
  }
}

// ── Image Analysis ──────────────────────────────────────────────────────────

export interface ImageAnalysisResponse {
  analysis: string;
  phase: string;
}

export async function analyzeImage(
  imageBase64: string,
  mediaType: string = "image/jpeg",
  message: string = "Please analyze this image."
): Promise<ImageAnalysisResponse> {
  const res = await fetch(`${API_URL}/analyze-image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      image_base64: imageBase64,
      media_type: mediaType,
      message,
    }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
