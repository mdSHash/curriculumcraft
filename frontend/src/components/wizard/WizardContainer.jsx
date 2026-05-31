import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, ArrowRight, Sparkles } from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'
import StepIndicator from './StepIndicator'
import ScopeSelection from './ScopeSelection'
import OutputModeSelection from './OutputModeSelection'
import WorkbookStructure from './WorkbookStructure'
import ExerciseConfig from './ExerciseConfig'
import ExamConfiguration from './ExamConfiguration'
import FormattingStyle from './FormattingStyle'
import PreviewPanel from './PreviewPanel'

export default function WizardContainer({ bookId, bookInfo, onGenerate, generating }) {
  const { t } = useLanguage()
  const [currentStep, setCurrentStep] = useState(0)
  const [direction, setDirection] = useState(1)
  const [config, setConfig] = useState({
    scope: {
      book_id: bookId,
      chapter_ids: [],
      topic_ids: [],
      page_range_start: null,
      page_range_end: null,
    },
    structure: {
      total_pages: 20,
      layout_style: 'standard',
      output_mode: 'workbook_only',
      include_cover: true,
      include_objectives: true,
      include_worked_examples: true,
      include_formula_box: true,
      include_answer_lines: true,
      include_answer_box: true,
      include_difficulty_labels: true,
      include_page_numbers: true,
      include_section_headers: true,
      include_teacher_notes: false,
    },
    exercises: {
      difficulty_easy: 40,
      difficulty_medium: 40,
      difficulty_hard: 20,
      types: ['multiple_choice', 'fill_blank', 'show_work', 'word_problems'],
      exercises_per_type: null,
      source: 'both',
    },
    formatting: {
      title: bookInfo?.title ? `${bookInfo.title} Workbook` : 'Math Workbook',
      school_name: '',
      teacher_name: '',
      grade: bookInfo?.grade || '',
      term: '',
      academic_year: '',
      font_size: 'medium',
      answer_style: 'ruled_lines',
      margins: 'normal',
      language: 'arabic',
    },
    // Exam-specific config (used when output_mode === 'exam_quiz')
    exam: null,
  })

  const isExamMode = config.structure.output_mode === 'exam_quiz'

  // Dynamic steps based on output mode
  const getSteps = () => {
    if (isExamMode) {
      return [
        { title: t('wizard.scope'), subtitle: t('wizard.scopeSubtitle'), component: ScopeSelection },
        { title: t('wizard.outputMode'), subtitle: t('wizard.outputModeSubtitle'), component: OutputModeSelection },
        { title: t('exam.configuration'), subtitle: t('exam.configurationSubtitle'), component: ExamConfiguration },
      ]
    }
    return [
      { title: t('wizard.scope'), subtitle: t('wizard.scopeSubtitle'), component: ScopeSelection },
      { title: t('wizard.outputMode'), subtitle: t('wizard.outputModeSubtitle'), component: OutputModeSelection },
      { title: t('wizard.structure'), subtitle: t('wizard.structureSubtitle'), component: WorkbookStructure },
      { title: t('wizard.exercises'), subtitle: t('wizard.exercisesSubtitle'), component: ExerciseConfig },
      { title: t('wizard.formatting'), subtitle: t('wizard.formattingSubtitle'), component: FormattingStyle },
    ]
  }

  const steps = getSteps()
  const CurrentStepComponent = steps[currentStep]?.component || ScopeSelection

  const canProceed = () => {
    switch (currentStep) {
      case 0:
        return config.scope.chapter_ids.length > 0
      case 1:
        return true // Output mode always has a valid selection
      case 2:
        if (isExamMode) {
          const exam = config.exam
          if (!exam) return true // Will be initialized
          const structure = exam.structure || {}
          if (structure.exam_type === 'weekly_assessment') {
            // Topic-organized — at least one topic with count > 0
            const sections = structure.topic_sections || []
            return sections.some((s) => (s.count || 0) > 0)
          }
          const totalQuestions = (structure.choose_correct || 0) +
            (structure.complete_following || 0) +
            (structure.answer_short || 0) +
            (structure.solve_prove || 0) +
            (structure.essay_extended || 0)
          return totalQuestions > 0
        }
        return config.structure.total_pages >= 5
      case 3:
        return config.exercises.types.length > 0
      case 4:
        return config.formatting.title.trim().length > 0
      default:
        return true
    }
  }

  const goNext = () => {
    if (currentStep < steps.length - 1) {
      setDirection(1)
      setCurrentStep((prev) => prev + 1)
    }
  }

  const goBack = () => {
    if (currentStep > 0) {
      setDirection(-1)
      setCurrentStep((prev) => prev - 1)
    }
  }

  const handleGenerate = () => {
    onGenerate(config)
  }

  const isLastStep = currentStep === steps.length - 1

  const slideVariants = {
    enter: (dir) => ({ x: dir > 0 ? 80 : -80, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (dir) => ({ x: dir > 0 ? -80 : 80, opacity: 0 }),
  }

  return (
    <div className="flex gap-6">
      {/* Main wizard area */}
      <div className="flex-1 min-w-0">
        {/* Step indicator */}
        <div className="bg-white border border-gray-200 rounded-xl mb-6">
          <StepIndicator steps={steps} currentStep={currentStep} />
        </div>

        {/* Step content */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 min-h-[500px]">
          <div className="mb-6">
            <h2 className="text-lg font-bold text-gray-900">
              {steps[currentStep].title}
            </h2>
            <p className="text-sm text-gray-500">{steps[currentStep].subtitle}</p>
          </div>

          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={`${currentStep}-${isExamMode}`}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.25, ease: 'easeInOut' }}
            >
              <CurrentStepComponent
                config={config}
                setConfig={setConfig}
                bookId={bookId}
                bookInfo={bookInfo}
              />
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Navigation buttons */}
        <div className="flex items-center justify-between mt-6">
          <button
            onClick={goBack}
            disabled={currentStep === 0}
            className={`
              flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all
              ${currentStep === 0
                ? 'text-gray-300 cursor-not-allowed'
                : 'text-gray-700 hover:bg-gray-100'
              }
            `}
          >
            <ArrowLeft size={16} />
            {t('common.back')}
          </button>

          {isLastStep ? (
            <button
              onClick={handleGenerate}
              disabled={!canProceed() || generating}
              className={`
                flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-semibold transition-all
                ${canProceed() && !generating
                  ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-md shadow-blue-200'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                }
              `}
            >
              {generating ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  {t('common.generating')}
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  {isExamMode ? t('exam.generateExam') : t('common.generate')}
                </>
              )}
            </button>
          ) : (
            <button
              onClick={goNext}
              disabled={!canProceed()}
              className={`
                flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all
                ${canProceed()
                  ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-md shadow-blue-200'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                }
              `}
            >
              {t('common.next')}
              <ArrowRight size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Preview sidebar */}
      <div className="hidden lg:block w-72 flex-shrink-0">
        <PreviewPanel config={config} bookInfo={bookInfo} />
      </div>
    </div>
  )
}
