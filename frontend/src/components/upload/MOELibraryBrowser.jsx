import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BookOpen, Download, Check, Loader2, X, Library, GraduationCap } from 'lucide-react'
import { moeLibraryApi } from '../../api/client'
import { useLanguage } from '../../i18n/LanguageContext'
import toast from 'react-hot-toast'

const STAGES = [
  { key: null, labelKey: 'allStages' },
  { key: 'primary', labelKey: 'primary' },
  { key: 'preparatory', labelKey: 'preparatory' },
  { key: 'secondary', labelKey: 'secondary' },
]

export default function MOELibraryBrowser({ isOpen, onClose, onImportSuccess }) {
  const { t } = useLanguage()
  const [books, setBooks] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedStage, setSelectedStage] = useState(null)
  const [importingIds, setImportingIds] = useState(new Set())
  const [importedIds, setImportedIds] = useState(new Set())
  const [error, setError] = useState(null)

  const fetchBooks = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { subject: 'math' }
      if (selectedStage) params.stage = selectedStage
      const res = await moeLibraryApi.getBooks('math', null, selectedStage)
      setBooks(res.data || [])
    } catch (err) {
      setError(t('moeLibrary.loadError'))
      setBooks([])
    } finally {
      setLoading(false)
    }
  }, [selectedStage, t])

  useEffect(() => {
    if (isOpen) {
      fetchBooks()
    }
  }, [isOpen, fetchBooks])

  const handleImport = async (book) => {
    if (importingIds.has(book.id) || importedIds.has(book.id)) return

    setImportingIds((prev) => new Set([...prev, book.id]))
    try {
      const res = await moeLibraryApi.importBook(book.id)
      setImportedIds((prev) => new Set([...prev, book.id]))
      toast.success(t('moeLibrary.importSuccess'))
      if (onImportSuccess) onImportSuccess(res.data)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (detail && detail.includes('already imported')) {
        setImportedIds((prev) => new Set([...prev, book.id]))
        toast.success(t('moeLibrary.imported'))
      } else {
        toast.error(t('moeLibrary.importError'))
      }
    } finally {
      setImportingIds((prev) => {
        const next = new Set(prev)
        next.delete(book.id)
        return next
      })
    }
  }

  // Group books by grade
  const groupedBooks = books.reduce((acc, book) => {
    const grade = book.grade || 'Unknown'
    if (!acc[grade]) acc[grade] = []
    acc[grade].push(book)
    return acc
  }, {})

  if (!isOpen) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 bg-gradient-to-r from-primary-50 to-white">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
                <Library size={20} className="text-primary-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">{t('moeLibrary.title')}</h2>
                <p className="text-sm text-gray-500">{t('moeLibrary.subtitle')}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-surface-100 transition-colors"
            >
              <X size={20} className="text-gray-500" />
            </button>
          </div>

          {/* Stage Filter Tabs */}
          <div className="px-6 py-3 border-b border-surface-100 flex gap-2 flex-wrap">
            {STAGES.map((stage) => (
              <button
                key={stage.key || 'all'}
                onClick={() => setSelectedStage(stage.key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  selectedStage === stage.key
                    ? 'bg-primary-500 text-white shadow-sm'
                    : 'bg-surface-100 text-gray-600 hover:bg-surface-200'
                }`}
              >
                {t(`moeLibrary.${stage.labelKey}`)}
              </button>
            ))}
            {!loading && books.length > 0 && (
              <span className="ms-auto self-center text-sm text-gray-400">
                {books.length} {t('moeLibrary.bookCount')}
              </span>
            )}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <Loader2 size={32} className="text-primary-500 animate-spin" />
                <p className="text-gray-500">{t('common.loading')}</p>
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <p className="text-red-500">{error}</p>
                <button
                  onClick={fetchBooks}
                  className="text-primary-500 hover:underline text-sm"
                >
                  {t('wizard.tryAgain')}
                </button>
              </div>
            ) : books.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <BookOpen size={40} className="text-gray-300" />
                <p className="text-gray-500">{t('moeLibrary.noBooks')}</p>
              </div>
            ) : (
              <div className="space-y-6">
                {Object.entries(groupedBooks).map(([grade, gradeBooks]) => (
                  <div key={grade}>
                    <div className="flex items-center gap-2 mb-3">
                      <GraduationCap size={16} className="text-primary-500" />
                      <h3 className="text-sm font-semibold text-gray-700">{grade}</h3>
                      <span className="text-xs text-gray-400">({gradeBooks.length})</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {gradeBooks.map((book) => (
                        <BookCard
                          key={book.id}
                          book={book}
                          isImporting={importingIds.has(book.id)}
                          isImported={importedIds.has(book.id)}
                          onImport={() => handleImport(book)}
                          t={t}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

function BookCard({ book, isImporting, isImported, onImport, t }) {
  const termLabel = book.term_number === '1' ? t('moeLibrary.term1') : t('moeLibrary.term2')

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-3 p-3 rounded-xl border border-surface-200 hover:border-primary-200 hover:bg-primary-50/30 transition-all group"
    >
      {/* Book Icon */}
      <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-100 to-primary-200 flex items-center justify-center flex-shrink-0">
        <BookOpen size={18} className="text-primary-600" />
      </div>

      {/* Book Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate" title={book.title}>
          {book.title}
        </p>
        <p className="text-xs text-gray-500 mt-0.5">
          {termLabel}
        </p>
      </div>

      {/* Import Button */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={onImport}
        disabled={isImporting || isImported}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex-shrink-0 ${
          isImported
            ? 'bg-green-100 text-green-700 cursor-default'
            : isImporting
            ? 'bg-surface-100 text-gray-400 cursor-wait'
            : 'bg-primary-500 text-white hover:bg-primary-600 shadow-sm'
        }`}
      >
        {isImported ? (
          <>
            <Check size={14} />
            {t('moeLibrary.imported')}
          </>
        ) : isImporting ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            {t('moeLibrary.importing')}
          </>
        ) : (
          <>
            <Download size={14} />
            {t('moeLibrary.importBtn')}
          </>
        )}
      </motion.button>
    </motion.div>
  )
}
