---
title: MathCraft API
emoji: 🧮
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
short_description: Egyptian-curriculum math workbook & exam generator API.
---

# MathCraft API

This Space hosts the FastAPI backend for **MathCraft** — an AI-powered generator for Egyptian-curriculum math workbooks, quizzes, and MOE-style weekly assessments.

The frontend lives on GitHub Pages: <https://mdshash.github.io/mathcraft/>

Source code: <https://github.com/mdSHash/mathcraft>

## Endpoints

- `GET /api/health` — liveness probe
- `POST /api/books/upload` — upload a textbook PDF
- `POST /api/workbooks/generate` — generate a workbook
- `POST /api/exams/generate` — generate an exam
- Interactive docs: [/docs](/docs)

## Notes

- Storage is ephemeral. Uploaded books, FAISS indices, generated DOCX files, and the SQLite database are wiped on every Space restart. Download outputs immediately.
- The Space sleeps after 48 h of inactivity. First request after sleep takes ~1 minute to wake.
- This API has **no authentication**. Anyone with the URL can use the Gemini key configured here.
