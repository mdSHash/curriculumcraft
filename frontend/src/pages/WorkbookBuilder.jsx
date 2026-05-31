import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertCircle } from 'lucide-react'
import { booksApi, examsApi } from '../api/client'
import { useWorkbooks } from '../hooks/useWorkbooks'
import WizardContainer from '../components/wizard/WizardContainer'

export default function WorkbookBuilder() {
  const { bookId } = useParams()
  const navigate = useNavigate()
  const { generateWorkbook } = useWorkbooks()

  const [bookInfo, setBookInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    const fetchBook = async () => {
      setLoading(true)
      try {
        const res = await booksApi.getOutline(bookId)
        setBookInfo(res.data)
        setError(null)
      } catch (err) {
        setError(err.response?.data?.detail || 'Book not found')
      } finally {
        setLoading(false)
      }
    }
    fetchBook()
  }, [bookId])

  const handleGenerate = async (config) => {
    setGenerating(true)
    try {
      // Check if this is an exam generation request
      if (config.structure.output_mode === 'exam_quiz') {
        const examPayload = {
          scope: config.scope,
          structure: config.exam?.structure || {},
          formatting: config.exam?.formatting || {},
        }
        const res = await examsApi.generate(examPayload)
        navigate(`/exam-results/${res.data.id}`)
      } else {
        const result = await generateWorkbook(config)
        navigate(`/results/${result.id}`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : (typeof err === 'string' ? err : 'Failed to start generation'))
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto flex items-center justify-center py-24">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 border-b-2 border-blue-600 rounded-full animate-spin" />
          <span className="text-gray-600">Loading book information...</span>
        </div>
      </div>
    )
  }

  if (error && !bookInfo) {
    return (
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-red-50 border border-red-200 rounded-xl p-8 text-center"
        >
          <AlertCircle size={40} className="mx-auto text-red-400 mb-3" />
          <h2 className="text-lg font-semibold text-red-800 mb-1">Book Not Found</h2>
          <p className="text-sm text-red-600 mb-4">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
          >
            Back to Dashboard
          </button>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mb-6"
      >
        <h1 className="text-2xl font-bold text-gray-900">Workbook Builder</h1>
        <p className="text-sm text-gray-500 mt-1">
          Configure and generate a custom workbook from <span className="font-medium text-gray-700">{bookInfo?.title}</span>
        </p>
      </motion.div>

      {error && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2"
        >
          <AlertCircle size={16} className="text-red-500 flex-shrink-0" />
          <p className="text-sm text-red-700">{error}</p>
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <WizardContainer
          bookId={bookId}
          bookInfo={bookInfo}
          onGenerate={handleGenerate}
          generating={generating}
        />
      </motion.div>
    </div>
  )
}
