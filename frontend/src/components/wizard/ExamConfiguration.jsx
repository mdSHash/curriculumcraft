import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  FileText,
  ClipboardList,
  Clock,
  Hash,
  Award,
  Layers,
  BookOpen,
  Library,
  Plus,
  Trash2,
} from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'
import { moeLibraryApi } from '../../api/client'

const DEFAULT_TOPIC_SECTIONS = [
  { title_en: 'First: Algebra', title_ar: 'أولاً: الجبر', count: 4, marks_per_question: 2 },
  { title_en: 'Second: Trigonometry', title_ar: 'ثانيًا: حساب المثلثات', count: 4, marks_per_question: 2 },
  { title_en: 'Third: Geometry', title_ar: 'ثالثًا: الهندسة', count: 2, marks_per_question: 2 },
]

export default function ExamConfig({ config, setConfig, bookInfo }) {
  const { t } = useLanguage()

  const examConfigDefault = {
    structure: {
      exam_type: 'monthly_exam',
      total_marks: 40,
      duration_minutes: 60,
      num_variants: 1,
      groups_per_variant: 1,
      choose_correct: 8,
      complete_following: 5,
      answer_short: 4,
      solve_prove: 3,
      essay_extended: 0,
      topic_sections: [],
      bloom_remember_understand: 30,
      bloom_apply_analyze: 40,
      bloom_evaluate_create: 30,
    },
    formatting: {
      title: 'امتحان شهري',
      school_name: '..................',
      subject: 'الرياضيات',
      grade: bookInfo?.grade || '',
      term: '',
      academic_year: '2025-2026',
      exam_date: '    /    /      ',
      language: 'arabic',
      include_answer_key: true,
      include_marking_rubric: true,
      moe_reference_id: null,
    },
  }

  const updateExamConfig = (path, value) => {
    setConfig((prev) => {
      const newExam = { ...(prev.exam || examConfigDefault) }
      const parts = path.split('.')
      let current = newExam
      for (let i = 0; i < parts.length - 1; i++) {
        current[parts[i]] = { ...current[parts[i]] }
        current = current[parts[i]]
      }
      current[parts[parts.length - 1]] = value
      return { ...prev, exam: newExam }
    })
  }

  // Initialize exam config if not present
  useEffect(() => {
    if (!config.exam) {
      setConfig((prev) => ({ ...prev, exam: examConfigDefault }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const structure = config.exam?.structure || examConfigDefault.structure
  const formatting = config.exam?.formatting || examConfigDefault.formatting
  const examType = structure.exam_type || 'monthly_exam'
  const isWeekly = examType === 'weekly_assessment'

  // ─── MOE reference assessments (lazy-loaded when picker opens) ───────────
  const [moeAssessments, setMoeAssessments] = useState([])
  const [moeLoading, setMoeLoading] = useState(false)
  const [moeError, setMoeError] = useState(null)
  const [moeLoaded, setMoeLoaded] = useState(false)

  const loadMoeAssessments = async () => {
    if (moeLoading) return
    setMoeLoading(true)
    setMoeError(null)
    try {
      const res = await moeLibraryApi.getAssessments({ subject: 'math' })
      setMoeAssessments(res.data || [])
      setMoeLoaded(true)
    } catch (err) {
      setMoeError(t('exam.moeReferenceError'))
      setMoeLoaded(false)
    } finally {
      setMoeLoading(false)
    }
  }

  // Auto-load when user picks weekly_assessment
  useEffect(() => {
    if (isWeekly) loadMoeAssessments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isWeekly])

  // ─── Exam type selection sets type-appropriate defaults ──────────────────
  const handleExamTypeSelect = (type) => {
    updateExamConfig('structure.exam_type', type)
    if (type === 'quiz') {
      updateExamConfig('structure.total_marks', 20)
      updateExamConfig('structure.duration_minutes', 20)
      updateExamConfig('structure.choose_correct', 5)
      updateExamConfig('structure.complete_following', 3)
      updateExamConfig('structure.answer_short', 0)
      updateExamConfig('structure.solve_prove', 2)
      updateExamConfig('structure.essay_extended', 0)
      updateExamConfig('structure.groups_per_variant', 1)
      updateExamConfig('structure.topic_sections', [])
      updateExamConfig('formatting.title', 'اختبار قصير')
    } else if (type === 'weekly_assessment') {
      updateExamConfig('structure.total_marks', 20)
      updateExamConfig('structure.duration_minutes', 30)
      updateExamConfig('structure.choose_correct', 0)
      updateExamConfig('structure.complete_following', 0)
      updateExamConfig('structure.answer_short', 0)
      updateExamConfig('structure.solve_prove', 0)
      updateExamConfig('structure.essay_extended', 0)
      updateExamConfig('structure.groups_per_variant', 3)
      updateExamConfig(
        'structure.topic_sections',
        structure.topic_sections?.length ? structure.topic_sections : DEFAULT_TOPIC_SECTIONS,
      )
      updateExamConfig('formatting.title', 'تقييم أسبوعي')
    } else {
      // monthly_exam
      updateExamConfig('structure.total_marks', 40)
      updateExamConfig('structure.duration_minutes', 60)
      updateExamConfig('structure.choose_correct', 8)
      updateExamConfig('structure.complete_following', 5)
      updateExamConfig('structure.answer_short', 4)
      updateExamConfig('structure.solve_prove', 3)
      updateExamConfig('structure.essay_extended', 0)
      updateExamConfig('structure.groups_per_variant', 1)
      updateExamConfig('structure.topic_sections', [])
      updateExamConfig('formatting.title', 'امتحان شهري')
    }
  }

  // ─── Topic section editor helpers ────────────────────────────────────────
  const topicSections = structure.topic_sections || []
  const updateTopicSection = (idx, key, value) => {
    const next = topicSections.map((s, i) => (i === idx ? { ...s, [key]: value } : s))
    updateExamConfig('structure.topic_sections', next)
  }
  const addTopicSection = () => {
    const next = [...topicSections, { title_en: '', title_ar: '', count: 4, marks_per_question: 2 }]
    updateExamConfig('structure.topic_sections', next)
  }
  const removeTopicSection = (idx) => {
    updateExamConfig('structure.topic_sections', topicSections.filter((_, i) => i !== idx))
  }

  return (
    <div className="space-y-6">
      {/* Exam Type Selection */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-3">
          {t('exam.examType')}
        </label>
        <div className="grid grid-cols-3 gap-3">
          {[
            { key: 'quiz', icon: ClipboardList, label: t('exam.quiz'), desc: t('exam.quizDesc') },
            { key: 'monthly_exam', icon: FileText, label: t('exam.monthlyExam'), desc: t('exam.monthlyExamDesc') },
            { key: 'weekly_assessment', icon: Library, label: t('exam.weeklyAssessment'), desc: t('exam.weeklyAssessmentDesc') },
          ].map((type) => {
            const isSelected = examType === type.key
            const Icon = type.icon
            return (
              <motion.button
                key={type.key}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                onClick={() => handleExamTypeSelect(type.key)}
                className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50/50 shadow-sm'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <Icon size={24} className={isSelected ? 'text-blue-600' : 'text-gray-500'} />
                <span className={`text-sm font-semibold ${isSelected ? 'text-blue-900' : 'text-gray-700'}`}>
                  {type.label}
                </span>
                <span className="text-xs text-gray-500 text-center leading-tight">{type.desc}</span>
              </motion.button>
            )
          })}
        </div>
      </div>

      {/* Marks, Duration, Variants, Groups */}
      <div className={`grid ${isWeekly ? 'grid-cols-4' : 'grid-cols-3'} gap-4`}>
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">
            <Award size={14} className="inline mr-1" />
            {t('exam.totalMarks')}
          </label>
          <input
            type="number" min={5} max={100}
            value={structure.total_marks}
            onChange={(e) => updateExamConfig('structure.total_marks', parseInt(e.target.value) || 40)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">
            <Clock size={14} className="inline mr-1" />
            {t('exam.duration')}
          </label>
          <input
            type="number" min={10} max={180} step={5}
            value={structure.duration_minutes}
            onChange={(e) => updateExamConfig('structure.duration_minutes', parseInt(e.target.value) || 60)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">
            <Layers size={14} className="inline mr-1" />
            {t('exam.variants')}
          </label>
          <input
            type="number" min={1} max={5}
            value={structure.num_variants}
            onChange={(e) => updateExamConfig('structure.num_variants', parseInt(e.target.value) || 1)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        {isWeekly && (
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1" title={t('exam.groupsPerVariantHint')}>
              <Hash size={14} className="inline mr-1" />
              {t('exam.groupsPerVariant')}
            </label>
            <input
              type="number" min={1} max={5}
              value={structure.groups_per_variant || 3}
              onChange={(e) => updateExamConfig('structure.groups_per_variant', parseInt(e.target.value) || 3)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        )}
      </div>

      {/* Topic Sections (weekly_assessment) OR Question Distribution (others) */}
      {isWeekly ? (
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-semibold text-gray-700">
              <BookOpen size={14} className="inline mr-1" />
              {t('exam.topicSections')}
            </label>
            <button
              type="button"
              onClick={addTopicSection}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1"
            >
              <Plus size={14} /> {t('exam.addTopic')}
            </button>
          </div>
          <p className="text-xs text-gray-500 mb-3">{t('exam.topicSectionsHint')}</p>
          <div className="space-y-2 bg-gray-50 rounded-xl p-3">
            {topicSections.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-4">
                — {t('exam.addTopic')} —
              </p>
            )}
            {topicSections.map((section, idx) => (
              <div key={idx} className="grid grid-cols-12 gap-2 items-center bg-white rounded-lg p-2 border border-gray-200">
                <input
                  type="text"
                  value={section.title_en || ''}
                  onChange={(e) => updateTopicSection(idx, 'title_en', e.target.value)}
                  placeholder={t('exam.topicTitleEn')}
                  className="col-span-4 px-2 py-1 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-blue-500"
                />
                <input
                  type="text"
                  dir="rtl"
                  value={section.title_ar || ''}
                  onChange={(e) => updateTopicSection(idx, 'title_ar', e.target.value)}
                  placeholder={t('exam.topicTitleAr')}
                  className="col-span-4 px-2 py-1 border border-gray-200 rounded text-xs focus:ring-1 focus:ring-blue-500"
                />
                <input
                  type="number" min={1} max={20}
                  value={section.count || 0}
                  onChange={(e) => updateTopicSection(idx, 'count', parseInt(e.target.value) || 0)}
                  title={t('exam.topicCount')}
                  className="col-span-1 px-2 py-1 border border-gray-200 rounded text-xs text-center focus:ring-1 focus:ring-blue-500"
                />
                <input
                  type="number" min={1} max={10}
                  value={section.marks_per_question || 1}
                  onChange={(e) => updateTopicSection(idx, 'marks_per_question', parseInt(e.target.value) || 1)}
                  title={t('exam.topicMarks')}
                  className="col-span-2 px-2 py-1 border border-gray-200 rounded text-xs text-center focus:ring-1 focus:ring-blue-500"
                />
                <button
                  type="button"
                  onClick={() => removeTopicSection(idx)}
                  className="col-span-1 text-red-400 hover:text-red-600 flex justify-center"
                  aria-label={t('exam.removeTopic')}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            <div className="flex items-center justify-between pt-2 border-t border-gray-200 px-1">
              <span className="text-xs font-semibold text-gray-700">{t('exam.totalQuestions')}</span>
              <span className="text-xs font-bold text-blue-600">
                {topicSections.reduce((s, sec) => s + (sec.count || 0), 0)}
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-3">
            <Hash size={14} className="inline mr-1" />
            {t('exam.questionDistribution')}
          </label>
          <div className="space-y-3 bg-gray-50 rounded-xl p-4">
            {[
              { key: 'choose_correct', label: t('exam.chooseCorrect') },
              { key: 'complete_following', label: t('exam.completeFollowing') },
              { key: 'answer_short', label: t('exam.answerShort') },
              { key: 'solve_prove', label: t('exam.solveProve') },
              { key: 'essay_extended', label: t('exam.essayExtended') },
            ].map((section) => (
              <div key={section.key} className="flex items-center justify-between">
                <span className="text-sm text-gray-700">{section.label}</span>
                <input
                  type="number" min={0} max={20}
                  value={structure[section.key] || 0}
                  onChange={(e) => updateExamConfig(`structure.${section.key}`, parseInt(e.target.value) || 0)}
                  className="w-16 px-2 py-1 border border-gray-300 rounded-lg text-sm text-center focus:ring-2 focus:ring-blue-500"
                />
              </div>
            ))}
            <div className="flex items-center justify-between pt-2 border-t border-gray-200">
              <span className="text-sm font-semibold text-gray-800">{t('exam.totalQuestions')}</span>
              <span className="text-sm font-bold text-blue-600">
                {(structure.choose_correct || 0) +
                  (structure.complete_following || 0) +
                  (structure.answer_short || 0) +
                  (structure.solve_prove || 0) +
                  (structure.essay_extended || 0)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* MOE Reference Picker */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-1">
          <Library size={14} className="inline mr-1" />
          {t('exam.moeReference')}
        </label>
        <p className="text-xs text-gray-500 mb-2">{t('exam.moeReferenceHint')}</p>
        {moeLoading && (
          <p className="text-xs text-gray-400">{t('exam.moeReferenceLoading')}</p>
        )}
        {moeError && (
          <div className="flex items-center gap-2 mb-2">
            <p className="text-xs text-red-500 flex-1">{moeError}</p>
            <button
              type="button"
              onClick={loadMoeAssessments}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              {t('exam.moeReferenceRetry')}
            </button>
          </div>
        )}
        {!moeLoading && (
          <select
            value={formatting.moe_reference_id || ''}
            onChange={(e) =>
              updateExamConfig('formatting.moe_reference_id', e.target.value || null)
            }
            onFocus={loadMoeAssessments}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">{t('exam.moeReferenceNone')}</option>
            {moeAssessments.map((a) => (
              <option key={a.id} value={a.id}>
                {a.grade} — {a.title} — {t('exam.moeReferenceWeek')} {a.week_number ?? '?'}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Bloom's Taxonomy Distribution */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-3">
          <BookOpen size={14} className="inline mr-1" />
          {t('exam.bloomDistribution')}
        </label>
        <div className="space-y-2 bg-gray-50 rounded-xl p-4">
          {[
            { key: 'bloom_remember_understand', label: t('exam.bloomRemember'), color: 'bg-green-500' },
            { key: 'bloom_apply_analyze', label: t('exam.bloomApply'), color: 'bg-blue-500' },
            { key: 'bloom_evaluate_create', label: t('exam.bloomEvaluate'), color: 'bg-purple-500' },
          ].map((bloom) => (
            <div key={bloom.key} className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-600">{bloom.label}</span>
                <span className="text-xs font-medium text-gray-700">{structure[bloom.key] || 0}%</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${bloom.color} rounded-full transition-all`}
                    style={{ width: `${structure[bloom.key] || 0}%` }}
                  />
                </div>
                <input
                  type="range" min={0} max={100} step={5}
                  value={structure[bloom.key] || 0}
                  onChange={(e) => updateExamConfig(`structure.${bloom.key}`, parseInt(e.target.value))}
                  className="w-20 h-1 accent-blue-500"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Exam Metadata */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-3">
          {t('exam.examDetails')}
        </label>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('exam.schoolName')}</label>
            <input
              type="text"
              value={formatting.school_name}
              onChange={(e) => updateExamConfig('formatting.school_name', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
              placeholder=".................."
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('exam.subject')}</label>
            <input
              type="text"
              value={formatting.subject}
              onChange={(e) => updateExamConfig('formatting.subject', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
              placeholder="الرياضيات"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('exam.academicYear')}</label>
            <input
              type="text"
              value={formatting.academic_year}
              onChange={(e) => updateExamConfig('formatting.academic_year', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
              placeholder="2025-2026"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('exam.language')}</label>
            <select
              value={formatting.language}
              onChange={(e) => updateExamConfig('formatting.language', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="arabic">{t('wizard.langArabic')}</option>
              <option value="english">{t('wizard.langEnglish')}</option>
              <option value="bilingual">{t('wizard.langBilingual')}</option>
            </select>
          </div>
        </div>
      </div>

      {/* Options */}
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={formatting.include_answer_key}
            onChange={(e) => updateExamConfig('formatting.include_answer_key', e.target.checked)}
            className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
          />
          <span className="text-sm text-gray-700">{t('exam.includeAnswerKey')}</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={formatting.include_marking_rubric}
            onChange={(e) => updateExamConfig('formatting.include_marking_rubric', e.target.checked)}
            className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
          />
          <span className="text-sm text-gray-700">{t('exam.includeRubric')}</span>
        </label>
      </div>
    </div>
  )
}
