import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle2, Loader2 } from 'lucide-react'
import { displayProgress, formatElapsed } from '../../utils/progress'

/**
 * Reusable progress card for long-running generations.
 *
 * Shows:
 *   - Spinning loader + heading
 *   - Backend's `progress_message` if present, otherwise the active stage label
 *   - A list of canned stages with the active one highlighted
 *   - A real progress bar that advances using max(server progress, time-based asymptotic)
 *   - Elapsed time (mm:ss)
 *
 * @param {object} props
 * @param {string} props.heading                 Big title on top
 * @param {string} [props.subheading]            Small text under heading
 * @param {Array<{key:string,label:string,icon:string}>} props.stages
 * @param {number|null} [props.serverProgress]   0–100 from backend, or null
 * @param {string|null} [props.serverMessage]    Status text from backend
 * @param {number} [props.expectedSeconds]       Expected duration for fallback estimate
 */
export default function GenerationProgress({
  heading,
  subheading = 'This usually takes a minute or two',
  stages,
  serverProgress = null,
  serverMessage = null,
  expectedSeconds = 90,
}) {
  const [startedAt] = useState(() => Date.now())
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const t = setInterval(() => {
      setElapsed((Date.now() - startedAt) / 1000)
    }, 1000)
    return () => clearInterval(t)
  }, [startedAt])

  const percent = displayProgress({
    serverProgress,
    elapsedSeconds: elapsed,
    expectedSeconds,
  })

  // Map percent → which canned stage is "active" so the list visually animates
  // even when the backend doesn't send messages.
  const stageIndex = Math.min(
    stages.length - 1,
    Math.floor((percent / 100) * stages.length),
  )
  const activeStage = stages[stageIndex]

  // Live status line: server message wins over the canned stage label.
  const statusLine = (serverMessage && serverMessage.trim()) || activeStage.label

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
      className="bg-white border border-gray-200 rounded-xl p-8"
    >
      <div className="text-center mb-8">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          className="inline-block mb-4"
        >
          <Loader2 size={40} className="text-blue-500" />
        </motion.div>
        <h2 className="text-lg font-semibold text-gray-900">{heading}</h2>
        <p className="text-sm text-gray-500 mt-1">{subheading}</p>
      </div>

      {/* Live status line — the most important "I'm not stuck" signal */}
      <motion.div
        key={statusLine}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="text-center mb-6"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-100 rounded-full text-sm font-medium text-blue-700">
          <motion.div
            animate={{ scale: [1, 1.4, 1], opacity: [1, 0.4, 1] }}
            transition={{ duration: 1.2, repeat: Infinity }}
            className="w-1.5 h-1.5 rounded-full bg-blue-500"
          />
          {statusLine}
        </div>
      </motion.div>

      {/* Stage list */}
      <div className="space-y-3 max-w-sm mx-auto">
        {stages.map((stage, index) => {
          const isCompleted = index < stageIndex
          const isActive = index === stageIndex
          return (
            <motion.div
              key={stage.key}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.06 }}
              className={`flex items-center gap-3 p-3 rounded-lg transition-all duration-300 ${
                isActive ? 'bg-blue-50 border border-blue-200' : ''
              } ${isCompleted ? 'opacity-60' : ''} ${index > stageIndex ? 'opacity-30' : ''}`}
            >
              <span className="text-lg">{stage.icon}</span>
              <span
                className={`text-sm ${
                  isActive ? 'font-medium text-blue-700' : 'text-gray-600'
                }`}
              >
                {stage.label}
              </span>
              {isActive && (
                <motion.div
                  animate={{ opacity: [0.4, 1, 0.4] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                  className="ms-auto w-2 h-2 rounded-full bg-blue-500"
                />
              )}
              {isCompleted && (
                <CheckCircle2 size={16} className="ms-auto text-green-500" />
              )}
            </motion.div>
          )
        })}
      </div>

      {/* Progress bar with percentage + elapsed time */}
      <div className="mt-8">
        <div className="flex items-baseline justify-between mb-2 text-xs text-gray-500">
          <span className="font-mono font-medium text-gray-700">{Math.round(percent)}%</span>
          <span className="font-mono">{formatElapsed(elapsed)} elapsed</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden relative">
          <motion.div
            className="h-full bg-blue-500 rounded-full"
            initial={{ width: '2%' }}
            animate={{ width: `${percent}%` }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          />
          {/* Shimmer overlay so the bar visibly moves even when % is steady */}
          <motion.div
            className="absolute inset-y-0 w-1/4 bg-gradient-to-r from-transparent via-white/40 to-transparent"
            animate={{ x: ['-100%', '400%'] }}
            transition={{ duration: 2.2, repeat: Infinity, ease: 'linear' }}
          />
        </div>
      </div>
    </motion.div>
  )
}
