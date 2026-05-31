# MathCraft — Project Structure

> AI-Powered Math Workbook Generator  
> Full-stack web application: React + Tailwind CSS | Python FastAPI | SQLite

---

## Table of Contents

1. [Directory Tree](#directory-tree)
2. [File Responsibilities](#file-responsibilities)
3. [Data Flow Diagram](#data-flow-diagram)
4. [API Endpoint Summary](#api-endpoint-summary)
5. [Key Design Decisions](#key-design-decisions)

---

## Directory Tree

```
mathcraft/
├── PROJECT_STRUCTURE.md          # This file — architecture reference
├── README.md                     # Setup & run instructions
├── docker-compose.yml            # Optional containerized deployment
├── setup.sh                      # One-command setup script
│
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── requirements.txt          # Python dependencies
│   ├── .env.example              # Environment variable template
│   ├── config.py                 # Configuration management (from .env)
│   ├── database.py               # SQLite setup with SQLAlchemy
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── book.py               # Book SQLAlchemy model
│   │   └── workbook.py           # Workbook SQLAlchemy model
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── book.py               # Pydantic schemas for books
│   │   └── workbook.py           # Pydantic schemas for workbooks
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── books.py              # Book upload & management endpoints
│   │   └── workbooks.py          # Workbook generation & management endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf_extractor.py      # PDF text extraction (pdfplumber + pytesseract fallback)
│   │   ├── content_parser.py     # Intelligent content chunking & structure detection
│   │   ├── embedding_service.py  # Sentence-transformers embedding + FAISS indexing
│   │   ├── rag_service.py        # RAG retrieval pipeline
│   │   ├── llm_service.py        # OpenAI/LLM interaction layer
│   │   └── docx_generator.py     # python-docx workbook assembly
│   │
│   ├── data/
│   │   ├── uploads/              # Uploaded PDF storage
│   │   ├── workbooks/            # Generated .docx output
│   │   ├── faiss_indices/        # FAISS vector stores per book
│   │   └── mathcraft.db          # SQLite database file
│   │
│   └── utils/
│       ├── __init__.py
│       ├── arabic_utils.py       # RTL text handling (arabic-reshaper, python-bidi)
│       └── file_utils.py         # File path helpers
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    ├── public/
    │   └── favicon.ico
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── index.css
        │
        ├── api/
        │   └── client.js             # Axios/fetch API client
        │
        ├── components/
        │   ├── layout/
        │   │   ├── Header.jsx
        │   │   ├── Sidebar.jsx
        │   │   └── Layout.jsx
        │   ├── upload/
        │   │   ├── DropZone.jsx
        │   │   ├── MetadataForm.jsx
        │   │   └── ProgressBar.jsx
        │   ├── wizard/
        │   │   ├── WizardContainer.jsx
        │   │   ├── StepIndicator.jsx
        │   │   ├── ScopeSelection.jsx
        │   │   ├── WorkbookStructure.jsx
        │   │   ├── ExerciseConfig.jsx
        │   │   └── FormattingStyle.jsx
        │   ├── workbook/
        │   │   ├── WorkbookCard.jsx
        │   │   └── PreviewPanel.jsx
        │   └── common/
        │       ├── Button.jsx
        │       ├── Card.jsx
        │       ├── Modal.jsx
        │       ├── Slider.jsx
        │       └── Toggle.jsx
        │
        ├── pages/
        │   ├── Dashboard.jsx
        │   ├── UploadPage.jsx
        │   ├── WorkbookBuilder.jsx
        │   └── ResultsPage.jsx
        │
        ├── hooks/
        │   ├── useBooks.js
        │   └── useWorkbooks.js
        │
        └── utils/
            └── constants.js
```

---

## File Responsibilities

### Root Files

| File | Purpose |
|------|---------|
| `PROJECT_STRUCTURE.md` | Canonical architecture reference document |
| `README.md` | Developer onboarding — prerequisites, installation, running locally |
| `docker-compose.yml` | Multi-container orchestration (backend + frontend) for deployment |
| `setup.sh` | Automated setup: creates venv, installs deps, initializes DB, installs frontend packages |

---

### Backend — Core

| File | Purpose |
|------|---------|
| `main.py` | FastAPI application factory — mounts routers, configures CORS, lifespan events |
| `requirements.txt` | Pinned Python dependencies for reproducible installs |
| `.env.example` | Template for `OPENAI_API_KEY`, `DATABASE_URL`, `UPLOAD_DIR`, etc. |
| `config.py` | Pydantic `BaseSettings` class — loads and validates environment variables |
| `database.py` | SQLAlchemy engine, session factory, `Base` declarative class, DB initialization |

### Backend — Models (`models/`)

| File | Purpose |
|------|---------|
| `book.py` | `Book` ORM model — id, title, author, grade_level, file_path, upload_date, processing_status, page_count |
| `workbook.py` | `Workbook` ORM model — id, book_id (FK), title, config_json, output_path, created_at, status |

### Backend — Schemas (`schemas/`)

| File | Purpose |
|------|---------|
| `book.py` | `BookCreate`, `BookResponse`, `BookList` — request/response validation |
| `workbook.py` | `WorkbookConfig`, `WorkbookCreate`, `WorkbookResponse` — generation parameters |

### Backend — Routers (`routers/`)

| File | Purpose |
|------|---------|
| `books.py` | CRUD endpoints for books: upload PDF, list, get details, delete, get processing status |
| `workbooks.py` | Generation endpoints: create workbook, list, download .docx, get preview, delete |

### Backend — Services (`services/`)

| File | Purpose |
|------|---------|
| `pdf_extractor.py` | Primary extraction via `pdfplumber`; OCR fallback via `pytesseract` for scanned pages; `pymupdf` for image extraction |
| `content_parser.py` | Splits extracted text into semantic chunks (by chapter/section/topic); detects headings, exercises, theorems, examples |
| `embedding_service.py` | Generates embeddings using `sentence-transformers` (all-MiniLM-L6-v2); builds and persists FAISS indices per book |
| `rag_service.py` | Accepts a query + book_id; retrieves top-k relevant chunks from FAISS; formats context for LLM prompt |
| `llm_service.py` | Manages OpenAI API calls; prompt templates for exercise generation, solution creation, difficulty calibration |
| `docx_generator.py` | Assembles final .docx workbook using `python-docx`; handles headers, footers, page numbers, exercise formatting, answer keys |

### Backend — Utils (`utils/`)

| File | Purpose |
|------|---------|
| `arabic_utils.py` | Reshapes Arabic text for correct rendering in .docx; handles BiDi algorithm for mixed LTR/RTL content |
| `file_utils.py` | Safe filename generation, path resolution, temp file cleanup, storage quota checks |

### Backend — Data (`data/`)

| Directory/File | Purpose |
|----------------|---------|
| `uploads/` | Raw uploaded PDF files, organized by book ID |
| `workbooks/` | Generated .docx files ready for download |
| `faiss_indices/` | Serialized FAISS index files, one directory per book |
| `mathcraft.db` | SQLite database file (auto-created on first run) |

---

### Frontend — Core

| File | Purpose |
|------|---------|
| `main.jsx` | React DOM root mount, router provider |
| `App.jsx` | Top-level routing configuration (React Router) |
| `index.css` | Tailwind directives + global custom styles |
| `api/client.js` | Centralized HTTP client (Axios) with base URL, interceptors, error handling |

### Frontend — Components

| Directory | Components | Purpose |
|-----------|-----------|---------|
| `layout/` | Header, Sidebar, Layout | App shell — persistent navigation, responsive sidebar, content wrapper |
| `upload/` | DropZone, MetadataForm, ProgressBar | PDF upload flow — drag-and-drop, book metadata entry, upload progress |
| `wizard/` | WizardContainer, StepIndicator, ScopeSelection, WorkbookStructure, ExerciseConfig, FormattingStyle | Multi-step workbook configuration wizard |
| `workbook/` | WorkbookCard, PreviewPanel | Workbook display — card grid for listing, live preview of generated content |
| `common/` | Button, Card, Modal, Slider, Toggle | Reusable UI primitives with consistent styling |

### Frontend — Pages

| File | Purpose |
|------|---------|
| `Dashboard.jsx` | Landing page — book library overview, recent workbooks, quick actions |
| `UploadPage.jsx` | Full upload experience — DropZone + MetadataForm + processing status |
| `WorkbookBuilder.jsx` | Wizard-driven workbook configuration and generation trigger |
| `ResultsPage.jsx` | Generated workbook display — preview, download, regenerate options |

### Frontend — Hooks

| File | Purpose |
|------|---------|
| `useBooks.js` | Data fetching/mutation for books (list, upload, delete, status polling) |
| `useWorkbooks.js` | Data fetching/mutation for workbooks (create, list, download, delete) |

### Frontend — Utils

| File | Purpose |
|------|---------|
| `constants.js` | API base URL, difficulty levels, exercise types, grade options, wizard step definitions |

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MathCraft Data Flow                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

 ┌──────────┐     ┌───────────┐     ┌──────────┐     ┌──────────┐     ┌─────────┐
 │  UPLOAD  │────▶│  EXTRACT  │────▶│  CHUNK   │────▶│  EMBED   │────▶│  STORE  │
 │          │     │           │     │          │     │          │     │         │
 │ User     │     │ pdfplumber│     │ content  │     │ sentence │     │ FAISS   │
 │ uploads  │     │ pytesseract│    │ _parser  │     │ transform│     │ index   │
 │ PDF      │     │ pymupdf   │     │          │     │ ers      │     │ SQLite  │
 └──────────┘     └───────────┘     └──────────┘     └──────────┘     └─────────┘
                                                                            │
                                                                            ▼
 ┌──────────┐     ┌───────────┐     ┌──────────┐                     ┌─────────┐
 │ DOWNLOAD │◀────│ GENERATE  │◀────│ RETRIEVE │◀────────────────────│  QUERY  │
 │          │     │           │     │          │                     │         │
 │ User     │     │ OpenAI    │     │ rag      │                     │ User    │
 │ gets     │     │ LLM +     │     │ _service │                     │ configs │
 │ .docx    │     │ python-   │     │ top-k    │                     │ wizard  │
 │          │     │ docx      │     │ chunks   │                     │         │
 └──────────┘     └───────────┘     └──────────┘                     └─────────┘
```

### Step-by-Step Flow

```
1. UPLOAD    → User uploads a math textbook PDF via the frontend DropZone
                 ↓
2. EXTRACT   → pdf_extractor.py processes the PDF
               • pdfplumber extracts text from digital PDFs
               • pytesseract OCRs scanned/image-based pages
               • pymupdf extracts embedded images (diagrams, figures)
                 ↓
3. CHUNK     → content_parser.py splits extracted text into semantic units
               • Detects chapters, sections, topics
               • Identifies exercise blocks, theorems, examples
               • Preserves mathematical notation context
                 ↓
4. EMBED     → embedding_service.py generates vector representations
               • Uses sentence-transformers (all-MiniLM-L6-v2)
               • Creates 384-dimensional embeddings per chunk
                 ↓
5. STORE     → Persists data for later retrieval
               • FAISS index saved to data/faiss_indices/{book_id}/
               • Book metadata saved to SQLite
               • Chunk text + metadata stored for reconstruction
                 ↓
6. RETRIEVE  → rag_service.py finds relevant content
               • User's wizard config translated to semantic queries
               • FAISS similarity search returns top-k chunks
               • Context window assembled from retrieved chunks
                 ↓
7. GENERATE  → llm_service.py + docx_generator.py create the workbook
               • LLM generates exercises based on retrieved context
               • Difficulty calibrated to user's selected level
               • python-docx assembles formatted .docx document
                 ↓
8. DOWNLOAD  → User downloads the generated .docx workbook
               • File served from data/workbooks/{workbook_id}.docx
               • Preview available in-browser before download
```

---

## API Endpoint Summary

### Books Router (`/api/books`)

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/api/books/upload` | Upload a new PDF textbook | `multipart/form-data` (file + metadata) | `BookResponse` (201) |
| `GET` | `/api/books` | List all uploaded books | — | `BookResponse[]` |
| `GET` | `/api/books/{book_id}` | Get book details + processing status | — | `BookResponse` |
| `GET` | `/api/books/{book_id}/chapters` | Get detected chapter structure | — | `ChapterList` |
| `DELETE` | `/api/books/{book_id}` | Delete book and associated data | — | 204 No Content |

### Workbooks Router (`/api/workbooks`)

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/api/workbooks/generate` | Trigger workbook generation | `WorkbookConfig` JSON | `WorkbookResponse` (202) |
| `GET` | `/api/workbooks` | List all generated workbooks | — | `WorkbookResponse[]` |
| `GET` | `/api/workbooks/{workbook_id}` | Get workbook details + status | — | `WorkbookResponse` |
| `GET` | `/api/workbooks/{workbook_id}/preview` | Get HTML preview of workbook | — | HTML content |
| `GET` | `/api/workbooks/{workbook_id}/download` | Download generated .docx file | — | `application/octet-stream` |
| `DELETE` | `/api/workbooks/{workbook_id}` | Delete workbook and .docx file | — | 204 No Content |

### Health & Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/status/{book_id}` | Processing pipeline status (extraction, chunking, embedding) |

---

## Key Design Decisions

### 1. FAISS over ChromaDB

| Factor | FAISS | ChromaDB |
|--------|-------|----------|
| **Deployment** | Zero external dependencies — single `.faiss` file | Requires separate server process or embedded mode |
| **Performance** | Optimized C++ core; handles millions of vectors | Python-heavy; slower for large indices |
| **Simplicity** | File-based persistence — easy backup/restore | Requires collection management overhead |
| **Memory** | Flat index fits entirely in RAM for fast search | Additional abstraction layers consume memory |
| **Use case fit** | Per-book indices (thousands of chunks, not millions) are ideal for flat FAISS | Overkill for our scale |

**Decision**: FAISS provides the best performance-to-complexity ratio for per-book vector stores with thousands of chunks each.

---

### 2. python-docx over LaTeX

| Factor | python-docx | LaTeX |
|--------|-------------|-------|
| **Output format** | Native .docx — universally editable | PDF only — not easily editable by teachers |
| **Dependencies** | Pure Python — pip install | Requires full TeX distribution (2+ GB) |
| **Formatting control** | Programmatic styles, tables, headers | Powerful but complex templating |
| **User expectation** | Teachers expect Word documents they can modify | PDF is final — no customization after generation |
| **Arabic/RTL** | Supported via python-bidi + arabic-reshaper | Requires XeLaTeX + complex font configuration |
| **Deployment** | No system dependencies | TeX Live/MiKTeX installation required |

**Decision**: Teachers need editable workbooks. python-docx produces .docx files that can be opened in Word, Google Docs, or LibreOffice for further customization.

---

### 3. SQLite over PostgreSQL

| Factor | SQLite | PostgreSQL |
|--------|--------|------------|
| **Setup** | Zero configuration — file-based | Requires server installation and management |
| **Deployment** | Single file in `data/` directory | Separate service to maintain |
| **Scale** | Handles thousands of books easily | Designed for millions of concurrent connections |
| **Backup** | Copy one file | pg_dump + restore procedures |
| **Use case fit** | Single-user/small-team tool | Enterprise multi-tenant applications |

**Decision**: MathCraft is a productivity tool, not a SaaS platform. SQLite eliminates infrastructure complexity while handling the expected data volume effortlessly.

---

### 4. Sentence-Transformers over OpenAI Embeddings

| Factor | Sentence-Transformers | OpenAI Embeddings |
|--------|----------------------|-------------------|
| **Cost** | Free — runs locally | $0.0001/1K tokens (adds up with large books) |
| **Privacy** | Book content never leaves the server | Content sent to OpenAI servers |
| **Latency** | Local inference — no network round-trip | API call latency per batch |
| **Offline** | Works without internet | Requires API connectivity |
| **Quality** | all-MiniLM-L6-v2 is excellent for semantic search | Slightly better for nuanced queries |

**Decision**: Local embeddings eliminate per-book processing costs and keep textbook content private. The quality difference is negligible for math content retrieval.

---

### 5. Multi-step Wizard over Single Form

| Factor | Rationale |
|--------|-----------|
| **Cognitive load** | Breaking configuration into steps prevents overwhelming users |
| **Validation** | Each step validates independently before proceeding |
| **Flexibility** | Steps can be skipped or revisited |
| **Guidance** | Each step provides contextual help and previews |

**Wizard Steps**:
1. **Scope Selection** — Choose book, chapters, or specific topics
2. **Workbook Structure** — Number of sections, exercises per section
3. **Exercise Configuration** — Types (multiple choice, fill-in, word problems), difficulty distribution
4. **Formatting & Style** — Language, RTL support, header/footer, answer key inclusion

---

### 6. pdfplumber + pytesseract Dual Strategy

| Scenario | Tool | Reason |
|----------|------|--------|
| Digital/text-based PDFs | pdfplumber | Fast, accurate, preserves layout |
| Scanned/image-based pages | pytesseract | OCR fallback for non-digital content |
| Mixed documents | Both | Page-by-page detection of text vs. image content |
| Diagram extraction | pymupdf | Extracts embedded images for reference |

**Decision**: Math textbooks come in all formats — from modern digital PDFs to scanned copies of older books. The dual strategy ensures maximum compatibility.

---

### 7. Per-Book FAISS Indices over Single Global Index

| Factor | Rationale |
|--------|-----------|
| **Isolation** | Each book's content is self-contained — no cross-contamination |
| **Performance** | Smaller indices = faster search |
| **Management** | Delete a book = delete its index file |
| **Relevance** | Workbook generation targets a specific book — global search adds noise |

---

## Technology Stack Summary

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                           │
│  React 18 · Vite · Tailwind CSS · React Router      │
│  Axios · Framer Motion                              │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP/REST
┌──────────────────────▼──────────────────────────────┐
│                    BACKEND                            │
│  Python 3.11+ · FastAPI · SQLAlchemy · Pydantic     │
│  pdfplumber · pytesseract · pymupdf                 │
│  sentence-transformers · FAISS · LangChain          │
│  OpenAI API · python-docx                           │
│  arabic-reshaper · python-bidi                      │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                   STORAGE                             │
│  SQLite (metadata) · FAISS files (vectors)          │
│  File system (PDFs + DOCX)                          │
└─────────────────────────────────────────────────────┘
```

---

*This document serves as the canonical architecture reference for MathCraft. All implementation should follow this structure.*
