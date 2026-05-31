import { FONT_SIZES, ANSWER_STYLES, LANGUAGES } from '../../utils/constants'

export default function FormattingStyle({ config, setConfig, bookInfo }) {
  const updateFormatting = (field, value) => {
    setConfig((prev) => ({
      ...prev,
      formatting: { ...prev.formatting, [field]: value },
    }))
  }

  const answerStyleIcons = {
    ruled_lines: (
      <svg className="w-10 h-10" viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.5">
        <line x1="4" y1="12" x2="36" y2="12" />
        <line x1="4" y1="20" x2="36" y2="20" />
        <line x1="4" y1="28" x2="36" y2="28" />
      </svg>
    ),
    dotted_lines: (
      <svg className="w-10 h-10" viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2 3">
        <line x1="4" y1="12" x2="36" y2="12" />
        <line x1="4" y1="20" x2="36" y2="20" />
        <line x1="4" y1="28" x2="36" y2="28" />
      </svg>
    ),
    grid: (
      <svg className="w-10 h-10" viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="0.75" opacity="0.6">
        {[8, 16, 24, 32].map((y) => <line key={`h${y}`} x1="4" y1={y} x2="36" y2={y} />)}
        {[8, 16, 24, 32].map((x) => <line key={`v${x}`} x1={x} y1="4" x2={x} y2="36" />)}
      </svg>
    ),
    plain_box: (
      <svg className="w-10 h-10" viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="6" y="8" width="28" height="24" rx="2" />
      </svg>
    ),
  }

  return (
    <div className="space-y-8">
      {/* Workbook Info */}
      <div className="border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Workbook Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2">
            <label className="text-xs font-medium text-gray-600 mb-1 block">Workbook Title</label>
            <input
              type="text"
              value={config.formatting.title}
              onChange={(e) => updateFormatting('title', e.target.value)}
              placeholder="Math Workbook"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">School Name</label>
            <input
              type="text"
              value={config.formatting.school_name}
              onChange={(e) => updateFormatting('school_name', e.target.value)}
              placeholder="Optional"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Teacher Name</label>
            <input
              type="text"
              value={config.formatting.teacher_name}
              onChange={(e) => updateFormatting('teacher_name', e.target.value)}
              placeholder="Optional"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Grade</label>
            <input
              type="text"
              value={config.formatting.grade}
              onChange={(e) => updateFormatting('grade', e.target.value)}
              placeholder={bookInfo?.grade || 'e.g. Grade 5'}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Term</label>
            <input
              type="text"
              value={config.formatting.term}
              onChange={(e) => updateFormatting('term', e.target.value)}
              placeholder="e.g. Term 1"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Academic Year</label>
            <input
              type="text"
              value={config.formatting.academic_year}
              onChange={(e) => updateFormatting('academic_year', e.target.value)}
              placeholder="e.g. 2024-2025"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>
      </div>

      {/* Font Size */}
      <div className="border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Font Size</h3>
        <div className="flex gap-3">
          {Object.entries(FONT_SIZES).map(([key, size]) => (
            <label
              key={key}
              className={`
                flex-1 flex items-center justify-center gap-2 p-3 rounded-lg border-2 cursor-pointer transition-all
                ${config.formatting.font_size === key
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
                }
              `}
            >
              <input
                type="radio"
                name="font_size"
                value={key}
                checked={config.formatting.font_size === key}
                onChange={(e) => updateFormatting('font_size', e.target.value)}
                className="sr-only"
              />
              <span className={`text-sm font-medium ${config.formatting.font_size === key ? 'text-blue-700' : 'text-gray-700'}`}>
                {size.label}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Answer Space Style */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Answer Space Style</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(ANSWER_STYLES).map(([key, style]) => {
            const isSelected = config.formatting.answer_style === key
            return (
              <button
                key={key}
                onClick={() => updateFormatting('answer_style', key)}
                className={`
                  relative p-4 rounded-xl border-2 text-center transition-all duration-200
                  ${isSelected
                    ? 'border-blue-500 bg-blue-50/50 shadow-sm'
                    : 'border-gray-200 hover:border-gray-300'
                  }
                `}
              >
                {isSelected && (
                  <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 flex items-center justify-center">
                    <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
                <div className={`flex justify-center mb-2 ${isSelected ? 'text-blue-600' : 'text-gray-400'}`}>
                  {answerStyleIcons[key]}
                </div>
                <p className="text-xs font-medium text-gray-900">{style.label}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">{style.description}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* Page Margins */}
      <div className="border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Page Margins</h3>
        <div className="flex gap-3">
          {[
            { value: 'normal', label: 'Normal', desc: 'Standard 1" margins' },
            { value: 'wide', label: 'Wide', desc: 'Extra space for ring-binding' },
          ].map((option) => (
            <label
              key={option.value}
              className={`
                flex-1 p-3 rounded-lg border-2 cursor-pointer transition-all
                ${config.formatting.margins === option.value
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
                }
              `}
            >
              <input
                type="radio"
                name="margins"
                value={option.value}
                checked={config.formatting.margins === option.value}
                onChange={(e) => updateFormatting('margins', e.target.value)}
                className="sr-only"
              />
              <p className={`text-sm font-medium ${config.formatting.margins === option.value ? 'text-blue-700' : 'text-gray-700'}`}>
                {option.label}
              </p>
              <p className="text-xs text-gray-500">{option.desc}</p>
            </label>
          ))}
        </div>
      </div>

      {/* Language */}
      <div className="border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Language</h3>
        <div className="flex gap-3">
          {Object.entries(LANGUAGES).map(([key, lang]) => (
            <label
              key={key}
              className={`
                flex-1 flex items-center justify-center p-3 rounded-lg border-2 cursor-pointer transition-all
                ${config.formatting.language === key
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
                }
              `}
            >
              <input
                type="radio"
                name="language"
                value={key}
                checked={config.formatting.language === key}
                onChange={(e) => updateFormatting('language', e.target.value)}
                className="sr-only"
              />
              <span className={`text-sm font-medium ${config.formatting.language === key ? 'text-blue-700' : 'text-gray-700'}`}>
                {lang.label}
              </span>
            </label>
          ))}
        </div>
      </div>
    </div>
  )
}
