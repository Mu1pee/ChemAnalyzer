import { API_ORIGIN, NETWORK_ERROR_MESSAGE } from "./base";
import type {
  AssistantMode,
  AssistantStatus,
  ChatMessage
} from "../types/molecule";

const API_ROOT = API_ORIGIN;

export async function getAssistantStatus(): Promise<AssistantStatus | null> {
  try {
    const response = await fetch(`${API_ROOT}/api/assistant/status`);
    return response.ok ? ((await response.json()) as AssistantStatus) : null;
  } catch {
    return null;
  }
}

/**
 * Отправляет диалог и вызывает onChunk по мере поступления текста.
 * Возвращает полный текст ответа. Отмена — через AbortSignal.
 */
export async function streamChat(
  mode: AssistantMode,
  messages: ChatMessage[],
  context: Record<string, unknown> | null,
  onChunk: (text: string) => void,
  signal: AbortSignal
): Promise<string> {
  let response: Response;

  try {
    response = await fetch(`${API_ROOT}/api/assistant/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, messages, context }),
      signal
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new Error(NETWORK_ERROR_MESSAGE);
  }

  if (!response.ok) {
    let detail = `Ошибка сервера (код ${response.status}).`;
    try {
      const data = (await response.json()) as { detail?: unknown };
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      // ответ не JSON — оставляем сообщение по умолчанию
    }
    throw new Error(detail);
  }

  if (!response.body) {
    const text = await response.text();
    onChunk(text);
    return text;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let full = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    const piece = decoder.decode(value, { stream: true });
    full += piece;
    onChunk(piece);
  }

  const tail = decoder.decode();
  if (tail) {
    full += tail;
    onChunk(tail);
  }
  return full;
}
