import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Settings } from 'lucide-react'
import { getApiBaseUrl, isStaticHost } from '../../utils/apiConfig'
import BackendSettingsModal from './BackendSettingsModal'

const HEALTH_TIMEOUT_MS = 5000

async function probeHealth() {
  const base = getApiBaseUrl()
  const url = `${base}/api/health`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS)
  try {
    const res = await fetch(url, { method: 'GET', cache: 'no-store', signal: controller.signal })
    return res.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

/**
 * Top-bar banner that shows backend connectivity status.
 *  - On a static host (GitHub Pages) with no backend configured: prompts the
 *    user to paste their tunnel URL.
 *  - When a backend URL is configured but unreachable: red banner.
 *  - When connected: a small confirmation banner that can be dismissed.
 */
export default function DemoBanner() {
  const [reachable, setReachable] = useState(null) // null = unknown / probing
  const [modalOpen, setModalOpen] = useState(false)
  const [confirmDismissed, setConfirmDismissed] = useState(false)
  const configured = Boolean(getApiBaseUrl())

  const probe = useCallback(async () => {
    setReachable(null)
    setReachable(await probeHealth())
  }, [])

  useEffect(() => { probe() }, [probe])

  const handleSaved = () => {
    setConfirmDismissed(false)
    probe()
  }

  // Hide entirely when reachable AND user has acknowledged the success banner.
  if (reachable === true && confirmDismissed) {
    return null
  }

  // Reachable on first load — hide silently in local-dev / self-hosted case
  // (only show the green confirm if the user explicitly configured a URL).
  if (reachable === true && !configured) {
    return null
  }

  if (reachable === true) {
    return (
      <div className="bg-green-50 border-b border-green-200 px-4 py-2 text-sm text-green-900 flex items-center gap-2">
        <CheckCircle2 size={16} className="flex-shrink-0" />
        <span className="flex-1">Connected to backend at <code className="px-1 py-0.5 bg-green-100 rounded text-xs">{getApiBaseUrl()}</code></span>
        <button
          onClick={() => setModalOpen(true)}
          className="text-green-800 hover:text-green-900 underline text-xs"
        >
          Change
        </button>
        <button
          onClick={() => setConfirmDismissed(true)}
          className="text-green-700 hover:text-green-900 text-xs"
          aria-label="Dismiss"
        >
          ×
        </button>
        <BackendSettingsModal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          onSaved={handleSaved}
        />
      </div>
    )
  }

  // Not reachable — show a configuration prompt.
  const isStatic = isStaticHost()

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 text-sm text-amber-900 flex items-start gap-2">
      <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
      <div className="flex-1 leading-snug">
        {isStatic ? (
          <>
            <span className="font-semibold">Backend not connected.</span>{' '}
            You're on the public demo — to actually generate workbooks, run the backend locally and connect it via a Cloudflare Tunnel.{' '}
            <a
              href="https://github.com/mdSHash/mathcraft/blob/main/HOSTING.md"
              target="_blank"
              rel="noreferrer"
              className="underline font-medium hover:text-amber-700"
            >
              Setup guide
            </a>
            .
          </>
        ) : (
          <>
            <span className="font-semibold">Backend unreachable.</span>{' '}
            Make sure the API is running on <code className="px-1 py-0.5 bg-amber-100 rounded text-xs">{getApiBaseUrl() || 'http://localhost:8000'}</code>.
          </>
        )}
      </div>
      <button
        onClick={() => setModalOpen(true)}
        className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-100 hover:bg-amber-200 rounded-md text-amber-900 font-medium text-xs whitespace-nowrap"
      >
        <Settings size={13} /> Connect backend
      </button>
      <BackendSettingsModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={handleSaved}
      />
    </div>
  )
}
