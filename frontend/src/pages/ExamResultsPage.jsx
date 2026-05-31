import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, CheckCircle2, AlertCircle, Loader2, FileText, Key } from 'lucide-react'
import { examsApi } from '../api/client'
import GenerationProgress from '../components/common/GenerationProgress'

const GENERATION_STAGES = [
  { key: 'retrieving', label: 'Retrieving curriculum content', icon: '📚' },
  { key: 'generating', label: 'Generating exam questions', icon: '✏️' },
  { key: 'answer_key', label: 'Building answer key', icon: '🔑' },
  { key: 'assembling', label: 'Assembling exam document', icon: '📄' },
  { key: 'finalizing', label: 'Finalizing documents', icon: '✨' },
]

export default function ExamResultsPage() {
  const { examId } = useParams()
  const navigate = useNavigate()

  const [status, setStatus] = useState('generating')
  const [examData, setExamData] = useState(null)
  const [serverProgress, setServerProgress] = useState(0)
  const [serverMessage, setServerMessage] = useState(null)
  const [downloading, setDownloading] = useState(false)
  const [downloadingKey, setDownloadingKey] = useState(false)
  const [error, setError] = useState(null)
  const pollIntervalRef = useRef(null)

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await examsApi.getStatus(examId)
        const data = res.data
        if (typeof data.progress === 'number') setServerProgress(data.progress)
        if (data.progress_message !== undefined) setServerMessage(data.progress_message)
        if (data.status === 'ready') {
          setStatus('ready')
          setServerProgress(100)
          fetchExamDetails()
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
        } else if (data.status === 'error') {
          setStatus('error')
          setError(data.error || 'Generation failed')
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
        }
      } catch (err) {
        // Continue polling
      }
    }

    checkStatus()
    pollIntervalRef.current = setInterval(checkStatus, 2000)

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [examId])

  const fetchExamDetails = async () => {
    try {
      const res = await examsApi.get(examId)
      setExamData(res.data)
    } catch (err) {
      // Non-critical
    }
  }

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const res = await examsApi.download(examId)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', examData?.filename || `exam-${examId}.docx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError('Download failed')
    } finally {
      setDownloading(false)
    }
  }

  const handleDownloadAnswerKey = async () => {
    setDownloadingKey(true)
    try {
      const res = await examsApi.downloadAnswerKey(examId)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', examData?.answer_key_filename || `exam-${examId}-answer-key.docx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError('Answer key download failed')
    } finally {
      setDownloadingKey(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mb-8"
      >
        <h1 className="text-2xl font-bold text-gray-900">Exam Results</h1>
        <p className="text-sm text-gray-500 mt-1">
          {status === 'generating' ? 'Your exam is being generated...' : 'Your exam is ready'}
        </p>
      </motion.div>

      <AnimatePresence mode="wait">
        {/* Generating State */}
        {status === 'generating' && (
          <div key="generating">
            <GenerationProgress
              heading="Generating Your Exam"
              stages={GENERATION_STAGES}
              serverProgress={serverProgress}
              serverMessage={serverMessage}
              expectedSeconds={120}
            />
          </div>
        )}

        {/* Ready State */}
        {status === 'ready' && (
          <motion.div
            key="ready"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
            className="space-y-6"
          >
            {/* Success banner */}
            <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 200, damping: 15 }}
              >
                <CheckCircle2 size={48} className="mx-auto text-green-500 mb-3" />
              </motion.div>
              <h2 className="text-lg font-semibold text-green-800">Exam Generated Successfully!</h2>
              <p className="text-sm text-green-600 mt-1">
                Your exam document is ready for download
              </p>
            </div>

            {/* Exam details */}
            {examData && (
              <div className="bg-white border border-gray-200 rounded-xl p-6">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">Exam Summary</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Title:</span>
                    <span className="ml-2 font-medium text-gray-900">{examData.title}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Type:</span>
                    <span className="ml-2 font-medium text-gray-900">
                      {examData.exam_type === 'quiz' ? 'Short Quiz' : 'Monthly Exam'}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Total Marks:</span>
                    <span className="ml-2 font-medium text-gray-900">{examData.total_marks}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Duration:</span>
                    <span className="ml-2 font-medium text-gray-900">{examData.duration_minutes} min</span>
                  </div>
                  {examData.num_variants > 1 && (
                    <div>
                      <span className="text-gray-500">Variants:</span>
                      <span className="ml-2 font-medium text-gray-900">{examData.num_variants}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Download buttons */}
            <div className="flex flex-col sm:flex-row gap-3">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleDownload}
                disabled={downloading}
                className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors shadow-md shadow-blue-200 disabled:opacity-50"
              >
                {downloading ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <FileText size={18} />
                )}
                {downloading ? 'Downloading...' : 'Download Exam'}
              </motion.button>

              {examData?.answer_key_filename && (
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleDownloadAnswerKey}
                  disabled={downloadingKey}
                  className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-xl font-semibold hover:bg-emerald-700 transition-colors shadow-md shadow-emerald-200 disabled:opacity-50"
                >
                  {downloadingKey ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <Key size={18} />
                  )}
                  {downloadingKey ? 'Downloading...' : 'Download Answer Key'}
                </motion.button>
              )}
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-between pt-4">
              <button
                onClick={() => navigate(-1)}
                className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
              >
                <ArrowLeft size={16} />
                Back to Builder
              </button>
              <button
                onClick={() => navigate('/')}
                className="text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors"
              >
                Go to Dashboard
              </button>
            </div>
          </motion.div>
        )}

        {/* Error State */}
        {status === 'error' && (
          <motion.div
            key="error"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
            className="bg-red-50 border border-red-200 rounded-xl p-8 text-center"
          >
            <AlertCircle size={48} className="mx-auto text-red-400 mb-3" />
            <h2 className="text-lg font-semibold text-red-800 mb-1">Generation Failed</h2>
            <p className="text-sm text-red-600 mb-6">{error}</p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => navigate(-1)}
                className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
              >
                <ArrowLeft size={14} className="inline mr-1" />
                Back to Builder
              </button>
              <button
                onClick={() => navigate('/')}
                className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
              >
                Go to Dashboard
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
