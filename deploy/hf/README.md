---
title: CurriculumCraft API
emoji: 🧮
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
short_description: Egyptian-curriculum workbook & exam generator API across all 24 MOE subjects.
---

# CurriculumCraft API

This Space hosts the FastAPI backend for **CurriculumCraft** — an AI-powered generator for Egyptian-curriculum workbooks, quizzes, and MOE-style weekly assessments across all 24 official subjects (math, languages, sciences, ICT, religion, history, and more).

The frontend lives on GitHub Pages: <https://mdshash.github.io/curriculumcraft/>

Source code: <https://github.com/mdSHash/curriculumcraft>

## Endpoints

- `GET /api/health` — liveness probe
- `GET /api/subjects` — canonical 24-subject taxonomy
- `GET /api/moe-library/books?subject={key}` — browse MOE textbooks (any of 24 subjects, or omit for all)
- `GET /api/moe-library/assessments?subject={key}` — browse weekly assessments
- `POST /api/books/upload` — upload a textbook PDF
- `POST /api/workbooks/generate` — generate a workbook
- `POST /api/exams/generate` — generate an exam
- Interactive docs: [/docs](/docs)

## Notes

- Storage is ephemeral. Uploaded books, FAISS indices, generated DOCX files, and the SQLite database are wiped on every Space restart. Download outputs immediately.
- The Space sleeps after 48 h of inactivity. First request after sleep takes ~1 minute to wake.
- This API has **no authentication**. Anyone with the URL can use the Gemini key configured here.
