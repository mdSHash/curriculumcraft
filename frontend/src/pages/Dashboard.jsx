import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Upload, BookOpen, FileText, Download, Trash2, Clock, CheckCircle2 } from 'lucide-react'
import { booksApi, workbooksApi } from '../api/client'
import { useLanguage } from '../i18n/LanguageContext'
import toast from 'react-hot-toast'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
}

export default function Dashboard() {
  const { t } = useLanguage()
  const [books, setBooks] = useState([])
  const [workbooks, setWorkbooks] = useState([])
  const [loadingBooks, setLoadingBooks] = useState(true)
  const [loadingWorkbooks, setLoadingWorkbooks] = useState(true)

  useEffect(() => {
    fetchBooks()
    fetchWorkbooks()
  }, [])

  const fetchBooks = async () => {
    try {
      const res = await booksApi.list()
      setBooks(res.data)
    } catch (err) {
      console.error('Failed to fetch books:', err)
    } finally {
      setLoadingBooks(false)
    }
  }

  const fetchWorkbooks = async () => {
    try {
      const res = await workbooksApi.list()
      setWorkbooks(res.data)
    } catch (err) {
      console.error('Failed to fetch workbooks:', err)
    } finally {
      setLoadingWorkbooks(false)
    }
  }

  const handleDeleteBook = async (bookId) => {
    try {
      await booksApi.delete(bookId)
      setBooks((prev) => prev.filter((b) => b.id !== bookId))
      toast.success('Book deleted')
    } catch (err) {
      toast.error('Failed to delete book')
    }
  }

  const handleDownloadWorkbook = async (workbookId) => {
    try {
      const res = await workbooksApi.download(workbookId)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `workbook-${workbookId}.docx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      toast.error('Failed to download workbook')
    }
  }

  const getStatusLabel = (status) => {
    switch (status) {
      case 'ready': return t('dashboard.ready')
      case 'generating': return t('dashboard.processing')
      case 'processing': return t('dashboard.processing')
      case 'error': return t('dashboard.error')
      default: return status
    }
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Welcome Section */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <h1 className="text-3xl font-bold text-gray-900 mb-2">{t('dashboard.welcome')}</h1>
        <p className="text-gray-600 text-lg">{t('dashboard.description')}</p>
      </motion.div>

      {/* CTA */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, delay: 0.2 }}
        className="mb-10"
      >
        <Link
          to="/upload"
          className="inline-flex items-center gap-2 btn-primary text-base px-8 py-3"
        >
          <Upload size={20} />
          {t('dashboard.uploadBtn')}
        </Link>
      </motion.div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Ingested Books */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <BookOpen size={20} className="text-primary-600" />
            <h2 className="text-xl font-semibold text-gray-900">{t('dashboard.booksTitle')}</h2>
          </div>

          {loadingBooks ? (
            <div className="card p-8 flex items-center justify-center">
              <div className="animate-spin w-6 h-6 border-2 border-primary-600 border-t-transparent rounded-full" />
            </div>
          ) : books.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="card p-8 text-center"
            >
              <BookOpen size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500 font-medium">{t('dashboard.noBooks')}</p>
              <p className="text-gray-400 text-sm mt-1">{t('dashboard.uploadCtaDesc')}</p>
            </motion.div>
          ) : (
            <motion.div
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className="flex flex-col gap-3"
            >
              {books.map((book) => (
                <motion.div key={book.id} variants={itemVariants} className="card p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-gray-900 truncate">{book.title}</h3>
                      <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                        {book.grade && <span>{book.grade}</span>}
                        {book.term && <span>{book.term}</span>}
                        {book.chapters_count && (
                          <span>{book.chapters_count} {t('dashboard.chapters')}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ms-3">
                      <span
                        className={`text-xs font-medium px-2 py-1 rounded-full ${
                          book.status === 'ready'
                            ? 'bg-green-50 text-green-700'
                            : book.status === 'processing'
                            ? 'bg-amber-50 text-amber-700'
                            : 'bg-red-50 text-red-700'
                        }`}
                      >
                        {book.status === 'ready' && <CheckCircle2 size={12} className="inline me-1" />}
                        {book.status === 'processing' && <Clock size={12} className="inline me-1" />}
                        {getStatusLabel(book.status)}
                      </span>
                      <button
                        onClick={() => handleDeleteBook(book.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                        aria-label={t('common.delete')}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                  {book.status === 'ready' && (
                    <Link
                      to={`/builder/${book.id}`}
                      className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700"
                    >
                      {t('dashboard.createWorkbook')} →
                    </Link>
                  )}
                </motion.div>
              ))}
            </motion.div>
          )}
        </section>

        {/* Recent Workbooks */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <FileText size={20} className="text-primary-600" />
            <h2 className="text-xl font-semibold text-gray-900">{t('dashboard.workbooksTitle')}</h2>
          </div>

          {loadingWorkbooks ? (
            <div className="card p-8 flex items-center justify-center">
              <div className="animate-spin w-6 h-6 border-2 border-primary-600 border-t-transparent rounded-full" />
            </div>
          ) : workbooks.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="card p-8 text-center"
            >
              <FileText size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500 font-medium">{t('dashboard.noWorkbooks')}</p>
            </motion.div>
          ) : (
            <motion.div
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className="flex flex-col gap-3"
            >
              {workbooks.map((wb) => (
                <motion.div key={wb.id} variants={itemVariants} className="card p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-gray-900 truncate">{wb.title}</h3>
                      <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                        {wb.created_at && (
                          <span>{new Date(wb.created_at).toLocaleDateString()}</span>
                        )}
                        {wb.total_pages && <span>{wb.total_pages} {t('dashboard.pages')}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ms-3">
                      <span
                        className={`text-xs font-medium px-2 py-1 rounded-full ${
                          wb.status === 'ready'
                            ? 'bg-green-50 text-green-700'
                            : (wb.status === 'generating' || wb.status === 'processing')
                            ? 'bg-amber-50 text-amber-700'
                            : 'bg-red-50 text-red-700'
                        }`}
                      >
                        {getStatusLabel(wb.status)}
                      </span>
                      {wb.status === 'ready' && (
                        <button
                          onClick={() => handleDownloadWorkbook(wb.id)}
                          className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                          aria-label={t('common.download')}
                        >
                          <Download size={16} />
                        </button>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          )}
        </section>
      </div>
    </div>
  )
}
