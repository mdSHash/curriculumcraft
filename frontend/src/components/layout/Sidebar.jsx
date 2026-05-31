import { NavLink, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Home, Upload, FileText, Settings } from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'

export default function Sidebar() {
  const location = useLocation()
  const { t, isRTL } = useLanguage()

  const navItems = [
    { to: '/', icon: Home, labelKey: 'nav.dashboard' },
    { to: '/upload', icon: Upload, labelKey: 'nav.upload' },
    { to: '#', icon: FileText, labelKey: 'nav.workbooks' },
    { to: '#', icon: Settings, labelKey: 'nav.settings' },
  ]

  return (
    <aside className="w-60 bg-white border-e border-surface-200 p-4 flex flex-col gap-1">
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = item.to === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(item.to) && item.to !== '#'

          return (
            <NavLink
              key={item.labelKey}
              to={item.to}
              className="relative"
            >
              <motion.div
                whileHover={{ x: isRTL ? -4 : 4 }}
                whileTap={{ scale: 0.97 }}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-surface-100 hover:text-gray-900'
                }`}
              >
                <Icon size={18} strokeWidth={isActive ? 2.2 : 1.8} />
                <span>{t(item.labelKey)}</span>
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active"
                    className={`absolute ${isRTL ? 'right-0' : 'left-0'} top-1/2 -translate-y-1/2 w-1 h-6 bg-primary-600 ${isRTL ? 'rounded-l-full' : 'rounded-r-full'}`}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  />
                )}
              </motion.div>
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}
