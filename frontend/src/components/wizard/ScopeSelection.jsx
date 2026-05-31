import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, CheckSquare, Square, MinusSquare, BookOpen } from 'lucide-react'
import { booksApi } from '../../api/client'
import { useLanguage } from '../../i18n/LanguageContext'

export default function ScopeSelection({ config, setConfig, bookId }) {
  const { t } = useLanguage()
  const [outline, setOutline] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedChapters, setExpandedChapters] = useState({})

  useEffect(() => {
    const fetchOutline = async () => {
      setLoading(true)
      try {
        const res = await booksApi.getOutline(bookId)
        setOutline(res.data)
        setError(null)
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load book outline')
      } finally {
        setLoading(false)
      }
    }
    fetchOutline()
  }, [bookId])

  const toggleChapterExpand = (chapterId) => {
    setExpandedChapters((prev) => ({ ...prev, [chapterId]: !prev[chapterId] }))
  }

  const isChapterSelected = (chapter) => {
    return config.scope.chapter_ids.includes(chapter.id)
  }

  const isTopicSelected = (topicId) => {
    return config.scope.topic_ids.includes(topicId)
  }

  const isChapterPartial = (chapter) => {
    const items = chapter.lessons?.length > 0 ? chapter.lessons : chapter.topics
    if (!items || items.length === 0) return false
    const selectedItems = items.filter((item) => config.scope.topic_ids.includes(item.id))
    return selectedItems.length > 0 && selectedItems.length < items.length
  }

  const toggleChapter = (chapter) => {
    const isSelected = isChapterSelected(chapter)
    // Use lessons if available, otherwise topics
    const items = chapter.lessons?.length > 0 ? chapter.lessons : chapter.topics
    const itemIds = items?.map((item) => item.id) || []

    if (isSelected) {
      setConfig((prev) => ({
        ...prev,
        scope: {
          ...prev.scope,
          chapter_ids: prev.scope.chapter_ids.filter((id) => id !== chapter.id),
          topic_ids: prev.scope.topic_ids.filter((id) => !itemIds.includes(id)),
        },
      }))
    } else {
      setConfig((prev) => ({
        ...prev,
        scope: {
          ...prev.scope,
          chapter_ids: [...prev.scope.chapter_ids, chapter.id],
          topic_ids: [...new Set([...prev.scope.topic_ids, ...itemIds])],
        },
      }))
    }
  }

  const toggleTopic = (chapter, topicId) => {
    const isSelected = isTopicSelected(topicId)
    let newTopicIds
    let newChapterIds = [...config.scope.chapter_ids]

    if (isSelected) {
      newTopicIds = config.scope.topic_ids.filter((id) => id !== topicId)
      const items = chapter.lessons?.length > 0 ? chapter.lessons : chapter.topics
      const remainingItems = items?.filter((item) => newTopicIds.includes(item.id)) || []
      if (remainingItems.length === 0) {
        newChapterIds = newChapterIds.filter((id) => id !== chapter.id)
      }
    } else {
      newTopicIds = [...config.scope.topic_ids, topicId]
      if (!newChapterIds.includes(chapter.id)) {
        newChapterIds = [...newChapterIds, chapter.id]
      }
    }

    setConfig((prev) => ({
      ...prev,
      scope: {
        ...prev.scope,
        chapter_ids: newChapterIds,
        topic_ids: newTopicIds,
      },
    }))
  }

  const selectAll = () => {
    if (!outline?.chapters) return
    const allChapterIds = outline.chapters.map((c) => c.id)
    const allItemIds = outline.chapters.flatMap((c) => {
      const items = c.lessons?.length > 0 ? c.lessons : c.topics
      return items?.map((item) => item.id) || []
    })
    setConfig((prev) => ({
      ...prev,
      scope: { ...prev.scope, chapter_ids: allChapterIds, topic_ids: allItemIds },
    }))
  }

  const deselectAll = () => {
    setConfig((prev) => ({
      ...prev,
      scope: { ...prev.scope, chapter_ids: [], topic_ids: [] },
    }))
  }

  const handlePageRange = (field, value) => {
    const numValue = value === '' ? null : parseInt(value, 10)
    setConfig((prev) => ({
      ...prev,
      scope: { ...prev.scope, [field]: numValue },
    }))
  }

  const selectedChapterCount = config.scope.chapter_ids.length
  const selectedTopicCount = config.scope.topic_ids.length

  // Determine if the book uses lessons (Egypt curriculum) or topics
  const hasLessons = outline?.chapters?.some((c) => c.lessons && c.lessons.length > 0)
  const itemLabel = hasLessons ? t('wizard.lessonsSelected') : t('wizard.topicsSelected')

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        <span className="ms-3 text-gray-600">{t('wizard.loadingOutline')}</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-16">
        <p className="text-red-600 mb-2">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="text-blue-600 hover:text-blue-700 text-sm font-medium"
        >
          {t('wizard.tryAgain')}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header actions */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-600">
          <span className="font-semibold text-gray-900">{selectedChapterCount}</span> {t('wizard.chaptersSelected')},{' '}
          <span className="font-semibold text-gray-900">{selectedTopicCount}</span> {itemLabel} {t('wizard.selected')}
        </p>
        <div className="flex gap-2">
          <button
            onClick={selectAll}
            className="px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
          >
            {t('wizard.selectAll')}
          </button>
          <button
            onClick={deselectAll}
            className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
          >
            {t('wizard.deselectAll')}
          </button>
        </div>
      </div>

      {/* Chapters accordion */}
      <div className="space-y-2">
        {outline?.chapters?.map((chapter, index) => {
          // Use lessons if available, otherwise topics
          const items = chapter.lessons?.length > 0 ? chapter.lessons : chapter.topics
          const isLessonBased = chapter.lessons?.length > 0

          return (
            <div
              key={chapter.id}
              className="border border-gray-200 rounded-lg overflow-hidden"
            >
              {/* Chapter header */}
              <div className="flex items-center gap-3 px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors">
                <button
                  onClick={() => toggleChapter(chapter)}
                  className="flex-shrink-0 text-gray-500 hover:text-blue-600 transition-colors"
                  aria-label={`Toggle chapter ${chapter.title}`}
                >
                  {isChapterSelected(chapter) ? (
                    <CheckSquare size={20} className="text-blue-600" />
                  ) : isChapterPartial(chapter) ? (
                    <MinusSquare size={20} className="text-blue-400" />
                  ) : (
                    <Square size={20} className="text-gray-400" />
                  )}
                </button>

                <button
                  onClick={() => toggleChapterExpand(chapter.id)}
                  className="flex-1 flex items-center justify-between text-left"
                >
                  <div>
                    <span className="text-sm font-medium text-gray-900">
                      {chapter.title || chapter.name || `Chapter ${index + 1}`}
                    </span>
                    {items && (
                      <span className="ms-2 text-xs text-gray-500">
                        ({items.length} {isLessonBased ? t('upload.lessons') : t('upload.topics')})
                      </span>
                    )}
                  </div>
                  <motion.div
                    animate={{ rotate: expandedChapters[chapter.id] ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <ChevronDown size={18} className="text-gray-400" />
                  </motion.div>
                </button>
              </div>

              {/* Items list (lessons or topics) */}
              <AnimatePresence>
                {expandedChapters[chapter.id] && items && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25, ease: 'easeInOut' }}
                    className="overflow-hidden"
                  >
                    <div className="px-4 py-2 space-y-1 border-t border-gray-100">
                      {items.map((item, itemIdx) => (
                        <button
                          key={item.id}
                          onClick={() => toggleTopic(chapter, item.id)}
                          className="flex items-center gap-3 w-full px-3 py-2 rounded-md hover:bg-gray-50 transition-colors text-left"
                        >
                          {isTopicSelected(item.id) ? (
                            <CheckSquare size={16} className="text-blue-600 flex-shrink-0" />
                          ) : (
                            <Square size={16} className="text-gray-400 flex-shrink-0" />
                          )}
                          {isLessonBased && (
                            <BookOpen size={14} className="text-primary-400 flex-shrink-0" />
                          )}
                          <span className="text-sm text-gray-700">
                            {item.title || item.name || `${isLessonBased ? 'Lesson' : 'Topic'} ${itemIdx + 1}`}
                          </span>
                          {item.content_type && item.content_type !== 'concept' && (
                            <span className="ms-auto text-xs text-gray-400 capitalize">
                              {item.content_type}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </div>

      {/* Page range filter */}
      <div className="border border-gray-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-900 mb-3">
          {t('wizard.pageRange')} <span className="text-gray-400 font-normal">{t('wizard.pageRangeOptional')}</span>
        </h4>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <label className="text-xs text-gray-500 mb-1 block">{t('wizard.startPage')}</label>
            <input
              type="number"
              min={1}
              placeholder="1"
              value={config.scope.page_range_start || ''}
              onChange={(e) => handlePageRange('page_range_start', e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <span className="text-gray-400 mt-5">—</span>
          <div className="flex-1">
            <label className="text-xs text-gray-500 mb-1 block">{t('wizard.endPage')}</label>
            <input
              type="number"
              min={1}
              placeholder="Last"
              value={config.scope.page_range_end || ''}
              onChange={(e) => handlePageRange('page_range_end', e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
