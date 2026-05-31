import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Download, ArrowLeft, Plus, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { useWorkbooks } from '../hooks/useWorkbooks'
import { workbooksApi } from '../api/client'

const GENERATION_STAGES = [
  { key: 'retrieving', label: 'Retrieving curriculum content...', icon: '📚' },
  { key: 'generating', label: 'Generating exercises...', icon: '✏️' },
  { key: 'assembling', label: 'Assembling workbook...', icon: '📄' },
  { key: 'finalizing', label: 'Finalizing document...', icon: '✨' },
]

export default function ResultsPage() {
  const { workbookId } = useParams()
  const navigate = useNavigate()
  const { pollStatus, downloadWorkbook } = useWorkbooks()

  const [status, setStatus] = useState('generating') // generating | ready | error
  const [workbookData, setWorkbookData] = useState(null)
  const [currentStage, setCurrentStage] = useState(0)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState(null)
  const stageIntervalRef = useRef(null)

  // Simulate stage progression while generating
  useEffect(() => {
    if (status === 'generating') {
      stageIntervalRef.current = setInterval(() => {
        setCurrentStage((prev) => {
          if (prev < GENERATION_STAGES.length - 1) return prev + 1
          return prev
        })
      }, 3000)
    }

    return () => {
      if (stageIntervalRef.current) {
        clearInterval(stageIntervalRef.current)
      }
    }
  }, [status])

  // Poll for status
  // Fetch full workbook details when ready
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
        if (res.data.status === 'ready') {
          setStatus('ready')
          fetchWorkbookDetails()
          if (stageIntervalRef.current) clearInterval(stageIntervalRef.current)
        } else if (res.data.status === 'error') {
          setStatus('error')
          setError(res.data.error || 'Generation failed')
          if (stageIntervalRef.current) clearInterval(stageIntervalRef.current)
        }
      } catch (err) {
        // Continue polling
      }
    }

    // Initial check
    checkStatus()

    // Start polling
    pollStatus(workbookId, (data) => {
      if (data.status === 'ready') {
        setStatus('ready')
        fetchWorkbookDetails()
        if (stageIntervalRef.current) clearInterval(stageIntervalRef.current)
      } else if (data.status === 'error') {
        setStatus('error')
        setError(data.error || 'Generation failed')
        if (stageIntervalRef.current) clearInterval(stageIntervalRef.current)
      }
    })
  }, [workbookId])

  const handleDownload = async () => {
    setDownloading(true)
    try {
      await downloadWorkbook(workbookId)
    } catch (err) {
      setError(err instanceof Error ? err.message : (typeof err === 'string' ? err : 'Download failed'))
    } finally {
      setDownloading(false)
    }
  }

  const handleRetry = () => {
    setStatus('generating')
    setCurrentStage(0)
    setError(null)
    pollStatus(workbookId, (data) => {
      if (data.status === 'ready') {
        setStatus('ready')
        setWorkbookData(data)
      } else if (data.status === 'error') {
        setStatus('error')
        setError(data.error || 'Generation failed')
      }
    })
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
          <motion.div
            key="generating"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
            className="bg-white border border-gray-200 rounded-xl p-8"
          >
            <div className="text-center mb-8">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                className="inline-block mb-4"
              >
                <Loader2 size={40} className="text-blue-500" />
              </motion.div>
              <h2 className="text-lg font-semibold text-gray-900">Generating Your Workbook</h2>
              <p className="text-sm text-gray-500 mt-1">This may take a minute or two</p>
            </div>

            {/* Progress stages */}
            <div className="space-y-3 max-w-sm mx-auto">
              {GENERATION_STAGES.map((stage, index) => {
                const isActive = index === currentStage
                const isCompleted = index < currentStage
                const isFuture = index > currentStage

                return (
                  <motion.div
                    key={stage.key}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className={`
                      flex items-center gap-3 p-3 rounded-lg transition-all duration-300
                      ${isActive ? 'bg-blue-50 border border-blue-200' : ''}
                      ${isCompleted ? 'opacity-60' : ''}
                      ${isFuture ? 'opacity-30' : ''}
                    `}
                  >
                    <span className="text-lg">{stage.icon}</span>
                    <span className={`text-sm ${isActive ? 'font-medium text-blue-700' : 'text-gray-600'}`}>
                      {stage.label}
                    </span>
                    {isActive && (
                      <motion.div
                        animate={{ opacity: [0.4, 1, 0.4] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                        className="ml-auto w-2 h-2 rounded-full bg-blue-500"
                      />
                    )}
                    {isCompleted && (
                      <CheckCircle2 size={16} className="ml-auto text-green-500" />
                    )}
                  </motion.div>
                )
              })}
            </div>

            {/* Progress bar */}
            <div className="mt-8 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-blue-500 rounded-full"
                initial={{ width: '5%' }}
                animate={{ width: `${((currentStage + 1) / GENERATION_STAGES.length) * 90}%` }}
                transition={{ duration: 0.5 }}
              />
            </div>
          </motion.div>
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
                onClick={handleRetry}
                className="px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                Try Again
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
