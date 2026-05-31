import { motion } from 'framer-motion'
import { Globe } from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'

export default function Header() {
  const { t, toggleLang, isRTL } = useLanguage()

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="bg-white border-b border-surface-200 px-6 py-4 flex items-center justify-between sticky top-0 z-50"
    >
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 bg-primary-600 rounded-lg flex items-center justify-center shadow-sm">
          <span className="text-white font-bold text-lg">M</span>
        </div>
        <div>
          <h1 className="text-xl font-bold text-gray-900 leading-tight">{t('header.title')}</h1>
          <p className="text-xs text-gray-500 leading-tight">{t('header.subtitle')}</p>
        </div>
      </div>

      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={toggleLang}
        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-surface-200 hover:bg-surface-50 transition-colors text-sm font-medium text-gray-700"
        aria-label="Toggle language"
      >
        <Globe size={16} />
        <span>{t('header.langToggle')}</span>
      </motion.button>
    </motion.header>
  )
}
