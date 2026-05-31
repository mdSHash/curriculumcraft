import { useRef, useCallback } from 'react'

export default function Slider({ value, onChange, min = 0, max = 100, step = 1, label, color = 'blue', showValue = true }) {
  const inputRef = useRef(null)

  const percentage = ((value - min) / (max - min)) * 100

  const colorMap = {
    blue: { track: 'bg-blue-500', thumb: 'accent-blue-600' },
    green: { track: 'bg-green-500', thumb: 'accent-green-600' },
    amber: { track: 'bg-amber-500', thumb: 'accent-amber-600' },
    red: { track: 'bg-red-500', thumb: 'accent-red-600' },
  }

  const colors = colorMap[color] || colorMap.blue

  const handleChange = useCallback((e) => {
    onChange(Number(e.target.value))
  }, [onChange])

  return (
    <div className="w-full">
      {(label || showValue) && (
        <div className="flex items-center justify-between mb-2">
          {label && (
            <label className="text-sm font-medium text-gray-700">{label}</label>
          )}
          {showValue && (
            <span className="text-sm font-semibold text-gray-900">{value}%</span>
          )}
        </div>
      )}
      <div className="relative w-full h-2 rounded-full bg-gray-200">
        <div
          className={`absolute left-0 top-0 h-full rounded-full ${colors.track} transition-all duration-150`}
          style={{ width: `${percentage}%` }}
        />
        <input
          ref={inputRef}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={handleChange}
          aria-label={label}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value}
          className={`absolute inset-0 w-full h-full opacity-0 cursor-pointer`}
        />
        <div
          className={`absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-white border-2 shadow-md pointer-events-none transition-all duration-150`}
          style={{
            left: `calc(${percentage}% - 8px)`,
            borderColor: color === 'green' ? '#16a34a' : color === 'amber' ? '#d97706' : color === 'red' ? '#dc2626' : '#2563eb',
          }}
        />
      </div>
    </div>
  )
}
