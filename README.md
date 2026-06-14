# 📚 BookGen — Automated Book Generation System

**BookGen is an AI-powered book writing system that turns ideas into polished manuscripts.** It orchestrates a multi-step human-in-the-loop pipeline: outline → chapter-by-chapter generation → final compilation. Editors review and approve at every gate, with continuity built in—each chapter knows what came before it. Powered by Groq's fast LLMs, LangGraph for workflow orchestration, and Supabase for state management.

## 🎬 Demo

Coming soon! [Link to demo video will go here at step 5]

## Stack

| Layer | Choice |
| --- | --- |
| LLM | **Groq** (`moonshotai/kimi-k2-instruct` for writing, `llama-3.1-8b-instant` for summarization) |
| Orchestration | **LangGraph** (graph-based, gated, resumable) |
| DB / State | **Supabase** (Postgres) |
| Dashboard | **Streamlit** |
| Notifications | **SMTP email** |
| Research (optional) | **DuckDuckGo** via `ddgs` (no API key) |
| Output | **python-docx** (`.docx` and `.pdf`) |

## About

**Topics:** `langgraph` · `agentic-ai` · `supabase` · `streamlit` · `groq`

## Architecture

```
   Streamlit Dashboard  ◄──── editor reviews / approves / regenerates
          │
          ▼
   Supabase (books, chapters, events)
          ▲
          │  poll every 5s
   Worker (worker.py)
          │
          ▼
   LangGraph: router → [outline | chapter | compile | gated]
          │
          ▼
   Groq LLM  +  optional DDG research  →  python-docx
                                          │
                                          ▼
                                  notify editor via SMTP
```

## Workflow

1. **Create book** in the dashboard (title + pre-notes + optional outline notes).
2. **Worker** picks it up, calls the outline node, sets status `waiting_for_review`, emails the editor.
3. **Editor** reviews the outline in the dashboard → either **Approve** or **Regenerate with notes**.
4. On approval, each chapter is generated sequentially. Chapter N's prompt includes summaries of chapters 1..N-1 (continuity).
5. Editor approves each chapter the same way.
6. When all chapters are approved, the worker compiles the `.docx` and the editor can download it.

## Setup

### 1. Clone & install

```bash
git clone <repo>
cd bookgen
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Supabase

- Create a free project at https://supabase.com
- In the **SQL editor**, paste and run `schema.sql`
- Copy your **Project URL** and **service_role key** (Settings → API)

### 3. Groq

- Get a free key at https://console.groq.com/keys

### 4. (Optional) SMTP

For Gmail: enable 2FA, then create an [app password](https://myaccount.google.com/apppasswords).
Leave SMTP variables blank to disable email notifications (the dashboard still works).

### 5. `.env`

```bash
cp .env.example .env
# then edit .env with your keys
```

### 6. Run

In one terminal:
```bash
python worker.py
```

In another:
```bash
streamlit run dashboard.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

## File layout

```
bookgen/
├── schema.sql              # Supabase tables
├── requirements.txt
├── .env.example
├── worker.py               # background loop -- advances books one step at a time
├── dashboard.py            # Streamlit UI
└── src/
    ├── config.py           # env loader
    ├── db.py               # Supabase CRUD
    ├── llm.py              # Groq client + retry
    ├── prompts.py          # outline / chapter / summary prompts
    ├── research.py         # optional DDG web search
    ├── notifications.py    # SMTP email
    ├── compiler.py         # DOCX assembly
    └── graph.py            # LangGraph pipeline (router + nodes)
```

## State machine

**Book.outline_status**
`ready_to_generate → generating → waiting_for_review → approved`
(loops back to `ready_to_generate` on regenerate request)

**Chapter.status**
`pending → ready_to_generate → generating → waiting_for_review → approved`

**Book.status**
`created → outlining → chapters → compiling → done` (or `error`)

The dashboard only mutates editor-controlled transitions (approve / regenerate). The worker handles `*_to_generate → generating → waiting_for_review` and final compile.

## How LangGraph is used

`src/graph.py` defines a graph with five nodes — `router`, `outline`, `chapter`, `compile`, `gated`. The router reads the book's DB state and conditionally routes to the right node. Each generation node terminates the graph (END) after producing one artifact and flipping status to `waiting_for_review`. The worker re-invokes `run_step(book_id)` after the editor's decision changes the status. This gives you genuine gating without long-running processes or web sockets.

## Notes on cost & speed

- Kimi-K2 on Groq is fast (~tens of seconds per chapter) and cheap.
- Summaries use the small Llama-3.1 8B to keep cost negligible.
- The worker polls every 5s; tune `POLL_SECONDS` in `worker.py` if you want faster reaction.

## Extending

- **Add PDF/TXT output**: extend `src/compiler.py` (use `reportlab` or `pypandoc`).
- **Add Teams notifications**: extend `src/notifications.py` to POST to a webhook.
- **Add Google Sheets input**: write an ingestion script that pushes rows into `books`.
- **Swap LLM provider**: edit `src/llm.py`; the rest of the pipeline doesn't care.

## License

MIT
