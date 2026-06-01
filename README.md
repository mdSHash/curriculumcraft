# CurriculumCraft

> **Generate Egyptian-curriculum workbooks, quizzes and MOE-style weekly assessments from a textbook PDF — across every subject. Fully editable `.docx` output, RTL Arabic supported, math-grade OMML where it matters.**

CurriculumCraft (formerly MathCraft) ingests an Egyptian-curriculum textbook PDF in any subject — Mathematics, Arabic, English, French, Physics, Chemistry, History, Religion, ICT, Programming, and 14 more — indexes it with a hybrid (FAISS + BM25) retrieval pipeline, and uses Google Gemini to produce print-ready Word documents that match the layout teachers actually use:

- **Workbooks** — exercises, fill-in answer space, optional answer key
- **Illustrated lessons + workbook** — concept boxes, theorems, key formulas, worked examples, then exercises
- **Quizzes & monthly exams** — official MOE multi-section format (choose / complete / answer / solve / essay)
- **Weekly assessments** — topic-organised paper with three parallel groups, mirroring the Ministry of Education's [Classroom & Home Assessments](https://ellibrary.moe.gov.eg/cha/) across all 24 canonical subjects

Output is A4 `.docx` with proper bidi/RTL handling, math-aware OMML rendering for STEM subjects, and plain Amiri/Tajawal rendering for language and humanities subjects. Editable in Word, Google Docs, or LibreOffice afterwards.

## Live demo

- **Frontend:** https://mdshash.github.io/curriculumcraft/

GitHub Pages serves the React frontend as a static site. To make it actually generate workbooks, run the FastAPI backend on your own machine and connect the deployed frontend to it via a free **Cloudflare Tunnel** — see [HOSTING.md](HOSTING.md) for the 3-step setup. (Or just run both halves locally — instructions below.)

## Status

Active development. The core ingestion → RAG → generation → DOCX pipeline works end-to-end on real Egyptian textbooks (primary, preparatory, and secondary), validated for math; other subjects share the infrastructure and ship via per-subject strategies that the registry resolves automatically. The build is **safe to run locally for personal use**, but **do not expose the backend to the public internet without adding authentication first** — there is no auth layer yet.

## Features

- 🌍 **All 24 canonical Egyptian MOE subjects** — Math, Physics, Chemistry, Integrated Science, Arabic, English, French (L1+L2), German, Spanish, Italian, Chinese, History, Geography, Philosophy & Logic, Psychology & Sociology, Islamic Studies, Christian Studies, ICT (Ar+En), Programming & AI (Ar+En), Family Skills, Agriculture Skills
- 📥 PDF ingestion with OCR fallback (`pdfplumber` + `pytesseract` + `pymupdf`)
- 🔎 Hybrid retrieval — semantic (sentence-transformers + FAISS) + lexical (BM25) + MMR diversification
- 🧮 Subject-aware prompt strategies — math gets OMML notation, language subjects get prose-aware prompts, religion subjects respect scripture citation conventions
- 🏛️ Direct integration with the **MOE eLibrary** for both `/books/books.json` (textbooks) and `/cha/books.json` (weekly assessments) — hamza-folded matching so catalog variants like `الاسبانية` and `الإسبانية` resolve to the same canonical key
- 🪄 Multi-step wizard with subject picker, scope, structure, exercise mix, formatting
- 📄 RTL-correct `.docx` output (paragraph-level `w:bidi`, per-subject ministry letterhead for weekly assessments)
- 🔁 Multi-variant exam generation with deterministic per-variant shuffling
- 🛡️ Resilient polling with exponential backoff (survives HF Space cold-starts) and orphaned-job recovery on server restart

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18 · Vite · Tailwind CSS · Framer Motion · React Router |
| Backend | Python 3.11 · FastAPI · SQLAlchemy 2 · Pydantic v2 |
| RAG | sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`) · FAISS · BM25 · MMR |
| Extraction | pdfplumber · pytesseract · pymupdf · python-docx |
| LLM | Google Gemini (configurable model) |
| Storage | SQLite + on-disk FAISS indices |

## Prerequisites

- **Python 3.11+** — https://python.org/downloads/
- **Node.js 18+** — https://nodejs.org/
- **Google Gemini API key** — https://aistudio.google.com/app/apikey *(optional — without it, CurriculumCraft falls back to template exercises)*
- **Tesseract OCR** *(optional, for scanned textbooks)* — [Windows installer](https://github.com/UB-Mannheim/tesseract/wiki) · `brew install tesseract` · `sudo apt install tesseract-ocr`

## Quick start

### Windows

```powershell
git clone https://github.com/mdSHash/curriculumcraft.git
cd curriculumcraft
.\setup.bat
```

### macOS / Linux

```bash
git clone https://github.com/mdSHash/curriculumcraft.git
cd curriculumcraft
chmod +x setup.sh && ./setup.sh
```

### Manual setup

**Backend**

```bash
cd backend
python -m venv venv
# Windows:  venv\Scripts\activate
# Unix:     source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then edit .env and add your GEMINI_API_KEY
uvicorn main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

App will be at **http://localhost:5173**.

### Docker

```bash
docker-compose up --build
```

## Configuration

Environment variables (see `backend/.env.example`):

| Variable | Default | Notes |
|---|---|---|
| `GEMINI_API_KEY` | — | Optional. App degrades to fallback exercises without it. |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Any Gemini model your key has access to. |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Multilingual model — important for Arabic content. |
| `DB_PATH` | `./data/mathcraft.db` | SQLite file. |
| `UPLOAD_DIR` | `./data/uploads` | Where uploaded PDFs are stored. |
| `OUTPUT_DIR` | `./data/workbooks` | Where generated `.docx` lives. |
| `FAISS_DIR` | `./data/faiss_indices` | One subdir per book. |
| `MAX_PDF_SIZE_MB` | `50` | Upload size cap (declared but not yet enforced — fix planned). |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated. |

## Usage

1. **Upload a textbook** — drag a PDF/DOCX into the upload page (or import directly from the MOE eLibrary). Wait while the pipeline extracts → chunks → embeds → indexes.
2. **Pick a mode** — workbook only · illustrated lesson + workbook · exam / quiz.
3. **Configure** — chapters and topics in scope, page count, exercise mix, difficulty distribution, formatting, language (Arabic / English / bilingual).
4. **Generate** — wait for RAG retrieval and Gemini to produce the content.
5. **Download** — print-ready `.docx`. Open in Word / Google Docs / LibreOffice and tweak as needed.

## Project layout

```
mathcraft/
├── backend/
│   ├── main.py                    FastAPI entry point
│   ├── config.py · database.py
│   ├── models/                    SQLAlchemy models (Book, Chapter, Topic, Workbook, Exam, ChunkMetadata)
│   ├── schemas/                   Pydantic request/response schemas
│   ├── routers/                   /books · /workbooks · /exams · /moe-library
│   ├── services/
│   │   ├── pdf_extractor.py       pdfplumber + OCR fallback
│   │   ├── content_parser.py      chapter/lesson detection
│   │   ├── semantic_chunker.py
│   │   ├── embedding_service.py   sentence-transformers + FAISS
│   │   ├── hybrid_search.py       FAISS + BM25 + MMR
│   │   ├── rag_service.py         retrieval pipeline
│   │   ├── llm_service.py         Gemini integration
│   │   ├── workbook_orchestrator.py
│   │   ├── exam_orchestrator.py
│   │   ├── moe_library_service.py MOE eLibrary catalog + downloads
│   │   ├── docx_generator.py      workbook DOCX assembly
│   │   └── exam_docx_generator.py exam DOCX assembly (RTL, MOE letterhead)
│   └── utils/                     Arabic reshaping, file utils
└── frontend/
    └── src/
        ├── pages/                 Dashboard · Upload · Builder · Results
        ├── components/wizard/     scope · output mode · structure · exercises · exam config · formatting
        ├── components/upload/     drop zone · MOE library browser · progress
        ├── api/client.js          axios client
        └── i18n/                  English & Arabic dictionaries
```

## API endpoints (selected)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/books/upload` | Upload a textbook PDF/DOCX |
| `GET` | `/api/books` · `/api/books/{id}` · `/api/books/{id}/outline` | List · detail · detected outline |
| `POST` | `/api/workbooks/generate` | Kick off workbook generation |
| `GET` | `/api/workbooks/{id}/status` · `/download` | Poll · download |
| `POST` | `/api/exams/generate` | Kick off exam / quiz generation |
| `GET` | `/api/exams/{id}/status` · `/download` · `/download-answer-key` | Poll · download |
| `GET` | `/api/moe-library/books` · `/assessments` · `/assessments/grades` · `/stages` | Browse MOE catalog |
| `POST` | `/api/moe-library/import` | Import an MOE textbook |

Interactive docs available at `http://localhost:8000/docs` once the backend is running.

## MOE eLibrary integration

The Egyptian Ministry of Education publishes two public JSON catalogs:

- `https://ellibrary.moe.gov.eg/books/books.json` — student textbooks
- `https://ellibrary.moe.gov.eg/cha/books.json` — official weekly assessments (Mathematics Curriculum Development Department)

MathCraft browses both, downloads PDFs into the upload pipeline on demand, and (optionally) feeds the extracted text from a real ministry assessment into the LLM context so generated weekly assessments mirror the official format — topic-organised sections (Algebra / Trigonometry / Geometry), three parallel "groups", and the ministry letterhead.

## Known limitations / roadmap

- No authentication on the API — single-user local app for now. Auth + per-user ownership planned.
- Upload size limit declared in config but not yet enforced.
- OCR is synchronous; large scanned books can block the event loop.
- LLM calls run sequentially per workbook; concurrent batching planned.
- See [issues](https://github.com/mdSHash/curriculumcraft/issues) for the full backlog.

## Contributing

Issues and PRs welcome. The codebase keeps a deliberate split between RAG plumbing (`services/rag_*`, `services/embedding_service.py`, `services/hybrid_search.py`) and content generation (`services/*_orchestrator.py`, `services/*_docx_generator.py`); please preserve that boundary when adding features.

## License

MIT — see `LICENSE`.

## Author

**Mostafa Ayman** ([@mdSHash](https://github.com/mdSHash))
