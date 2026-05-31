import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  Loader2,
  ScrollText,
  Trash2,
  Upload,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { examsApi, workbooksApi } from '../api/client'
import { useLanguage } from '../i18n/LanguageContext'

const TABS = [
  { key: 'all',       labelKey: 'workbooksPage.tabAll' },
  { key: 'workbooks', labelKey: 'workbooksPage.tabWorkbooks' },
  { key: 'exams',     labelKey: 'workbooksPage.tabExams' },
]

function StatusBadge({ status, progress, t }) {
  if (status === 'ready') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full bg-green-50 text-green-700">
        <CheckCircle2 size={12} /> {t('workbooksPage.status.ready')}
      </span>
    )
  }
  if (status === 'error') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full bg-red-50 text-red-700">
        <AlertCircle size={12} /> {t('workbooksPage.status.error')}
      </span>
    )
  }
  // generating / processing
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full bg-amber-50 text-amber-700">
      <Clock size={12} />
      {typeof progress === 'number' && progress > 0
        ? `${Math.min(99, progress)}%`
        : t('workbooksPage.status.generating')}
    </span>
  )
}

function ItemRow({ item, kind, onDownload, onDownloadAnswerKey, onDelete, t }) {
  const isReady = item.status === 'ready'
  const isExam  = kind === 'exam'

  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white border border-gray-200 rounded-xl p-4 flex items-start gap-4"
    >
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
        isExam ? 'bg-emerald-50 text-emerald-600' : 'bg-blue-50 text-blue-600'
      }`}>
        {isExam ? <ScrollText size={18} /> : <FileText size={18} />}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-semibold text-gray-900 truncate">{item.title}</h3>
          <StatusBadge status={item.status} progress={item.progress} t={t} />
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-gray-500">
          <span>{new Date(item.created_at).toLocaleString()}</span>
          {isExam ? (
            <>
              <span>•</span>
              <span>
                {item.exam_type === 'quiz'
                  ? t('workbooksPage.examType.quiz')
                  : item.exam_type === 'weekly_assessment'
                  ? t('workbooksPage.examType.weekly')
                  : t('workbooksPage.examType.monthly')}
              </span>
              <span>•</span>
              <span>{item.total_marks} {t('workbooksPage.marks')}</span>
              {item.num_variants > 1 && (
                <>
                  <span>•</span>
                  <span>{item.num_variants} {t('workbooksPage.variants')}</span>
                </>
              )}
            </>
          ) : (
            <>
              <span>•</span>
              <span>{item.total_pages} {t('workbooksPage.pages')}</span>
            </>
          )}
        </div>
        {item.status !== 'ready' && item.progress_message && (
          <div className="mt-2 text-xs text-amber-700">{item.progress_message}</div>
        )}
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {isReady && (
          <button
            onClick={() => onDownload(item)}
            className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
            aria-label={t('common.download')}
            title={t('common.download')}
          >
            <Download size={16} />
          </button>
        )}
        {isExam && isReady && item.answer_key_filename && (
          <button
            onClick={() => onDownloadAnswerKey(item)}
            className="p-2 text-gray-500 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
            aria-label={t('workbooksPage.downloadAnswerKey')}
            title={t('workbooksPage.downloadAnswerKey')}
          >
            <ScrollText size={16} />
          </button>
        )}
        <button
          onClick={() => onDelete(item, kind)}
          className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          aria-label={t('common.delete')}
          title={t('common.delete')}
        >
          <Trash2 size={16} />
        </button>
      </div>
    </motion.li>
  )
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export default function WorkbooksPage() {
  const { t } = useLanguage()
  const [tab, setTab] = useState('all')
  const [workbooks, setWorkbooks] = useState([])
  const [exams, setExams] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = async () => {
    try {
      const [wRes, eRes] = await Promise.all([workbooksApi.list(), examsApi.list()])
      setWorkbooks(wRes.data || [])
      setExams(eRes.data || [])
      setError(null)
    } catch (err) {
      setError(t('workbooksPage.loadError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    // Poll while there are in-progress items so the percentage updates live.
    const t = setInterval(() => {
      const anyPending =
        workbooks.some((w) => w.status === 'generating' || w.status === 'processing') ||
        exams.some((e) => e.status === 'generating' || e.status === 'processing')
      if (anyPending) refresh()
    }, 3000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workbooks.length, exams.length])

  const items = useMemo(() => {
    const wb = workbooks.map((w) => ({ ...w, _kind: 'workbook' }))
    const ex = exams.map((e) => ({ ...e, _kind: 'exam' }))
    let combined
    if (tab === 'workbooks') combined = wb
    else if (tab === 'exams') combined = ex
    else combined = [...wb, ...ex]
    return combined.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
  }, [workbooks, exams, tab])

  const handleDownload = async (item) => {
    try {
      const isExam = item._kind === 'exam'
      const res = isExam
        ? await examsApi.download(item.id)
        : await workbooksApi.download(item.id)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      const fallback = isExam ? `exam-${item.id}.docx` : `workbook-${item.id}.docx`
      downloadBlob(blob, item.filename || fallback)
    } catch {
      toast.error(t('workbooksPage.downloadError'))
    }
  }

  const handleDownloadAnswerKey = async (item) => {
    try {
      const res = await examsApi.downloadAnswerKey(item.id)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      downloadBlob(blob, item.answer_key_filename || `answer-key-${item.id}.docx`)
    } catch {
      toast.error(t('workbooksPage.downloadError'))
    }
  }

  const handleDelete = async (item, kind) => {
    if (!window.confirm(t('workbooksPage.confirmDelete'))) return
    try {
      if (kind === 'exam') {
        await examsApi.delete(item.id)
        setExams((prev) => prev.filter((e) => e.id !== item.id))
      } else {
        await workbooksApi.delete(item.id)
        setWorkbooks((prev) => prev.filter((w) => w.id !== item.id))
      }
      toast.success(t('workbooksPage.deleted'))
    } catch {
      toast.error(t('workbooksPage.deleteError'))
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('workbooksPage.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('workbooksPage.subtitle')}</p>
      </div>

      <div className="border-b border-gray-200 mb-5 flex gap-1">
        {TABS.map((tabSpec) => (
          <button
            key={tabSpec.key}
            onClick={() => setTab(tabSpec.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === tabSpec.key
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            {t(tabSpec.labelKey)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="animate-spin" size={20} />
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center text-sm text-red-700">
          {error}
          <div className="mt-3">
            <button
              onClick={refresh}
              className="px-3 py-1.5 bg-red-600 text-white rounded-md text-xs font-medium hover:bg-red-700"
            >
              {t('common.retry')}
            </button>
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white border border-dashed border-gray-300 rounded-xl p-10 text-center">
          <FileText size={36} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-600 font-medium">{t('workbooksPage.empty')}</p>
          <p className="text-gray-400 text-sm mt-1">{t('workbooksPage.emptyHint')}</p>
          <Link
            to="/upload"
            className="mt-5 inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            <Upload size={16} /> {t('dashboard.uploadBtn')}
          </Link>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((item) => (
            <ItemRow
              key={`${item._kind}-${item.id}`}
              item={item}
              kind={item._kind}
              onDownload={handleDownload}
              onDownloadAnswerKey={handleDownloadAnswerKey}
              onDelete={handleDelete}
              t={t}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
