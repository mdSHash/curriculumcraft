import { motion } from 'framer-motion'

export default function Toggle({ enabled, onChange, label, description, id }) {
  const toggleId = id || `toggle-${label?.replace(/\s+/g, '-').toLowerCase()}`

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <label
          htmlFor={toggleId}
          className="text-sm font-medium text-gray-900 cursor-pointer"
        >
          {label}
        </label>
        {description && (
          <p className="text-xs text-gray-500 mt-0.5">{description}</p>
        )}
      </div>
      <button
        id={toggleId}
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-label={label}
        onClick={() => onChange(!enabled)}
        className={`
          relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full
          border-2 border-transparent transition-colors duration-200 ease-in-out
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
          ${enabled ? 'bg-blue-600' : 'bg-gray-200'}
        `}
      >
        <motion.span
          layout
          transition={{ type: 'spring', stiffness: 700, damping: 30 }}
          className={`
            pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg
            ring-0 ${enabled ? 'translate-x-5' : 'translate-x-0'}
          `}
          animate={{ x: enabled ? 20 : 0 }}
        />
      </button>
    </div>
  )
}
