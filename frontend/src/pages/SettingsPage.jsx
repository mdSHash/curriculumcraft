import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  CheckCircle2,
  Globe,
  Github,
  Loader2,
  RefreshCw,
  Server,
  XCircle,
} from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'
import {
  clearApiBaseUrl,
  getApiBaseUrl,
  getBuildDefaultUrl,
  getOverrideUrl,
} from '../utils/apiConfig'
import BackendSettingsModal from '../components/layout/BackendSettingsModal'

const HEALTH_TIMEOUT_MS = 6000

async function probe(baseUrl) {
  if (!baseUrl) return { ok: false, error: 'no-url' }
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS)
  try {
    const res = await fetch(`${baseUrl}/api/health`, {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal,
    })
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` }
    return { ok: true, body: await res.json().catch(() => null) }
  } catch (err) {
    return { ok: false, error: err?.name === 'AbortError' ? 'timeout' : 'network' }
  } finally {
    clearTimeout(timer)
  }
}

function Section({ icon: Icon, title, description, children }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white border border-gray-200 rounded-xl p-6"
    >
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center flex-shrink-0">
          <Icon size={18} />
        </div>
        <div>
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          {description && (
            <p className="text-sm text-gray-500 mt-0.5">{description}</p>
          )}
        </div>
      </div>
      <div className="ms-13">{children}</div>
    </motion.section>
  )
}

export default function SettingsPage() {
  const { t, lang, setLang } = useLanguage()
  const [modalOpen, setModalOpen] = useState(false)
  const [probeState, setProbeState] = useState({ kind: 'idle' })

  const overrideUrl = getOverrideUrl()
  const buildUrl = getBuildDefaultUrl()
  const activeUrl = getApiBaseUrl()

  const runProbe = async () => {
    setProbeState({ kind: 'testing' })
    const result = await probe(activeUrl)
    setProbeState({ kind: result.ok ? 'ok' : 'fail', detail: result })
  }

  useEffect(() => {
    runProbe()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('settingsPage.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('settingsPage.subtitle')}</p>
      </div>

      <Section
        icon={Server}
        title={t('settingsPage.backend.title')}
        description={t('settingsPage.backend.description')}
      >
        <dl className="space-y-2 text-sm">
          <div className="flex items-baseline gap-3">
            <dt className="w-32 text-gray-500">{t('settingsPage.backend.activeUrl')}</dt>
            <dd className="flex-1 font-mono text-xs break-all">
              <code className="px-1.5 py-0.5 bg-gray-100 rounded">{activeUrl || '—'}</code>
            </dd>
          </div>
          <div className="flex items-baseline gap-3">
            <dt className="w-32 text-gray-500">{t('settingsPage.backend.source')}</dt>
            <dd className="flex-1 text-gray-700">
              {overrideUrl
                ? t('settingsPage.backend.sourceOverride')
                : buildUrl
                ? t('settingsPage.backend.sourceBuilt')
                : t('settingsPage.backend.sourceNone')}
            </dd>
          </div>
          <div className="flex items-baseline gap-3">
            <dt className="w-32 text-gray-500">{t('settingsPage.backend.health')}</dt>
            <dd className="flex-1">
              {probeState.kind === 'testing' && (
                <span className="inline-flex items-center gap-1.5 text-gray-600">
                  <Loader2 size={14} className="animate-spin" />
                  {t('settingsPage.backend.probing')}
                </span>
              )}
              {probeState.kind === 'ok' && (
                <span className="inline-flex items-center gap-1.5 text-green-700">
                  <CheckCircle2 size={14} />
                  {t('settingsPage.backend.healthy')}
                  {probeState.detail?.body?.version && (
                    <span className="text-gray-500 font-mono text-xs ms-1">
                      v{probeState.detail.body.version}
                    </span>
                  )}
                </span>
              )}
              {probeState.kind === 'fail' && (
                <span className="inline-flex items-center gap-1.5 text-red-700">
                  <XCircle size={14} />
                  {t('settingsPage.backend.unhealthy')}{' '}
                  <span className="text-gray-500 text-xs">({probeState.detail?.error})</span>
                </span>
              )}
            </dd>
          </div>
        </dl>

        <div className="mt-5 flex items-center gap-2">
          <button
            onClick={() => setModalOpen(true)}
            className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-xs font-medium hover:bg-blue-700"
          >
            {t('settingsPage.backend.changeBtn')}
          </button>
          <button
            onClick={runProbe}
            disabled={probeState.kind === 'testing'}
            className="inline-flex items-center gap-1 px-3 py-1.5 bg-white border border-gray-200 text-gray-700 rounded-md text-xs font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={12} /> {t('settingsPage.backend.testBtn')}
          </button>
          {overrideUrl && (
            <button
              onClick={() => {
                clearApiBaseUrl()
                runProbe()
              }}
              className="px-3 py-1.5 text-gray-500 text-xs underline hover:text-gray-700"
            >
              {t('settingsPage.backend.clearBtn')}
            </button>
          )}
        </div>
      </Section>

      <Section
        icon={Globe}
        title={t('settingsPage.language.title')}
        description={t('settingsPage.language.description')}
      >
        <div className="flex gap-2">
          <button
            onClick={() => setLang('en')}
            className={`flex-1 px-4 py-3 rounded-lg border text-sm font-medium transition-colors ${
              lang === 'en'
                ? 'bg-blue-50 border-blue-300 text-blue-700'
                : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
            }`}
          >
            English
          </button>
          <button
            onClick={() => setLang('ar')}
            className={`flex-1 px-4 py-3 rounded-lg border text-sm font-medium transition-colors ${
              lang === 'ar'
                ? 'bg-blue-50 border-blue-300 text-blue-700'
                : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
            }`}
          >
            العربية
          </button>
        </div>
      </Section>

      <Section
        icon={Github}
        title={t('settingsPage.about.title')}
        description={t('settingsPage.about.description')}
      >
        <ul className="space-y-2 text-sm">
          <li>
            <a
              href="https://github.com/mdSHash/curriculumcraft"
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 hover:underline"
            >
              {t('settingsPage.about.repo')}
            </a>
          </li>
          <li>
            <a
              href="https://github.com/mdSHash/curriculumcraft/blob/main/HOSTING.md"
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 hover:underline"
            >
              {t('settingsPage.about.hosting')}
            </a>
          </li>
          <li>
            <a
              href="https://huggingface.co/spaces/ScriptMaker/curriculumcraft"
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 hover:underline"
            >
              {t('settingsPage.about.space')}
            </a>
          </li>
        </ul>
      </Section>

      <BackendSettingsModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={runProbe}
      />
    </div>
  )
}
