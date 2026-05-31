import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileText, ChevronRight, Library } from 'lucide-react'
import { booksApi } from '../api/client'
import { useLanguage } from '../i18n/LanguageContext'
import DropZone from '../components/upload/DropZone'
import ProgressBar from '../components/upload/ProgressBar'
import MOELibraryBrowser from '../components/upload/MOELibraryBrowser'
import toast from 'react-hot-toast'

const GRADE_KEYS = [
  'primary1', 'primary2', 'primary3', 'primary4', 'primary5', 'primary6',
  'preparatory1', 'preparatory2', 'preparatory3',
  'secondary1', 'secondary2', 'secondary3',
]

export default function UploadPage() {
  const navigate = useNavigate()
  const { t } = useLanguage()
  const [file, setFile] = useState(null)
  const [metadata, setMetadata] = useState({
    title: '',
    grade: '',
    academic_year: '2024-2025',
    term: '',
    subject: 'Mathematics',
  })
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [currentStage, setCurrentStage] = useState(-1)
  const [completedStages, setCompletedStages] = useState([])
  const [outline, setOutline] = useState(null)
  const [bookId, setBookId] = useState(null)
  const [moeLibraryOpen, setMoeLibraryOpen] = useState(false)

  const STAGES = [
    { key: 'uploading', label: t('upload.stages.uploading') },
    { key: 'extracting', label: t('upload.stages.extracting') },
    { key: 'analyzing', label: t('upload.stages.analyzing') },
    { key: 'indexing', label: t('upload.stages.indexing') },
    { key: 'done', label: t('upload.stages.done') },
  ]

  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile)
    if (selectedFile && !metadata.title) {
      const name = selectedFile.name.replace(/\.(pdf|docx)$/i, '').replace(/[-_]/g, ' ')
      setMetadata((prev) => ({ ...prev, title: name }))
    }
  }

  const handleMetadataChange = (field, value) => {
    setMetadata((prev) => ({ ...prev, [field]: value }))
  }

  const advanceStage = (stageIndex) => {
    setCurrentStage(stageIndex)
    if (stageIndex > 0) {
      setCompletedStages((prev) => [...prev, STAGES[stageIndex - 1].key])
    }
  }

  const handleUpload = async () => {
    if (!file) {
      toast.error(t('upload.errorNoFile'))
      return
    }
    if (!metadata.title.trim()) {
      toast.error(t('upload.errorNoTitle'))
      return
    }

    setUploading(true)
    advanceStage(0)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('title', metadata.title)
    formData.append('grade_level', metadata.grade || '')
    formData.append('academic_year', metadata.academic_year || '')
    formData.append('term', metadata.term || '')
    formData.append('subject', metadata.subject || 'Mathematics')

    try {
      const res = await booksApi.upload(formData, (progressEvent) => {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        setUploadProgress(percent)
        if (percent >= 100) {
          advanceStage(1)
        }
      })

      // Simulate processing stages (backend processes asynchronously)
      advanceStage(2)
      await new Promise((r) => setTimeout(r, 1500))
      advanceStage(3)
      await new Promise((r) => setTimeout(r, 1200))
      advanceStage(4)

      setCompletedStages(STAGES.map((s) => s.key))

      const book = res.data
      setBookId(book.id)

      // Fetch outline
      try {
        const outlineRes = await booksApi.getOutline(book.id)
        setOutline(outlineRes.data)
      } catch {
        // Outline may not be ready yet
      }

      toast.success(t('upload.success'))
    } catch (err) {
      const detail = err.response?.data?.detail
      const errorMessage = detail
        ? (typeof detail === 'string' ? detail : JSON.stringify(detail))
        : (err.message || 'Upload failed. Please try again.')
      toast.error(errorMessage)
      setUploading(false)
      setCurrentStage(-1)
      setCompletedStages([])
      setUploadProgress(0)
    }
  }

  const isComplete = currentStage === 4

  return (
    <div className="max-w-3xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="mb-8"
      >
        <h1 className="text-3xl font-bold text-gray-900 mb-2">{t('upload.title')}</h1>
        <p className="text-gray-600">{t('upload.description')}</p>
      </motion.div>

      <AnimatePresence mode="wait">
        {!uploading ? (
          <motion.div
            key="upload-form"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.4 }}
          >
            {/* Drop Zone */}
            <DropZone file={file} onFileSelect={handleFileSelect} onRemove={() => setFile(null)} />

            {/* MOE Library Section */}
            {!file && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.4 }}
                className="mt-6"
              >
                <div className="relative flex items-center justify-center my-4">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-surface-200" />
                  </div>
                  <span className="relative bg-white px-4 text-sm text-gray-500">
                    {t('moeLibrary.orBrowse')}
                  </span>
                </div>
                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={() => setMoeLibraryOpen(true)}
                  className="w-full flex items-center justify-center gap-3 px-6 py-4 rounded-xl border-2 border-dashed border-primary-200 bg-primary-50/50 hover:bg-primary-50 hover:border-primary-300 transition-all group"
                >
                  <Library size={22} className="text-primary-500 group-hover:text-primary-600" />
                  <span className="text-sm font-medium text-primary-700 group-hover:text-primary-800">
                    {t('moeLibrary.browseBtn')}
                  </span>
                </motion.button>
              </motion.div>
            )}

            {/* Metadata Form */}
            {file && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                transition={{ duration: 0.4 }}
                className="mt-6 card p-6"
              >
                <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('upload.bookDetails')}</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Title */}
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('upload.bookTitle')} *
                    </label>
                    <input
                      type="text"
                      value={metadata.title}
                      onChange={(e) => handleMetadataChange('title', e.target.value)}
                      className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all"
                      placeholder={t('upload.bookTitlePlaceholder')}
                    />
                  </div>

                  {/* Grade - Egypt curriculum */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('upload.gradeLevel')}
                    </label>
                    <select
                      value={metadata.grade}
                      onChange={(e) => handleMetadataChange('grade', e.target.value)}
                      className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all bg-white"
                    >
                      <option value="">{t('upload.selectGrade')}</option>
                      {GRADE_KEYS.map((key) => (
                        <option key={key} value={key}>
                          {t(`grades.${key}`)}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Term - Egypt (Term 1 / Term 2 only) */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('upload.term')}
                    </label>
                    <select
                      value={metadata.term}
                      onChange={(e) => handleMetadataChange('term', e.target.value)}
                      className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all bg-white"
                    >
                      <option value="">{t('upload.selectTerm')}</option>
                      <option value="1">{t('upload.term1')}</option>
                      <option value="2">{t('upload.term2')}</option>
                    </select>
                  </div>

                  {/* Academic Year */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('upload.academicYear')}
                    </label>
                    <input
                      type="text"
                      value={metadata.academic_year}
                      onChange={(e) => handleMetadataChange('academic_year', e.target.value)}
                      className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all"
                      placeholder={t('upload.academicYearPlaceholder')}
                    />
                  </div>

                  {/* Subject */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('upload.subject')}
                    </label>
                    <input
                      type="text"
                      value={metadata.subject}
                      onChange={(e) => handleMetadataChange('subject', e.target.value)}
                      className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all"
                      placeholder="Mathematics"
                    />
                  </div>
                </div>

                {/* Upload Button */}
                <div className="mt-6 flex justify-end">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleUpload}
                    className="btn-primary flex items-center gap-2"
                  >
                    <Upload size={18} />
                    {t('upload.uploadBtn')}
                  </motion.button>
                </div>
              </motion.div>
            )}
          </motion.div>
        ) : (
          <motion.div
            key="progress"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.4 }}
            className="card p-8"
          >
            <ProgressBar
              stages={STAGES}
              currentStage={currentStage}
              completedStages={completedStages}
              uploadProgress={uploadProgress}
            />

            {/* Outline Preview */}
            {isComplete && outline && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="mt-8 border-t border-surface-200 pt-6"
              >
                <h3 className="text-lg font-semibold text-gray-900 mb-3">
                  {t('upload.detectedOutline')}
                </h3>
                <div className="bg-surface-50 rounded-lg p-4 max-h-60 overflow-y-auto">
                  {outline.chapters?.map((chapter, idx) => (
                    <div key={idx} className="flex items-center gap-2 py-1.5">
                      <FileText size={14} className="text-primary-500 flex-shrink-0" />
                      <span className="text-sm text-gray-700">{chapter.title}</span>
                      {chapter.topics_count > 0 && (
                        <span className="text-xs text-gray-400 ms-auto">
                          {chapter.topics_count} {t('upload.topics')}
                        </span>
                      )}
                      {chapter.lessons?.length > 0 && (
                        <span className="text-xs text-gray-400 ms-auto">
                          {chapter.lessons.length} {t('upload.lessons')}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Create Workbook CTA */}
            {isComplete && bookId && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
                className="mt-6 flex justify-center"
              >
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => navigate(`/builder/${bookId}`)}
                  className="btn-primary flex items-center gap-2 text-base px-8 py-3"
                >
                  {t('dashboard.createWorkbook')}
                  <ChevronRight size={18} />
                </motion.button>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* MOE Library Browser Modal */}
      <MOELibraryBrowser
        isOpen={moeLibraryOpen}
        onClose={() => setMoeLibraryOpen(false)}
        onImportSuccess={(importedBook) => {
          setMoeLibraryOpen(false)
          if (importedBook?.id) {
            setBookId(importedBook.id)
            navigate(`/builder/${importedBook.id}`)
          }
        }}
      />
    </div>
  )
}
