import { BookOpen, Layers, BarChart3, CheckCircle2 } from 'lucide-react'
import { LAYOUT_STYLES, EXERCISE_TYPES } from '../../utils/constants'

export default function PreviewPanel({ config, bookInfo }) {
  const densityMap = { spacious: 2, standard: 3, dense: 5 }
  const density = densityMap[config.structure.layout_style] || 3
  const estimatedExercises = Math.round(config.structure.total_pages * density)

  const selectedChapterCount = config.scope.chapter_ids.length
  const selectedTopicCount = config.scope.topic_ids.length
  const hasScope = selectedChapterCount > 0
  const hasTypes = config.exercises.types.length > 0
  const isReady = hasScope && hasTypes

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-5 sticky top-6">
      {/* Book info */}
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0">
          <BookOpen size={18} className="text-blue-600" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900 truncate">
            {bookInfo?.title || 'Loading...'}
          </p>
          {bookInfo?.grade && (
            <p className="text-xs text-gray-500">{bookInfo.grade}</p>
          )}
        </div>
      </div>

      <hr className="border-gray-100" />

      {/* Scope summary */}
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-purple-100 flex items-center justify-center flex-shrink-0">
          <Layers size={18} className="text-purple-600" />
        </div>
        <div>
          <p className="text-xs font-medium text-gray-600">Selected Scope</p>
          <p className="text-sm font-semibold text-gray-900">
            {selectedChapterCount} chapters, {selectedTopicCount} topics
          </p>
        </div>
      </div>

      {/* Estimates */}
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
          <BarChart3 size={18} className="text-amber-600" />
        </div>
        <div>
          <p className="text-xs font-medium text-gray-600">Estimated Exercises</p>
          <p className="text-sm font-semibold text-gray-900">~{estimatedExercises} exercises</p>
          <p className="text-[10px] text-gray-400">
            {config.structure.total_pages} pages × {LAYOUT_STYLES[config.structure.layout_style]?.label}
          </p>
        </div>
      </div>

      <hr className="border-gray-100" />

      {/* Difficulty distribution bar */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-2">Difficulty Mix</p>
        <div className="h-2.5 rounded-full overflow-hidden flex bg-gray-100">
          <div
            className="bg-green-500 transition-all duration-300"
            style={{ width: `${config.exercises.difficulty_easy}%` }}
          />
          <div
            className="bg-amber-500 transition-all duration-300"
            style={{ width: `${config.exercises.difficulty_medium}%` }}
          />
          <div
            className="bg-red-500 transition-all duration-300"
            style={{ width: `${config.exercises.difficulty_hard}%` }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-[10px] text-green-600">{config.exercises.difficulty_easy}%</span>
          <span className="text-[10px] text-amber-600">{config.exercises.difficulty_medium}%</span>
          <span className="text-[10px] text-red-600">{config.exercises.difficulty_hard}%</span>
        </div>
      </div>

      {/* Exercise types */}
      <div>
        <p className="text-xs font-medium text-gray-600 mb-2">Exercise Types</p>
        <div className="flex flex-wrap gap-1.5">
          {config.exercises.types.map((type) => (
            <span
              key={type}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-gray-100 text-[10px] font-medium text-gray-700"
            >
              <span>{EXERCISE_TYPES[type]?.icon}</span>
              {EXERCISE_TYPES[type]?.label}
            </span>
          ))}
          {config.exercises.types.length === 0 && (
            <span className="text-[10px] text-gray-400 italic">None selected</span>
          )}
        </div>
      </div>

      <hr className="border-gray-100" />

      {/* Ready indicator */}
      <div className={`flex items-center gap-2 p-3 rounded-lg ${isReady ? 'bg-green-50' : 'bg-gray-50'}`}>
        <CheckCircle2
          size={18}
          className={isReady ? 'text-green-600' : 'text-gray-300'}
        />
        <span className={`text-xs font-medium ${isReady ? 'text-green-700' : 'text-gray-500'}`}>
          {isReady ? 'Ready to generate' : 'Complete all required fields'}
        </span>
      </div>
    </div>
  )
}
