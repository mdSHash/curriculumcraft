import { motion } from 'framer-motion'

const paddingOptions = {
  none: '',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
}

export default function Card({
  children,
  variant = 'default',
  padding = 'md',
  header,
  footer,
  className = '',
  onClick,
}) {
  const Component = variant === 'interactive' ? motion.div : 'div'
  const motionProps =
    variant === 'interactive'
      ? {
          whileHover: { y: -2, shadow: '0 8px 30px rgba(0,0,0,0.08)' },
          transition: { duration: 0.2 },
        }
      : {}

  return (
    <Component
      className={`bg-white rounded-xl border border-surface-200 shadow-sm ${
        variant === 'interactive' ? 'hover:shadow-md cursor-pointer' : ''
      } transition-shadow duration-200 ${className}`}
      onClick={onClick}
      {...motionProps}
    >
      {header && (
        <div className="px-6 py-4 border-b border-surface-200">
          {typeof header === 'string' ? (
            <h3 className="text-lg font-semibold text-gray-900">{header}</h3>
          ) : (
            header
          )}
        </div>
      )}
      <div className={paddingOptions[padding]}>{children}</div>
      {footer && (
        <div className="px-6 py-4 border-t border-surface-200 bg-surface-50 rounded-b-xl">
          {footer}
        </div>
      )}
    </Component>
  )
}
