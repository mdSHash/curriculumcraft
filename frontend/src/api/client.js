import axios from 'axios'
import { getApiBaseUrl } from '../utils/apiConfig'

const api = axios.create({
  headers: {
    'Content-Type': 'application/json',
  },
})

// Resolve baseURL per-request so localStorage updates take effect immediately
// (no full page reload needed after the user changes the backend URL).
api.interceptors.request.use((config) => {
  config.baseURL = `${getApiBaseUrl()}/api`
  return config
})

// Books API
export const booksApi = {
  upload: (formData, onProgress) =>
    api.post('/books/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    }),
  list: () => api.get('/books'),
  getOutline: (bookId) => api.get(`/books/${bookId}/outline`),
  delete: (bookId) => api.delete(`/books/${bookId}`),
}

// Workbooks API
export const workbooksApi = {
  generate: (config) => api.post('/workbooks/generate', config),
  list: () => api.get('/workbooks'),
  getStatus: (workbookId) => api.get(`/workbooks/${workbookId}/status`),
  get: (workbookId) => api.get(`/workbooks/${workbookId}`),
  download: (workbookId) => api.get(`/workbooks/${workbookId}/download`, { responseType: 'blob' }),
  delete: (workbookId) => api.delete(`/workbooks/${workbookId}`),
}

// Exams API
export const examsApi = {
  generate: (config) => api.post('/exams/generate', config),
  list: () => api.get('/exams'),
  getStatus: (examId) => api.get(`/exams/${examId}/status`),
  get: (examId) => api.get(`/exams/${examId}`),
  download: (examId) => api.get(`/exams/${examId}/download`, { responseType: 'blob' }),
  downloadAnswerKey: (examId) => api.get(`/exams/${examId}/download-answer-key`, { responseType: 'blob' }),
  delete: (examId) => api.delete(`/exams/${examId}`),
}

// MOE eLibrary API. `subject` is now an optional canonical key (e.g. 'math',
// 'arabic_lang', 'physics') OR null/undefined to span all subjects in the
// catalog. Pre-Phase-2 callers that passed 'math' explicitly keep working.
function moeParams(subject, grade, stage, week) {
  const p = {}
  if (subject) p.subject = subject
  if (grade) p.grade = grade
  if (stage) p.stage = stage
  if (week !== undefined && week !== null) p.week = week
  return p
}

export const moeLibraryApi = {
  getBooks: (subject = null, grade = null, stage = null) =>
    api.get('/moe-library/books', { params: moeParams(subject, grade, stage) }),
  getStages: (subject = null) =>
    api.get('/moe-library/stages', { params: moeParams(subject) }),
  getCatalogSubjects: () => api.get('/moe-library/catalog-subjects'),
  importBook: (bookId) => api.post('/moe-library/import', { book_id: bookId }),

  // Official weekly assessments (cha/books.json)
  getAssessments: ({ subject = null, grade = null, stage = null, week = null } = {}) =>
    api.get('/moe-library/assessments', {
      params: moeParams(subject, grade, stage, week),
    }),
  getAssessmentGrades: (subject = null) =>
    api.get('/moe-library/assessments/grades', { params: moeParams(subject) }),
}

// Canonical Subject taxonomy (the 24-key list seeded from
// backend/seeds/subjects.json). Used by SubjectPicker and the wizard
// to render subject-aware UI.
export const subjectsApi = {
  list: () => api.get('/subjects'),
  get: (key) => api.get(`/subjects/${key}`),
  getConfig: (key) => api.get(`/subjects/${key}/config`),
}

export default api
