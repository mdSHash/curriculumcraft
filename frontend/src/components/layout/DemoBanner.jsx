import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Settings } from 'lucide-react'
import {
  clearApiBaseUrl,
  getApiBaseUrl,
  getBuildDefaultUrl,
  getOverrideUrl,
  isStaticHost,
} from '../../utils/apiConfig'
import BackendSettingsModal from './BackendSettingsModal'

const HEALTH_TIMEOUT_MS = 5000

async function probe(baseUrl) {
  if (!baseUrl) return false
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS)
  try {
    const res = await fetch(`${baseUrl}/api/health`, { method: 'GET', cache: 'no-store', signal: controller.signal })
    return res.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

/**
 * Top-bar banner that shows backend connectivity status.
 *
 * Probe strategy:
 *   1. Try the configured URL (localStorage override → build-time default).
 *   2. If that fails AND a localStorage override is shadowing a different
 *      build-time default, try the build-time default. If THAT works, drop
 *      the stale override automatically — this rescues users whose saved
 *      URL went dead (e.g. a rotating Cloudflare Tunnel URL).
 */
export default function DemoBanner() {
  const [reachable, setReachable] = useState(null) // null = probing
  const [activeUrl, setActiveUrl] = useState(getApiBaseUrl())
  const [modalOpen, setModalOpen] = useState(false)
  const [confirmDismissed, setConfirmDismissed] = useState(false)

  const runProbe = useCallback(async () => {
    setReachable(null)
    const configured = getApiBaseUrl()
    setActiveUrl(configured)

    if (await probe(configured)) {
      setReachable(true)
      return
    }

    // Configured URL is dead. If a stale localStorage override is shadowing
    // a working build-time default, recover automatically.
    const override = getOverrideUrl()
    const buildDefault = getBuildDefaultUrl()
    if (override && buildDefault && override !== buildDefault) {
      if (await probe(buildDefault)) {
        clearApiBaseUrl()
        setActiveUrl(buildDefault)
        setReachable(true)
        return
      }
    }

    setReachable(false)
  }, [])

  useEffect(() => { runProbe() }, [runProbe])

  const handleSaved = () => {
    setConfirmDismissed(false)
    runProbe()
  }

  // Probing — render nothing (avoids a flash of the amber banner on every load).
  if (reachable === null) return null

  if (reachable === true) {
    // No banner at all when the backend is reachable AND no override is set.
    if (!getOverrideUrl() && confirmDismissed) return null
    if (!getOverrideUrl()) {
      // Successful default connection on first load — stay invisible.
      return null
    }
    if (confirmDismissed) return null

    return (
      <div className="bg-green-50 border-b border-green-200 px-4 py-2 text-sm text-green-900 flex items-center gap-2">
        <CheckCircle2 size={16} className="flex-shrink-0" />
        <span className="flex-1">
          Connected to backend at <code className="px-1 py-0.5 bg-green-100 rounded text-xs">{activeUrl}</code>
        </span>
        <button onClick={() => setModalOpen(true)} className="text-green-800 hover:text-green-900 underline text-xs">
          Change
        </button>
        <button onClick={() => setConfirmDismissed(true)} className="text-green-700 hover:text-green-900 text-xs" aria-label="Dismiss">
          ×
        </button>
        <BackendSettingsModal isOpen={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />
      </div>
    )
  }

  // Not reachable.
  const isStatic = isStaticHost()

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 text-sm text-amber-900 flex items-start gap-2">
      <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
      <div className="flex-1 leading-snug">
        {isStatic ? (
          <>
            <span className="font-semibold">Backend unreachable.</span>{' '}
            The hosted backend at <code className="px-1 py-0.5 bg-amber-100 rounded text-xs">{activeUrl || '(none configured)'}</code> isn't responding.
            It may be waking from sleep — try again in ~30 seconds — or you can{' '}
            <a
              href="https://github.com/mdSHash/curriculumcraft/blob/main/HOSTING.md"
              target="_blank"
              rel="noreferrer"
              className="underline font-medium hover:text-amber-700"
            >
              connect a different backend
            </a>
            .
          </>
        ) : (
          <>
            <span className="font-semibold">Backend unreachable.</span>{' '}
            Make sure the API is running on{' '}
            <code className="px-1 py-0.5 bg-amber-100 rounded text-xs">{activeUrl || 'http://localhost:8000'}</code>.
          </>
        )}
      </div>
      <button onClick={runProbe} className="px-2.5 py-1 bg-amber-100 hover:bg-amber-200 rounded-md text-amber-900 font-medium text-xs whitespace-nowrap">
        Retry
      </button>
      <button
        onClick={() => setModalOpen(true)}
        className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-100 hover:bg-amber-200 rounded-md text-amber-900 font-medium text-xs whitespace-nowrap"
      >
        <Settings size={13} /> Connect backend
      </button>
      <BackendSettingsModal isOpen={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />
    </div>
  )
}
