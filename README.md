# Meeting Summarizer

An AI-powered web application that turns meeting recordings, audio, video, or PDF transcripts into concise summaries. Upload your content, get a transcript (or use existing text), and download a professional PDF summary.

---

## What This Project Does

- **Audio/Video → Summary**: Upload audio (MP3, WAV, etc.) or video (MP4, MOV, etc.). The app transcribes speech with Whisper, generates a summary with LLMs, and produces a downloadable PDF.
- **PDF Transcript → Summary**: Upload a PDF transcript. The app extracts text, generates a summary, and outputs a PDF summary—no transcription step.
- **Live Recording**: Record audio in the browser, then upload it for the same pipeline (transcribe → summarize → PDF).
- **Session Cleanup**: Uploaded files, transcripts, and generated PDFs are tied to a session and can be cleaned up when the user leaves or when a new file is uploaded.

---

## Features

- **Multiple input types**: Audio files, video files, PDF transcripts, or live microphone recording
- **Automatic transcription**: OpenAI Whisper for speech-to-text (audio/video)
- **PDF text extraction**: pdfminer.six + PyPDF2 for transcript PDFs
- **AI summarization**: LangChain + Hugging Face models (chunk-based, then combined summary)
- **PDF export**: ReportLab-generated summary PDFs with styling
- **Session-based flow**: Unique session IDs, download links, and cleanup on navigation/failure
- **Responsive UI**: Single-page app with tabs for file upload vs. record, drag-and-drop, and status feedback

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3, Flask |
| **Transcription** | OpenAI Whisper (medium model) |
| **PDF text extraction** | pdfminer.six, PyPDF2 |
| **Summarization** | LangChain, Hugging Face (Qwen, Meta-Llama), langchain-text-splitters |
| **PDF generation** | ReportLab |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript (no framework) |
| **File handling** | Werkzeug (secure uploads), uuid (session IDs) |

### Key Dependencies

- **openai-whisper** – speech-to-text (audio/video)
- **flask**, **werkzeug** – web server and upload handling
- **langchain-core**, **langchain-community**, **langchain-text-splitters**, **langchain-huggingface** – summarization pipeline
- **reportlab** – PDF creation
- **PyPDF2**, **pdfminer.six** – PDF text extraction
- **python-dotenv** – environment variables (e.g. Hugging Face API)

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Browser)                              │
│  • Upload: audio / video / PDF  OR  Record → Upload                          │
│  • POST /upload-audio (multipart) → Poll / status → GET /download-pdf         │
│  • DELETE/POST /cleanup/<session_id> on leave or new upload                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Flask App (main.py)                              │
│  • Save file to uploads/ (unique name: session_id + filename)                │
│  • Branch by type: PDF → pdf_extractor | Audio/Video → transcribe             │
│  • summary_generator(transcript_path) → summary text                          │
│  • pdf_generator(summary_text) → output/<name>_summary.pdf                     │
│  • Store paths in session_files[session_id]                                    │
│  • On error: delete uploaded file, transcript, and PDF                        │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                           │
                    ▼                           ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│  transcribe.py (Whisper)      │   │  pdf_extractor.py             │
│  • Audio/Video → .txt          │   │  • PDF → .txt (transcript)    │
│  • data/transcripts/          │   │  • data/transcripts/           │
└──────────────────────────────┘   └──────────────────────────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  summary_generator.py                                                        │
│  • Load transcript .txt → chunk (RecursiveCharacterTextSplitter)             │
│  • Per-chunk summary (Meta-Llama-3-8B) → combine (Qwen) → single summary     │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  pdf_generator.py                                                             │
│  • summary text → ReportLab SimpleDocTemplate → output/*.pdf                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Directory Layout

```
meeting-summarizer/
├── main.py              # Flask app: routes, upload, download, cleanup
├── transcribe.py        # Whisper: audio/video → transcript .txt
├── pdf_extractor.py     # PDF → transcript .txt
├── summary_generator.py # Transcript → LLM summary (LangChain + Hugging Face)
├── pdf_generator.py     # Summary text → PDF
├── backend.py           # (Optional) standalone summarization script
├── requirements.txt
├── .env                 # e.g. HUGGINGFACEHUB_API_TOKEN (create locally)
├── templates/
│   └── index.html       # Single-page UI (upload / record tabs)
├── static/
│   ├── app.js           # Upload, record, download, cleanup logic
│   └── style.css        # Layout and styling
├── uploads/             # Incoming files (created at runtime)
├── data/
│   └── transcripts/     # Intermediate .txt transcripts
└── output/              # Generated summary PDFs
```

### Data Flow by Input Type

1. **Audio/Video**
   - File → `uploads/` → `transcribe.transcribe_audio_file()` → `data/transcripts/<base>.txt` → `summary_generator.generate_summary()` → `pdf_generator.generate_pdf()` → `output/<name>_summary.pdf`.

2. **PDF transcript**
   - File → `uploads/` → `pdf_extractor.extract_text_from_pdf()` → `data/transcripts/<base>.txt` → same summary + PDF steps.

3. **Live recording**
   - Browser records → Blob uploaded as file → same as audio path.

---

## Prerequisites

- **Python**: 3.9 or higher (recommended 3.10+)
- **ffmpeg**: Required for Whisper to process audio/video (install on system path)
- **Hugging Face**: Account and API token for Hugging Face models used in summarization

---

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd meeting-summarizer
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/macOS
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment variables**
   - Create a `.env` file in the project root.
   - Add your Hugging Face API token (used by `summary_generator.py`):
     ```
     HUGGINGFACEHUB_API_TOKEN=your_token_here
     ```

5. **ffmpeg**
   - Install ffmpeg and ensure it is on your system PATH (required for Whisper with audio/video).

---

## Usage

1. **Start the server**
   ```bash
   python main.py
   ```
   The app runs at `http://127.0.0.1:5000` by default.

2. **Open in browser**
   - Go to `http://127.0.0.1:5000`.

3. **Upload or record**
   - **File upload**: Choose “File upload”, then drag-and-drop or select an audio file, video file, or PDF transcript.
   - **Record**: Choose “Record audio”, allow microphone access, record, then click “Upload”.

4. **Wait for processing**
   - The server transcribes (or extracts text from PDF), then generates the summary and PDF. This may take a minute or more for large files.

5. **Download**
   - When done, a “Download PDF” link appears. Use it to download the summary PDF.

6. **Cleanup**
   - Closing the tab or navigating away triggers cleanup for that session. Uploading a new file cleans up the previous session’s files.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serves the main UI (`index.html`) |
| POST | `/upload-audio` | Upload file (audio/video/PDF). Form field: `audio_file`. Returns `session_id`, `pdf_filename` on success. |
| GET | `/download-pdf/<session_id>` | Download the generated summary PDF for the session. |
| DELETE or POST | `/cleanup/<session_id>` | Delete uploaded file, transcript, and output PDF for the session. |
| GET | `/status/<session_id>` | Check if processing completed and get `pdf_filename`. |

---

## Supported File Types

- **Audio**: `.mp3`, `.wav`, `.m4a`, `.flac`, `.aac`, `.ogg`, `.wma`
- **Video**: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.flv`, `.wmv`, `.m4v`, `.3gp`
- **Transcript**: `.pdf` (text is extracted; no transcription)

---

## Configuration

- **Folders**: `UPLOAD_FOLDER` (`uploads/`), `OUTPUT_FOLDER` (`output/`), and `TRANSCRIPT_FOLDER` (`data/transcripts/`) are set in `main.py`. Folders are created automatically if missing.
- **Whisper model**: In `transcribe.py`, the default model is `medium`. You can change it to `base`, `small`, `large`, or `large-v2` for different speed/quality tradeoffs.
- **Summarization models**: In `summary_generator.py`, chunk summarization uses Meta-Llama-3-8B and final combination uses Qwen. These require a valid `HUGGINGFACEHUB_API_TOKEN` and model access on Hugging Face.

---

## License

See the `LICENSE` file in the project root.

---

## Summary

Meeting Summarizer is a full-stack app that accepts audio, video, or PDF transcripts, produces a text transcript (via Whisper or PDF extraction), runs an LLM-based summarization pipeline, and delivers a PDF summary. The README above describes what it does, the tech stack, architecture, project structure, installation, usage, API, and supported formats so others can run and extend the project.
