import { motion } from 'framer-motion'
import { Check } from 'lucide-react'

export default function StepIndicator({ steps, currentStep }) {
  return (
    <div className="w-full px-4 py-6">
      <div className="flex items-center justify-between relative">
        {/* Connecting line */}
        <div className="absolute top-5 left-0 right-0 h-0.5 bg-gray-200 mx-12" />
        <motion.div
          className="absolute top-5 left-0 h-0.5 bg-blue-500 mx-12"
          initial={false}
          animate={{ width: `${(currentStep / (steps.length - 1)) * (100 - (100 / steps.length))}%` }}
          transition={{ duration: 0.4, ease: 'easeInOut' }}
        />

        {steps.map((step, index) => {
          const isCompleted = index < currentStep
          const isActive = index === currentStep
          const isFuture = index > currentStep

          return (
            <div key={index} className="flex flex-col items-center relative z-10">
              {/* Step circle */}
              <motion.div
                initial={false}
                animate={{
                  scale: isActive ? 1.1 : 1,
                  backgroundColor: isCompleted ? '#2563eb' : isActive ? '#2563eb' : '#ffffff',
                  borderColor: isCompleted ? '#2563eb' : isActive ? '#2563eb' : '#d1d5db',
                }}
                transition={{ duration: 0.3 }}
                className={`
                  w-10 h-10 rounded-full border-2 flex items-center justify-center
                  ${isCompleted || isActive ? 'shadow-md shadow-blue-200' : ''}
                `}
              >
                {isCompleted ? (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  >
                    <Check size={18} className="text-white" strokeWidth={3} />
                  </motion.div>
                ) : (
                  <span className={`text-sm font-semibold ${isActive ? 'text-white' : 'text-gray-400'}`}>
                    {index + 1}
                  </span>
                )}
              </motion.div>

              {/* Step title */}
              <div className="mt-2 text-center">
                <p className={`text-xs font-semibold ${isActive ? 'text-blue-600' : isCompleted ? 'text-gray-700' : 'text-gray-400'}`}>
                  {step.title}
                </p>
                <p className={`text-[10px] mt-0.5 ${isActive ? 'text-blue-500' : 'text-gray-400'}`}>
                  {step.subtitle}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
