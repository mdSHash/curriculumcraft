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

// MOE eLibrary API
export const moeLibraryApi = {
  getBooks: (subject = 'math', grade, stage) =>
    api.get('/moe-library/books', { params: { subject, grade, stage } }),
  getStages: () => api.get('/moe-library/stages'),
  importBook: (bookId) => api.post('/moe-library/import', { book_id: bookId }),

  // Official weekly assessments (cha/books.json)
  getAssessments: ({ subject = 'math', grade, stage, week } = {}) =>
    api.get('/moe-library/assessments', { params: { subject, grade, stage, week } }),
  getAssessmentGrades: () => api.get('/moe-library/assessments/grades'),
}

export default api
