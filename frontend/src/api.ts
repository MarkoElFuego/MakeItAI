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
  svg: string;
}

export interface TutorialData {
  project_name: string;
  difficulty: string;
  time_estimate: string;
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
  status_text: string;
  generated_image?: string;
  tutorial_data?: TutorialData;
  sources: Record<string, unknown>[];
  conversation_history: ChatMessage[];
}

export interface ImageAnalysisResponse {
  analysis: string;
  phase: string;
}

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
