import { motion } from 'framer-motion'
import { CheckCircle2, Loader2 } from 'lucide-react'

export default function ProgressBar({ stages, currentStage, completedStages, uploadProgress }) {
  return (
    <div className="space-y-4">
      {/* Upload progress bar (shown during upload stage) */}
      {currentStage === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mb-6"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Uploading...</span>
            <span className="text-sm font-medium text-primary-600">{uploadProgress}%</span>
          </div>
          <div className="w-full h-2 bg-surface-200 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-primary-600 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${uploadProgress}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </motion.div>
      )}

      {/* Stage list */}
      <div className="space-y-3">
        {stages.map((stage, idx) => {
          const isCompleted = completedStages.includes(stage.key)
          const isCurrent = idx === currentStage
          const isPending = idx > currentStage

          return (
            <motion.div
              key={stage.key}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.1, duration: 0.3 }}
              className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors ${
                isCurrent
                  ? 'bg-primary-50'
                  : isCompleted
                  ? 'bg-green-50'
                  : 'bg-surface-50'
              }`}
            >
              {/* Icon */}
              <div className="flex-shrink-0">
                {isCompleted ? (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                  >
                    <CheckCircle2 size={20} className="text-green-600" />
                  </motion.div>
                ) : isCurrent ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  >
                    <Loader2 size={20} className="text-primary-600" />
                  </motion.div>
                ) : (
                  <div className="w-5 h-5 rounded-full border-2 border-surface-300" />
                )}
              </div>

              {/* Label */}
              <span
                className={`text-sm font-medium ${
                  isCurrent
                    ? 'text-primary-700'
                    : isCompleted
                    ? 'text-green-700'
                    : 'text-gray-400'
                }`}
              >
                {stage.label}
              </span>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
