const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface CraftStep {
  id: number;
  title: string;
  description: string;
  svgCode: string;
}

export interface CraftData {
  projectName: string;
  difficulty: string;
  estimatedTime: string;
  materials: string[];
  steps: CraftStep[];
}

export interface ChatResponse {
  response: string;
  phase: string;
  sources: Record<string, unknown>[];
  inspiration_images: InspirationImage[];
  craft_data: CraftData | null;
  conversation_history: ChatMessage[];
}

export interface InspirationImage {
  id: number;
  description: string;
  photographer: string;
  url_medium: string;
  url_small: string;
  url_page: string;
}

export interface ImageAnalysisResponse {
  analysis: string;
  phase: string;
}

export async function sendChat(
  message: string,
  conversationHistory: ChatMessage[] = [],
  projectContext: Record<string, unknown> = {}
): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
      project_context: projectContext,
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
