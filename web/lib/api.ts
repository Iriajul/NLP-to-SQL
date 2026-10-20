export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";

export type Cell = string | number | boolean | null;

export interface AskResult {
  question: string; // standalone version of what was asked (differs for follow-ups)
  answer: string;
  sql: string;
  sql_history: string[];
  attempts: number;
  tables: string[];
  columns: string[];
  rows: Cell[][];
  error: string | null;
}

export type StepNode = "rewrite_question" | "generate_sql" | "check_sql" | "execute_sql" | "fix_sql" | "answer";

export interface StepEvent {
  node: StepNode;
  attempt: number;
  error: string | null;
}

export interface ChatSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface SavedChat extends ChatSummary {
  messages: { question: string; result: AskResult }[];
}

export interface TableInfo {
  name: string;
  rows: number;
  columns: { name: string; type: string }[];
}

export interface Health {
  ok: boolean;
  model: string;
  has_api_key: boolean;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

export const getHealth = () => getJson<Health>("/api/health");
export const getSchema = () => getJson<{ schema: string; tables: TableInfo[] }>("/api/schema");
export const listChats = () => getJson<ChatSummary[]>("/api/chats");
export const getChat = (id: string) => getJson<SavedChat>(`/api/chats/${id}`);

export async function deleteChat(id: string) {
  const res = await fetch(`${API_URL}/api/chats/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
}

/**
 * POST a question and call the handlers as server-sent events arrive.
 * chatId continues a saved chat (the server supplies the follow-up context); null starts a new one.
 */
export async function ask(
  question: string,
  chatId: string | null,
  handlers: {
    onStep: (s: StepEvent) => void;
    onChat: (c: { id: string; title?: string }) => void;
    onResult: (r: AskResult) => void;
  },
  signal?: AbortSignal,
) {
  const res = await fetch(`${API_URL}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, chat_id: chatId }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const event = block.match(/^event: (.*)$/m)?.[1];
      const data = JSON.parse(block.match(/^data: (.*)$/m)?.[1] ?? "null");
      if (event === "step") handlers.onStep(data);
      else if (event === "chat") handlers.onChat(data);
      else if (event === "result") handlers.onResult(data);
      else if (event === "error") throw new Error(data.message);
    }
  }
}
