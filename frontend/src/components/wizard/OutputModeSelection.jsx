import { motion } from 'framer-motion'
import { FileText, BookOpen, ClipboardList } from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'

export default function OutputModeSelection({ config, setConfig }) {
  const { t } = useLanguage()

  const modes = [
    {
      key: 'workbook_only',
      icon: FileText,
      title: t('wizard.workbookOnly'),
      description: t('wizard.workbookOnlyDesc'),
    },
    {
      key: 'illustration_and_workbook',
      icon: BookOpen,
      title: t('wizard.illustrationAndWorkbook'),
      description: t('wizard.illustrationAndWorkbookDesc'),
    },
    {
      key: 'exam_quiz',
      icon: ClipboardList,
      title: t('wizard.examQuiz'),
      description: t('wizard.examQuizDesc'),
    },
  ]

  const currentMode = config.structure.output_mode || 'workbook_only'

  const handleSelect = (mode) => {
    setConfig((prev) => ({
      ...prev,
      structure: {
        ...prev.structure,
        output_mode: mode,
      },
    }))
  }

  return (
    <div className="space-y-4">
      {modes.map((mode) => {
        const isSelected = currentMode === mode.key
        const Icon = mode.icon

        return (
          <motion.button
            key={mode.key}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            onClick={() => handleSelect(mode.key)}
            className={`w-full flex items-start gap-4 p-5 rounded-xl border-2 text-start transition-all ${
              isSelected
                ? 'border-blue-500 bg-blue-50/50 shadow-sm'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            <div
              className={`w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 ${
                isSelected ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500'
              }`}
            >
              <Icon size={24} />
            </div>
            <div className="flex-1 min-w-0">
              <h3
                className={`text-base font-semibold mb-1 ${
                  isSelected ? 'text-blue-900' : 'text-gray-900'
                }`}
              >
                {mode.title}
              </h3>
              <p className="text-sm text-gray-600 leading-relaxed">{mode.description}</p>
            </div>
            <div className="flex-shrink-0 mt-1">
              <div
                className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                  isSelected ? 'border-blue-500' : 'border-gray-300'
                }`}
              >
                {isSelected && (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="w-3 h-3 rounded-full bg-blue-500"
                  />
                )}
              </div>
            </div>
          </motion.button>
        )
      })}
    </div>
  )
}
