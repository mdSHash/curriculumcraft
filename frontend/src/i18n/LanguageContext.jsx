import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import en from './en'
import ar from './ar'

const translations = { en, ar }

const LanguageContext = createContext()

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    // One-time migration of pre-rename language preference key.
    const legacy = localStorage.getItem('mathcraft-lang')
    const current = localStorage.getItem('curriculumcraft-lang')
    if (legacy && !current) {
      localStorage.setItem('curriculumcraft-lang', legacy)
      localStorage.removeItem('mathcraft-lang')
    } else if (legacy) {
      localStorage.removeItem('mathcraft-lang')
    }
    return localStorage.getItem('curriculumcraft-lang') || 'ar'
  })

  const isRTL = lang === 'ar'

  useEffect(() => {
    localStorage.setItem('curriculumcraft-lang', lang)
    document.documentElement.setAttribute('dir', isRTL ? 'rtl' : 'ltr')
    document.documentElement.setAttribute('lang', lang)
  }, [lang, isRTL])

  const toggleLang = useCallback(() => {
    setLang((prev) => (prev === 'ar' ? 'en' : 'ar'))
  }, [])

  const t = useCallback(
    (key) => {
      const keys = key.split('.')
      let value = translations[lang]
      for (const k of keys) {
        if (value && typeof value === 'object' && k in value) {
          value = value[k]
        } else {
          // Fallback to English
          let fallback = translations.en
          for (const fk of keys) {
            if (fallback && typeof fallback === 'object' && fk in fallback) {
              fallback = fallback[fk]
            } else {
              return key // Return key if not found in either
            }
          }
          return fallback
        }
      }
      return value
    },
    [lang]
  )

  return (
    <LanguageContext.Provider value={{ lang, setLang, toggleLang, isRTL, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider')
  }
  return context
}

export default LanguageContext
