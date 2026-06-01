import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Loader2, Settings } from 'lucide-react'
import {
  clearApiBaseUrl,
  getApiBaseUrl,
  getBuildDefaultUrl,
  getOverrideUrl,
  isStaticHost,
} from '../../utils/apiConfig'
import BackendSettingsModal from './BackendSettingsModal'

// HF Spaces cold-start can take 30-60 s. The first probe tolerates that.
// Subsequent probes (already-warm) get a tighter budget.
const HEALTH_TIMEOUT_FIRST_MS = 20_000
const HEALTH_TIMEOUT_RETRY_MS = 8_000
// Auto-retry interval while the banner is amber. Hits the backoff sweet
// spot for HF Space wake-ups: long enough that we don't hammer a sleeping
// Space, short enough that the user sees the green state appear without
// having to manually reload the page.
const AUTO_RETRY_INTERVAL_MS = 30_000

async function probe(baseUrl, timeoutMs) {
  if (!baseUrl) return false
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${baseUrl}/api/health`, {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal,
    })
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
 *   1. Initial probe with a long timeout (covers HF Space cold-start).
 *      Tries the configured URL (localStorage override → build-time default).
 *   2. If that fails AND a localStorage override is shadowing a different
 *      build-time default, try the build-time default. If THAT works, drop
 *      the stale override automatically — rescues users whose saved URL
 *      went dead (rotating Cloudflare Tunnel, renamed HF Space, etc).
 *   3. While the banner is amber, auto-retry every 30 s. When the backend
 *      eventually responds (e.g. HF Space finishes waking from sleep),
 *      the banner clears WITHOUT requiring the user to click Retry or
 *      reload the page. Auto-retry stops as soon as a probe succeeds.
 */
export default function DemoBanner() {
  const [reachable, setReachable] = useState(null) // null = probing, true | false
  const [activeUrl, setActiveUrl] = useState(getApiBaseUrl())
  const [modalOpen, setModalOpen] = useState(false)
  const [confirmDismissed, setConfirmDismissed] = useState(false)
  // True only on the very first probe of the page lifecycle, so we can
  // give the cold-start the long timeout while subsequent retries stay
  // snappy. Reset to true if the user changes the URL (manual override).
  const isFirstProbeRef = useRef(true)
  const retryTimerRef = useRef(null)
  const probeRunningRef = useRef(false)

  const runProbe = useCallback(async () => {
    if (probeRunningRef.current) return
    probeRunningRef.current = true
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }

    const timeoutMs = isFirstProbeRef.current
      ? HEALTH_TIMEOUT_FIRST_MS
      : HEALTH_TIMEOUT_RETRY_MS

    try {
      setReachable((prev) => (prev === false ? false : null))
      const configured = getApiBaseUrl()
      setActiveUrl(configured)

      if (await probe(configured, timeoutMs)) {
        setReachable(true)
        isFirstProbeRef.current = false
        return
      }

      // Configured URL is dead. If a stale localStorage override is shadowing
      // a working build-time default, recover automatically.
      const override = getOverrideUrl()
      const buildDefault = getBuildDefaultUrl()
      if (override && buildDefault && override !== buildDefault) {
        if (await probe(buildDefault, timeoutMs)) {
          clearApiBaseUrl()
          setActiveUrl(buildDefault)
          setReachable(true)
          isFirstProbeRef.current = false
          return
        }
      }

      setReachable(false)
      isFirstProbeRef.current = false
    } finally {
      probeRunningRef.current = false
    }
  }, [])

  // Initial probe on mount.
  useEffect(() => {
    runProbe()
    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    }
  }, [runProbe])

  // Auto-retry loop while the banner is amber. Stops as soon as a probe
  // returns true (the success branch above clears reachable=true and this
  // effect re-runs, taking the no-op path).
  useEffect(() => {
    if (reachable !== false) {
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current)
        retryTimerRef.current = null
      }
      return
    }
    retryTimerRef.current = setTimeout(() => {
      retryTimerRef.current = null
      runProbe()
    }, AUTO_RETRY_INTERVAL_MS)
    return () => {
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current)
        retryTimerRef.current = null
      }
    }
  }, [reachable, runProbe])

  const handleSaved = () => {
    setConfirmDismissed(false)
    isFirstProbeRef.current = true   // user changed URL — give it cold-start budget
    runProbe()
  }

  // Probing for the FIRST time — show a quiet inline pulse so the user
  // knows we're trying. Avoids a flash of the amber banner on every load.
  if (reachable === null) {
    if (!isFirstProbeRef.current) return null
    return (
      <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 text-xs text-blue-900 flex items-center gap-2">
        <Loader2 size={14} className="animate-spin flex-shrink-0" />
        <span className="flex-1">
          Connecting to backend at <code className="px-1 py-0.5 bg-blue-100 rounded">{activeUrl}</code>
          {' '}— this can take ~30 seconds if the Space is waking from sleep.
        </span>
      </div>
    )
  }

  if (reachable === true) {
    // No banner at all when the backend is reachable AND no override is set.
    if (!getOverrideUrl() && confirmDismissed) return null
    if (!getOverrideUrl()) return null
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

  // reachable === false. Banner shows while we keep auto-retrying every 30s.
  const isStatic = isStaticHost()
  const isProbingNow = probeRunningRef.current

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 text-sm text-amber-900 flex items-start gap-2">
      <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
      <div className="flex-1 leading-snug">
        {isStatic ? (
          <>
            <span className="font-semibold">Backend unreachable.</span>{' '}
            The hosted backend at <code className="px-1 py-0.5 bg-amber-100 rounded text-xs">{activeUrl || '(none configured)'}</code> isn't responding.
            It may be waking from sleep — auto-retrying every 30 s, or you can{' '}
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
      <button
        onClick={runProbe}
        disabled={isProbingNow}
        className="px-2.5 py-1 bg-amber-100 hover:bg-amber-200 disabled:opacity-50 rounded-md text-amber-900 font-medium text-xs whitespace-nowrap flex items-center gap-1"
      >
        {isProbingNow && <Loader2 size={11} className="animate-spin" />}
        {isProbingNow ? 'Checking…' : 'Retry now'}
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
