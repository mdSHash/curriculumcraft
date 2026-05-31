import { Minus, Plus } from 'lucide-react'
import { LAYOUT_STYLES } from '../../utils/constants'
import Toggle from '../common/Toggle'

export default function WorkbookStructure({ config, setConfig }) {
  const updateStructure = (field, value) => {
    setConfig((prev) => ({
      ...prev,
      structure: { ...prev.structure, [field]: value },
    }))
  }

  const incrementPages = () => {
    if (config.structure.total_pages < 100) {
      updateStructure('total_pages', config.structure.total_pages + 1)
    }
  }

  const decrementPages = () => {
    if (config.structure.total_pages > 5) {
      updateStructure('total_pages', config.structure.total_pages - 1)
    }
  }

  const handlePagesInput = (e) => {
    const val = parseInt(e.target.value, 10)
    if (!isNaN(val) && val >= 5 && val <= 100) {
      updateStructure('total_pages', val)
    }
  }

  const toggles = [
    { key: 'include_cover', label: 'Cover Page', description: 'Title page with student name, class, and date fields' },
    { key: 'include_objectives', label: 'Learning Objectives', description: 'List objectives at the start of each section' },
    { key: 'include_worked_examples', label: 'Worked Examples', description: 'Show a solved example before exercises' },
    { key: 'include_formula_box', label: 'Formula Reference Box', description: 'Key formulas and rules for each topic' },
    { key: 'include_answer_lines', label: 'Answer Lines', description: 'Ruled lines for student working' },
    { key: 'include_answer_box', label: 'Answer Box', description: 'Boxed area for final answers' },
    { key: 'include_difficulty_labels', label: 'Difficulty Labels', description: 'Star ratings (⭐/⭐⭐/⭐⭐⭐) on exercises' },
    { key: 'include_page_numbers', label: 'Page Numbers', description: 'Page numbers in footer' },
    { key: 'include_section_headers', label: 'Section Headers', description: 'Topic name headers between sections' },
    { key: 'include_teacher_notes', label: 'Teacher Notes Margin', description: 'Extra margin space for teacher annotations' },
  ]

  // Estimate exercises based on pages and layout (matches backend EXERCISES_PER_PAGE_BY_DENSITY)
  const densityMap = { spacious: 2, standard: 3, dense: 5 }
  const density = densityMap[config.structure.layout_style] || 3
  const estimatedExercises = Math.round(config.structure.total_pages * density)

  return (
    <div className="space-y-8">
      {/* Total Pages */}
      <div className="border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Total Pages</h3>
        <div className="flex items-center gap-4">
          <button
            onClick={decrementPages}
            disabled={config.structure.total_pages <= 5}
            className="w-10 h-10 rounded-lg border border-gray-200 flex items-center justify-center text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Minus size={16} />
          </button>
          <input
            type="number"
            min={5}
            max={100}
            value={config.structure.total_pages}
            onChange={handlePagesInput}
            className="w-20 text-center text-2xl font-bold text-gray-900 border-b-2 border-gray-200 focus:border-blue-500 focus:outline-none bg-transparent"
          />
          <button
            onClick={incrementPages}
            disabled={config.structure.total_pages >= 100}
            className="w-10 h-10 rounded-lg border border-gray-200 flex items-center justify-center text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Plus size={16} />
          </button>
          <span className="text-sm text-gray-500 ml-2">pages (5–100)</span>
        </div>
      </div>

      {/* Layout Style */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Layout Style</h3>
        <div className="grid grid-cols-3 gap-3">
          {Object.entries(LAYOUT_STYLES).map(([key, style]) => {
            const isSelected = config.structure.layout_style === key
            return (
              <button
                key={key}
                onClick={() => updateStructure('layout_style', key)}
                className={`
                  relative p-4 rounded-xl border-2 text-left transition-all duration-200
                  ${isSelected
                    ? 'border-blue-500 bg-blue-50/50 shadow-sm'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }
                `}
              >
                {isSelected && (
                  <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
                <span className="text-2xl mb-2 block">{style.icon}</span>
                <p className="text-sm font-semibold text-gray-900">{style.label}</p>
                <p className="text-xs text-gray-500 mt-1">{style.description}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* Feature Toggles */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Include / Exclude Features</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4 border border-gray-200 rounded-lg p-5">
          {toggles.map((toggle) => (
            <Toggle
              key={toggle.key}
              enabled={config.structure[toggle.key]}
              onChange={(val) => updateStructure(toggle.key, val)}
              label={toggle.label}
              description={toggle.description}
            />
          ))}
        </div>
      </div>

      {/* Estimate */}
      <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
          <span className="text-blue-600 font-bold text-sm">≈</span>
        </div>
        <div>
          <p className="text-sm font-medium text-blue-900">
            Estimated: ~{estimatedExercises} exercises total
          </p>
          <p className="text-xs text-blue-600">
            Based on {config.structure.total_pages} pages × {LAYOUT_STYLES[config.structure.layout_style]?.label} layout
          </p>
        </div>
      </div>
    </div>
  )
}
