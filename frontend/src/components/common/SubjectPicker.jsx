import { useEffect, useState } from 'react'
import { subjectsApi } from '../../api/client'
import { useLanguage } from '../../i18n/LanguageContext'

/**
 * SubjectPicker — pill-row of canonical curriculum subjects.
 *
 * Drives multi-subject filtering in MOELibraryBrowser and the upload form.
 * Fetches /api/subjects on mount and renders a button per subject (plus
 * an "All" pill when allowAll is true). The selected key is reported via
 * onChange — null means "all subjects".
 *
 * Props:
 *   value: selected subject_key, or null
 *   onChange(nextKey: string|null)
 *   allowAll: render the "all subjects" pill (default true)
 *   compact: render in a denser horizontal-scroll layout
 *   includeBookCount: show book count next to each label
 */
export default function SubjectPicker({
  value = null,
  onChange,
  allowAll = true,
  compact = false,
  includeBookCount = false,
}) {
  const { t, isRTL } = useLanguage()
  const [subjects, setSubjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    subjectsApi
      .list()
      .then((res) => {
        if (!cancelled) {
          setSubjects(res.data || [])
          setError(null)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(true)
          setSubjects([])
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const labelFor = (s) => (isRTL ? s.label_ar : s.label_en)

  const Pill = ({ active, onClick, children, count }) => (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
        active
          ? 'bg-primary-500 text-white shadow-sm'
          : 'bg-surface-100 text-gray-600 hover:bg-surface-200'
      }`}
    >
      {children}
      {includeBookCount && count != null && (
        <span className="ms-1.5 text-xs opacity-70">({count})</span>
      )}
    </button>
  )

  if (loading) {
    return (
      <div className="text-xs text-gray-400">
        {t('common.loading')}
      </div>
    )
  }

  if (error || subjects.length === 0) {
    return null
  }

  return (
    <div
      className={
        compact
          ? 'flex gap-2 overflow-x-auto py-1'
          : 'flex flex-wrap gap-2'
      }
      role="group"
      aria-label={t('moeLibrary.subjectPickerLabel')}
    >
      {allowAll && (
        <Pill active={value == null} onClick={() => onChange?.(null)}>
          {t('moeLibrary.allSubjects')}
        </Pill>
      )}
      {subjects.map((s) => (
        <Pill
          key={s.key}
          active={value === s.key}
          onClick={() => onChange?.(s.key)}
          count={s.book_count}
        >
          {labelFor(s)}
        </Pill>
      ))}
    </div>
  )
}
