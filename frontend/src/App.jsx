import { Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import UploadPage from './pages/UploadPage'
import WorkbookBuilder from './pages/WorkbookBuilder'
import ResultsPage from './pages/ResultsPage'
import ExamResultsPage from './pages/ExamResultsPage'
import WorkbooksPage from './pages/WorkbooksPage'
import SettingsPage from './pages/SettingsPage'

function App() {
  return (
    <>
      <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="builder/:bookId" element={<WorkbookBuilder />} />
          <Route path="results/:workbookId" element={<ResultsPage />} />
          <Route path="exam-results/:examId" element={<ExamResultsPage />} />
          <Route path="workbooks" element={<WorkbooksPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </>
  )
}

export default App
