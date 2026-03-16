# MeetingAI — Real-Time Intelligent Meeting Assistant

An AI-powered web application that captures live meeting audio, transcribes speech in real time, indexes the transcript for semantic search, and runs an intelligent agent that can answer questions about your meeting, search the web, and manage your Google Calendar — all from a single browser tab.

---

## What This Project Does

- **Live Transcription**: Captures microphone audio, tab audio, or both simultaneously. Streams audio chunks to the server every 15 seconds, transcribes with Groq Whisper `large-v3`, and displays results in real time.
- **Semantic Q&A**: Ask anything about the meeting in natural language. A LangGraph ReAct agent searches the live transcript using vector similarity and returns grounded answers.
- **Calendar Integration**: Ask the agent to create, list, or update Google Calendar events. Commands like *"Schedule a follow-up for Sunday at 3pm"* are handled end-to-end.
- **Web Search**: When the answer isn't in the transcript, the agent searches the web via Tavily and returns current information.
- **Auto Summarization**: Generates a final meeting summary when recording stops. For sessions longer than 10 minutes, progressive summaries are generated automatically using a MapReduce strategy for long transcripts.

---

## Features

- Real-time WebSocket audio streaming from the browser
- Multi-source audio capture — mic only, tab audio, or mic + tab mixed via Web Audio API
- Per-session in-memory ChromaDB vector store — no cross-session data leakage
- LangGraph ReAct agent with `ToolNode` and `tools_condition` — proper tool-call loop, not a single-shot chain
- MCP (Model Context Protocol) calendar server — extensible to Gmail, Drive, and other tools
- MapReduce summarization strategy for long meetings
- Clean, responsive UI with live transcript scroll, Q&A chat interface, and transcript keyword filter

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Transcription** | Groq Whisper `large-v3` |
| **Embeddings** | FastEmbed `BAAI/bge-small-en-v1.5` (local ONNX — no API call) |
| **Vector Store** | LangChain Chroma (in-memory, per session) |
| **Agent Framework** | LangGraph ReAct with `ToolNode` + `tools_condition` |
| **Agent LLM** | GPT-4o via GitHub Models (Azure inference endpoint) |
| **Summary LLM** | Groq `llama-3.3-70b-versatile` |
| **Web Search** | Tavily |
| **Calendar** | MCP server (`@cablate/mcp-google-calendar`) + Google Service Account |
| **Backend** | FastAPI + WebSocket + Uvicorn |
| **Audio Processing** | ffmpeg (WebM → WAV), Web Audio API |
| **Frontend** | Vanilla JS + CSS — no framework |

---

## Architecture

```
Browser (MediaRecorder API)
        │
        │  WebM/Opus audio chunks over WebSocket
        ▼
FastAPI WebSocket Server  (app/api/audio.py)
        │
        ├── ffmpeg ──────────────────────► WebM → WAV conversion
        │
        ├── Groq Whisper large-v3 ───────► Real-time transcription
        │
        ├── TranscriptIngestionPipeline  (background thread queue)
        │       └── Sentence splitter
        │               └── FastEmbed embeddings
        │                       └── ChromaDB  (in-memory, per session)
        │
        ├── LangGraph ReAct Agent  ──────► On every Q&A request
        │       ├── search_transcript    ► ChromaDB cosine similarity search
        │       ├── web_search           ► Tavily
        │       └── MCP Calendar Tools   ► create_event / list_events / update_event / delete_event
        │                                        └── Google Calendar API (Service Account)
        │
        └── Groq LLM ───────────────────► Final summary + progressive summaries
```

---

## Project Structure

```
meeting-summarizer/
├── app/
│   ├── api/
│   │   ├── audio.py              # WebSocket handler, MeetingSession, audio pipeline
│   │   └── upload.py             # File upload endpoints
│   ├── core/
│   │   └── config.py             # Settings — all config lives here
│   ├── services/
│   │   ├── audio_processor.py    # ffmpeg WebM → WAV conversion + cleanup
│   │   ├── summary.py            # Groq LLM summarization (direct + MapReduce)
│   │   ├── transcription.py      # Groq Whisper client
│   │   └── rag/
│   │       ├── __init__.py       # Public exports
│   │       ├── agent.py          # LangGraph ReAct agent, run_agent()
│   │       ├── ingestion.py      # Background queue worker, sentence splitter
│   │       ├── retriever.py      # MeetingRetriever, RetrievalResult dataclass
│   │       ├── store.py          # ChromaDB vectorstore (thread-safe wrapper)
│   │       └── tools.py          # search_transcript, web_search, MCP tools loader
│   └── main.py                   # FastAPI app, lifespan, static file serving
├── static/
│   ├── index.html                # UI structure
│   ├── style.css                 # All styles
│   └── app.js                    # WebSocket logic, audio capture, UI interactions
├── uploads/                      # Temporary audio chunks (auto-cleaned per session)
├── output/                       # Session transcripts and summaries
├── data/
│   └── transcripts/              # Saved transcript text files
├── logs/                         # Application logs
├── mcp_server_file.json          # MCP server configuration
├── service_account.json          # Google Service Account key (gitignored)
├── .env                          # API keys (gitignored)
├── .env.example                  # Template — copy this to .env
└── requirements.txt
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+ and `npx` (required for the MCP calendar server)
- ffmpeg installed and available on `PATH`
- Chrome or Edge (required for `MediaRecorder` with `audio/webm;codecs=opus`)

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/yourusername/meeting-summarizer.git
cd meeting-summarizer
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**3. Install Python dependencies**

```bash
pip install -r requirements.txt
```

**4. Set up environment variables**

```bash
cp .env.example .env
```

Open `.env` and fill in your keys (see [Environment Variables](#environment-variables) below).

**5. Set up Google Calendar** (optional — skip if not using calendar features)

Follow the [Google Calendar Setup](#google-calendar-setup) section below.

**6. Run the server**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

---

## Environment Variables

Only the following four keys go in `.env`. All other configuration (folders, model names, debug mode) is managed in `app/core/config.py`.

```env
# Groq — transcription and summarization
GROQ_API_KEY=gsk_your_groq_api_key

# GitHub Models — GPT-4o agent LLM (via Azure inference endpoint)
GITHUB_TOKEN=your_github_personal_access_token

# Tavily — web search tool for the agent
TAVILY_API_KEY=tvly_your_tavily_api_key

# MCP server config — absolute path to mcp_server_file.json
MCP_CONFIG_FILE=C:\Users\YourName\meeting-summarizer\mcp_server_file.json
```

To get these keys:
- **Groq**: [console.groq.com](https://console.groq.com)
- **GitHub Token**: [github.com/settings/tokens](https://github.com/settings/tokens) — enable Models access
- **Tavily**: [app.tavily.com](https://app.tavily.com)

---

## Google Calendar Setup

MeetingAI uses a **Google Service Account** for calendar access. This requires a one-time setup and works forever without browser login prompts.

**1. Enable the Calendar API**

Go to [console.cloud.google.com](https://console.cloud.google.com), select your project, and enable the **Google Calendar API**.

**2. Create a Service Account**

Navigate to **IAM & Admin → Service Accounts → Create Service Account**. After creation go to the **Keys** tab → **Add Key → Create new key → JSON**. Download the file and save it as `service_account.json` in the project root.

**3. Share your calendar with the service account**

Open [Google Calendar](https://calendar.google.com) → your calendar → **Settings and sharing** → **Share with specific people** → add the `client_email` from `service_account.json` with **Make changes to events** permission.

```

---

## Usage

**Starting a session**

1. Select your audio source — **Mic Only**, **Tab Audio**, or **Mic + Tab** (recommended for online meetings)
2. Click **Start Recording**
3. Speak naturally — transcript chunks appear every ~15 seconds

**Asking questions**

The Q&A panel is available at any time during or after recording:

| Example prompt | What happens |
|---|---|
| *"What decisions were made?"* | Searches transcript via vector similarity |
| *"What did we say about the deadline?"* | Returns matching transcript segments |
| *"Schedule a follow-up for Sunday at 3pm"* | Creates event in Google Calendar |
| *"List my events this week"* | Fetches from Google Calendar |
| *"What is LangGraph?"* | Web search via Tavily |

**Generating a summary**

Click **Summarise** after stopping the recording, or let the app auto-generate one. Sessions longer than 10 minutes get progressive summaries automatically.

---

## Summarization Strategy

| Transcript length | Strategy |
|---|---|
| Short (< 2,000 tokens) | Single direct LLM call |
| Medium (2,000 – 6,000 tokens) | Direct with token-aware context window management |
| Long (> 6,000 tokens) | MapReduce — chunk → summarize each chunk → reduce all chunk summaries into one |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the main UI |
| `WebSocket` | `/ws/audio?session_id=<id>` | Audio stream, transcription, Q&A, summary |
| `POST` | `/api/upload` | File upload endpoint |

**WebSocket — client → server**

| Type | Payload | Description |
|---|---|---|
| Binary | `ArrayBuffer` | Raw audio chunk |
| `stop` | `{}` | Stop recording, trigger final summary |
| `question` | `{ text: string }` | Send a Q&A question |
| `generate_summary` | `{}` | Manually request summary generation |

**WebSocket — server → client**

| Type | Description |
|---|---|
| `transcript` | New transcribed chunk with chunk ID and word count |
| `qa_answer` | Agent response to a question |
| `final_summary` | Complete summary after session ends |
| `progressive_summary` | Auto-generated mid-session summary |
| `error` | Error message |

---

## Known Limitations

- **Session memory** — the vector store is in-memory and lost when the session ends. Transcripts are saved to `output/` but are not re-indexed on reload.
- **Single user calendar** — the Google Calendar integration uses a service account tied to one shared calendar. Multi-user OAuth is not yet implemented.
- **Browser support** — Chrome and Edge are fully supported. Safari has limited `MediaRecorder` support.
- **MCP cold start** — the first calendar question per session takes 5–8 seconds while the MCP server process spawns. Subsequent questions in the same session are fast.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [Groq](https://groq.com) — fast Whisper and LLM inference
- [LangGraph](https://github.com/langchain-ai/langgraph) — agent framework
- [ChromaDB](https://www.trychroma.com) — vector store
- [FastEmbed](https://github.com/qdrant/fastembed) — local ONNX embeddings
- [Model Context Protocol](https://modelcontextprotocol.io) — calendar integration pattern
- [Tavily](https://tavily.com) — web search API
