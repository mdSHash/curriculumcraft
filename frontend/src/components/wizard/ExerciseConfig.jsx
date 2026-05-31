import { useState } from 'react'
import { EXERCISE_TYPES } from '../../utils/constants'
import Slider from '../common/Slider'
import Toggle from '../common/Toggle'

export default function ExerciseConfig({ config, setConfig }) {
  const [autoDistribute, setAutoDistribute] = useState(true)

  const updateExercises = (field, value) => {
    setConfig((prev) => ({
      ...prev,
      exercises: { ...prev.exercises, [field]: value },
    }))
  }

  // Difficulty sliders — must sum to 100
  const handleDifficultyChange = (level, newValue) => {
    const levels = ['difficulty_easy', 'difficulty_medium', 'difficulty_hard']
    const otherLevels = levels.filter((l) => l !== level)
    const currentOthersSum = otherLevels.reduce((sum, l) => sum + config.exercises[l], 0)

    // Clamp new value
    newValue = Math.max(0, Math.min(100, newValue))
    const remaining = 100 - newValue

    let newValues = { [level]: newValue }

    if (currentOthersSum === 0) {
      // Distribute remaining equally
      newValues[otherLevels[0]] = Math.round(remaining / 2)
      newValues[otherLevels[1]] = remaining - Math.round(remaining / 2)
    } else {
      // Proportional adjustment
      otherLevels.forEach((l) => {
        const proportion = config.exercises[l] / currentOthersSum
        newValues[l] = Math.round(remaining * proportion)
      })
      // Fix rounding
      const total = Object.values(newValues).reduce((s, v) => s + v, 0)
      if (total !== 100) {
        newValues[otherLevels[0]] += 100 - total
      }
    }

    setConfig((prev) => ({
      ...prev,
      exercises: { ...prev.exercises, ...newValues },
    }))
  }

  const toggleExerciseType = (type) => {
    const current = config.exercises.types
    const updated = current.includes(type)
      ? current.filter((t) => t !== type)
      : [...current, type]
    updateExercises('types', updated)
  }

  const handlePerTypeCount = (type, value) => {
    const numValue = value === '' ? null : parseInt(value, 10)
    const current = config.exercises.exercises_per_type || {}
    setConfig((prev) => ({
      ...prev,
      exercises: {
        ...prev.exercises,
        exercises_per_type: { ...current, [type]: numValue },
      },
    }))
  }

  return (
    <div className="space-y-8">
      {/* Difficulty Distribution */}
      <div className="border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Difficulty Distribution</h3>
        <p className="text-xs text-gray-500 mb-5">Adjust the balance — sliders must sum to 100%</p>

        <div className="space-y-5">
          <Slider
            label="Easy"
            value={config.exercises.difficulty_easy}
            onChange={(val) => handleDifficultyChange('difficulty_easy', val)}
            min={0}
            max={100}
            step={5}
            color="green"
          />
          <Slider
            label="Medium"
            value={config.exercises.difficulty_medium}
            onChange={(val) => handleDifficultyChange('difficulty_medium', val)}
            min={0}
            max={100}
            step={5}
            color="amber"
          />
          <Slider
            label="Hard"
            value={config.exercises.difficulty_hard}
            onChange={(val) => handleDifficultyChange('difficulty_hard', val)}
            min={0}
            max={100}
            step={5}
            color="red"
          />
        </div>

        {/* Distribution bar */}
        <div className="mt-4 h-3 rounded-full overflow-hidden flex">
          <div
            className="bg-green-500 transition-all duration-200"
            style={{ width: `${config.exercises.difficulty_easy}%` }}
          />
          <div
            className="bg-amber-500 transition-all duration-200"
            style={{ width: `${config.exercises.difficulty_medium}%` }}
          />
          <div
            className="bg-red-500 transition-all duration-200"
            style={{ width: `${config.exercises.difficulty_hard}%` }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-[10px] text-green-600">Easy {config.exercises.difficulty_easy}%</span>
          <span className="text-[10px] text-amber-600">Medium {config.exercises.difficulty_medium}%</span>
          <span className="text-[10px] text-red-600">Hard {config.exercises.difficulty_hard}%</span>
        </div>
      </div>

      {/* Exercise Types */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Exercise Types</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {Object.entries(EXERCISE_TYPES).map(([key, type]) => {
            const isSelected = config.exercises.types.includes(key)
            return (
              <button
                key={key}
                onClick={() => toggleExerciseType(key)}
                className={`
                  relative p-3 rounded-xl border-2 text-left transition-all duration-200
                  ${isSelected
                    ? 'border-blue-500 bg-blue-50/50'
                    : 'border-gray-200 hover:border-gray-300'
                  }
                `}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{type.icon}</span>
                  <span className={`text-sm font-medium ${isSelected ? 'text-blue-700' : 'text-gray-700'}`}>
                    {type.label}
                  </span>
                </div>
                {isSelected && (
                  <div className="absolute top-1 right-1 w-4 h-4 rounded-full bg-blue-500 flex items-center justify-center">
                    <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
              </button>
            )
          })}
        </div>
        {config.exercises.types.length === 0 && (
          <p className="text-xs text-red-500 mt-2">Please select at least one exercise type</p>
        )}
      </div>

      {/* Source */}
      <div className="border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Exercise Source</h3>
        <div className="space-y-2">
          {[
            { value: 'textbook', label: 'Original textbook problems only', desc: 'Use only exercises found in the uploaded book' },
            { value: 'ai', label: 'AI-generated variations only', desc: 'Create new exercises based on the curriculum' },
            { value: 'both', label: 'Both (recommended)', desc: 'Mix of original and AI-generated exercises' },
          ].map((option) => (
            <label
              key={option.value}
              className={`
                flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors
                ${config.exercises.source === option.value ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-50 border border-transparent'}
              `}
            >
              <input
                type="radio"
                name="source"
                value={option.value}
                checked={config.exercises.source === option.value}
                onChange={(e) => updateExercises('source', e.target.value)}
                className="mt-0.5 w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <div>
                <p className="text-sm font-medium text-gray-900">{option.label}</p>
                <p className="text-xs text-gray-500">{option.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Per-type count */}
      <div className="border border-gray-200 rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Per-Type Count</h3>
            <p className="text-xs text-gray-500">Set specific counts per exercise type, or auto-distribute</p>
          </div>
          <Toggle
            enabled={autoDistribute}
            onChange={(val) => {
              setAutoDistribute(val)
              if (val) {
                updateExercises('exercises_per_type', null)
              }
            }}
            label="Auto"
          />
        </div>

        {!autoDistribute && (
          <div className="grid grid-cols-2 gap-3">
            {config.exercises.types.map((type) => (
              <div key={type} className="flex items-center gap-2">
                <span className="text-xs text-gray-600 flex-1">{EXERCISE_TYPES[type]?.label}</span>
                <input
                  type="number"
                  min={1}
                  max={50}
                  placeholder="Auto"
                  value={config.exercises.exercises_per_type?.[type] || ''}
                  onChange={(e) => handlePerTypeCount(type, e.target.value)}
                  className="w-16 px-2 py-1 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
