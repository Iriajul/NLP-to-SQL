"use client";

import { useEffect, useRef, useState } from "react";
import AssistantMessage, { type Turn } from "@/components/AssistantMessage";
import Sidebar from "@/components/Sidebar";
import {
  ask,
  deleteChat,
  getChat,
  getHealth,
  getSchema,
  listChats,
  type ChatSummary,
  type Health,
  type SavedChat,
  type TableInfo,
} from "@/lib/api";

const EXAMPLES = [
  "Which 5 products have the lowest stock level?",
  "Who are the top 3 customers by total amount spent?",
  "What is the monthly revenue for the last 6 months?",
  "Which sales reps handled the most orders this year?",
];

/** Keep the open chat in the URL (?chat=<id>) so a refresh reopens it. */
function setUrl(chatId: string | null) {
  window.history.replaceState(null, "", chatId ? `?chat=${chatId}` : window.location.pathname);
}

function toTurns(chat: SavedChat): Turn[] {
  return chat.messages.map((m, i) => ({
    id: i, question: m.question, steps: [], result: m.result, failure: null, running: false,
  }));
}

export default function Home() {
  const [chatId, setChatId] = useState<string | null>(null);
  const [chats, setChats] = useState<ChatSummary[] | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loadingChat, setLoadingChat] = useState(false);
  const [input, setInput] = useState("");
  const [tables, setTables] = useState<TableInfo[] | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const nextTurnId = useRef(1_000_000); // above any index used for loaded turns
  const busy = turns.some((t) => t.running);

  const refreshChats = () => listChats().then(setChats).catch(() => setChats([]));

  async function openChat(id: string) {
    if (busy) return;
    setMenuOpen(false);
    setChatId(id);
    setUrl(id);
    setTurns([]);
    setLoadingChat(true);
    try {
      setTurns(toTurns(await getChat(id)));
    } catch {
      // Deleted or unknown chat: fall back to a fresh one.
      setChatId(null);
      setUrl(null);
    } finally {
      setLoadingChat(false);
    }
  }

  function newChat() {
    if (busy) return;
    setMenuOpen(false);
    setChatId(null);
    setUrl(null);
    setTurns([]);
    inputRef.current?.focus();
  }

  async function removeChat(id: string) {
    const title = chats?.find((c) => c.id === id)?.title ?? "this chat";
    if (!window.confirm(`Delete "${title}"?`)) return;
    await deleteChat(id).catch(() => {});
    if (id === chatId) newChat();
    refreshChats();
  }

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    getSchema().then((s) => setTables(s.tables)).catch(() => setTables([]));
    refreshChats();
    const fromUrl = new URLSearchParams(window.location.search).get("chat");
    if (fromUrl) {
      getChat(fromUrl)
        .then((chat) => {
          setChatId(chat.id);
          setTurns(toTurns(chat));
        })
        .catch(() => setUrl(null)); // deleted or unknown chat: start fresh
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const update = (id: number, patch: (t: Turn) => Partial<Turn>) =>
    setTurns((all) => all.map((t) => (t.id === id ? { ...t, ...patch(t) } : t)));

  async function submit(question: string) {
    question = question.trim();
    if (!question || busy || loadingChat) return;
    setInput("");
    setMenuOpen(false);
    const id = nextTurnId.current++;
    setTurns((all) => [...all, { id, question, steps: [], result: null, failure: null, running: true }]);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      // The server keeps the conversation, so follow-ups only need the chat id.
      await ask(
        question,
        chatId,
        {
          onStep: (s) => update(id, (t) => ({ steps: [...t.steps, s] })),
          onChat: (c) => {
            if (!chatId) {
              setChatId(c.id);
              setUrl(c.id);
              refreshChats(); // show the new chat in the sidebar right away
            }
          },
          onResult: (result) => update(id, () => ({ result })),
        },
        controller.signal,
      );
    } catch (e) {
      const message =
        controller.signal.aborted ? "Stopped." :
        e instanceof TypeError ? "Can't reach the API at port 8100. Is the backend running?" :
        (e as Error).message;
      update(id, () => ({ failure: message }));
    } finally {
      update(id, () => ({ running: false }));
      refreshChats(); // new chat appears / active chat moves to the top
    }
  }

  return (
    <div className="flex h-dvh">
      <div
        className={`fixed inset-y-0 left-0 z-20 w-72 transition-transform md:static md:translate-x-0 ${
          menuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar
          chats={chats}
          activeId={chatId}
          onSelect={openChat}
          onNew={newChat}
          onDelete={removeChat}
          tables={tables}
          health={health}
          disabled={busy}
        />
      </div>
      {menuOpen && <div className="fixed inset-0 z-10 bg-black/30 md:hidden" onClick={() => setMenuOpen(false)} />}

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-zinc-200 px-4 py-3 md:hidden dark:border-zinc-800">
          <button onClick={() => setMenuOpen(true)} className="rounded-md px-2 py-1 text-lg" aria-label="Open menu">
            ☰
          </button>
          <span className="flex-1 truncate text-sm font-semibold">
            {chats?.find((c) => c.id === chatId)?.title ?? "NLP to SQL"}
          </span>
          <button onClick={newChat} disabled={busy} className="rounded-md px-2 py-1 text-lg" aria-label="New chat">
            +
          </button>
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
            {loadingChat && <p className="text-center text-sm text-zinc-500">Loading chat…</p>}
            {!loadingChat && turns.length === 0 && (
              <div className="mt-[12vh] text-center">
                <h2 className="text-2xl font-semibold tracking-tight">Ask your database anything</h2>
                <p className="mt-2 text-zinc-500">
                  Questions in plain English become SQL, run on PostgreSQL, and come back as answers.
                </p>
                <div className="mt-8 grid gap-2 text-left sm:grid-cols-2">
                  {EXAMPLES.map((q) => (
                    <button
                      key={q}
                      onClick={() => submit(q)}
                      className="rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700 transition hover:border-indigo-400 hover:bg-indigo-50/50 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-300 dark:hover:border-indigo-500 dark:hover:bg-indigo-950/30"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {turns.map((t) => (
              <div key={t.id} className="flex flex-col gap-3">
                <div className="self-end rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-[15px] text-white">
                  {t.question}
                </div>
                <AssistantMessage turn={t} />
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(input);
          }}
          className="border-t border-zinc-200 bg-[var(--background)] p-4 dark:border-zinc-800"
        >
          <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-zinc-300 bg-white p-2 shadow-sm focus-within:border-indigo-500 dark:border-zinc-700 dark:bg-zinc-900">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit(input);
                }
              }}
              rows={1}
              placeholder={turns.length ? "Ask a follow-up, e.g. \"now only for Germany\"" : "e.g. Which customers spent the most last quarter?"}
              className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-[15px] outline-none placeholder:text-zinc-400"
            />
            {busy ? (
              <button
                type="button"
                onClick={() => abortRef.current?.abort()}
                className="rounded-xl bg-zinc-200 px-4 py-2 text-sm font-medium dark:bg-zinc-700"
              >
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim() || loadingChat}
                className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-40"
              >
                Ask
              </button>
            )}
          </div>
          <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-zinc-500">
            Read-only access · queries time out after 10 s · chats are saved
          </p>
        </form>
      </main>
    </div>
  );
}
