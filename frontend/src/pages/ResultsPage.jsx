import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Download, ArrowLeft, Plus, CheckCircle2, AlertCircle } from 'lucide-react'
import { workbooksApi } from '../api/client'
import GenerationProgress from '../components/common/GenerationProgress'

const GENERATION_STAGES = [
  { key: 'retrieving', label: 'Retrieving curriculum content', icon: '📚' },
  { key: 'generating', label: 'Generating exercises', icon: '✏️' },
  { key: 'assembling', label: 'Assembling workbook', icon: '📄' },
  { key: 'finalizing', label: 'Finalizing document', icon: '✨' },
]

export default function ResultsPage() {
  const { workbookId } = useParams()
  const navigate = useNavigate()

  const [status, setStatus] = useState('generating') // generating | ready | error
  const [workbookData, setWorkbookData] = useState(null)
  const [serverProgress, setServerProgress] = useState(0)
  const [serverMessage, setServerMessage] = useState(null)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState(null)
  const pollIntervalRef = useRef(null)

  const fetchWorkbookDetails = async () => {
    try {
      const res = await workbooksApi.get(workbookId)
      setWorkbookData(res.data)
    } catch (err) {
      // Non-critical — summary just won't show
    }
  }

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await workbooksApi.getStatus(workbookId)
        const data = res.data
        if (typeof data.progress === 'number') setServerProgress(data.progress)
        if (data.progress_message !== undefined) setServerMessage(data.progress_message)
        if (data.status === 'ready') {
          setStatus('ready')
          setServerProgress(100)
          fetchWorkbookDetails()
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
  }, [workbookId])

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const res = await workbooksApi.download(workbookId)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', workbookData?.filename || `workbook-${workbookId}.docx`)
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

  return (
    <div className="max-w-3xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mb-8"
      >
        <h1 className="text-2xl font-bold text-gray-900">Workbook Results</h1>
        <p className="text-sm text-gray-500 mt-1">
          {status === 'generating' ? 'Your workbook is being generated...' : 'Your workbook is ready'}
        </p>
      </motion.div>

      <AnimatePresence mode="wait">
        {/* Generating State */}
        {status === 'generating' && (
          <div key="generating">
            <GenerationProgress
              heading="Generating Your Workbook"
              stages={GENERATION_STAGES}
              serverProgress={serverProgress}
              serverMessage={serverMessage}
              expectedSeconds={90}
            />
          </div>
        )}

        {/* Ready State */}
        {status === 'ready' && (
          <motion.div
            key="ready"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
            className="bg-white border border-gray-200 rounded-xl p-8 text-center"
          >
            {/* Success animation */}
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.2 }}
              className="mb-6"
            >
              <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mx-auto">
                <motion.div
                  initial={{ scale: 0, rotate: -180 }}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.4 }}
                >
                  <CheckCircle2 size={40} className="text-green-600" />
                </motion.div>
              </div>
            </motion.div>

            {/* Confetti-like dots */}
            <div className="relative">
              {[...Array(8)].map((_, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, scale: 0, y: 0 }}
                  animate={{
                    opacity: [0, 1, 0],
                    scale: [0, 1, 0.5],
                    y: [-20, -60 - Math.random() * 40],
                    x: (Math.random() - 0.5) * 120,
                  }}
                  transition={{ duration: 1.2, delay: 0.3 + i * 0.1 }}
                  className={`absolute left-1/2 top-0 w-2 h-2 rounded-full ${
                    ['bg-blue-400', 'bg-green-400', 'bg-amber-400', 'bg-purple-400', 'bg-pink-400', 'bg-cyan-400', 'bg-red-400', 'bg-indigo-400'][i]
                  }`}
                />
              ))}
            </div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
            >
              <h2 className="text-xl font-bold text-gray-900 mb-2">Workbook Ready!</h2>
              <p className="text-sm text-gray-500 mb-6">
                Your workbook has been generated successfully
              </p>
            </motion.div>

            {/* Workbook summary */}
            {workbookData && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
                className="bg-gray-50 rounded-lg p-4 mb-8 text-left max-w-sm mx-auto"
              >
                <div className="space-y-2">
                  {workbookData.title && (
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-500">Title</span>
                      <span className="text-xs font-medium text-gray-900">{workbookData.title}</span>
                    </div>
                  )}
                  {workbookData.total_pages && (
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-500">Pages</span>
                      <span className="text-xs font-medium text-gray-900">{workbookData.total_pages}</span>
                    </div>
                  )}
                  {workbookData.exercise_count && (
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-500">Exercises</span>
                      <span className="text-xs font-medium text-gray-900">{workbookData.exercise_count}</span>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* Actions */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="space-y-3"
            >
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="w-full max-w-xs mx-auto flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 shadow-lg shadow-blue-200 transition-all disabled:opacity-60"
              >
                {downloading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Downloading...
                  </>
                ) : (
                  <>
                    <Download size={18} />
                    Download .docx
                  </>
                )}
              </button>

              <div className="flex items-center justify-center gap-4 pt-2">
                <button
                  onClick={() => navigate(-1)}
                  className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors"
                >
                  <Plus size={14} />
                  Create Another Workbook
                </button>
                <span className="text-gray-300">|</span>
                <button
                  onClick={() => navigate('/')}
                  className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
                >
                  <ArrowLeft size={14} />
                  Back to Dashboard
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* Error State */}
        {status === 'error' && (
          <motion.div
            key="error"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="bg-white border border-red-200 rounded-xl p-8 text-center"
          >
            <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
              <AlertCircle size={32} className="text-red-500" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Generation Failed</h2>
            <p className="text-sm text-red-600 mb-6">{error || 'An unexpected error occurred'}</p>

            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => navigate(-1)}
                className="px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                Back to Builder
              </button>
              <button
                onClick={() => navigate('/')}
                className="px-5 py-2.5 border border-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
              >
                Back to Dashboard
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
