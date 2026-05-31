import { useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'

/**
 * Probes the backend at mount and renders a top banner when the API is
 * unreachable. This is the case on the GitHub Pages static demo, where
 * only the frontend bundle is served.
 */
export default function DemoBanner() {
  const [apiReachable, setApiReachable] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetch('/api/health', { method: 'GET', cache: 'no-store' })
      .then((res) => { if (!cancelled) setApiReachable(res.ok) })
      .catch(() => { if (!cancelled) setApiReachable(false) })
    return () => { cancelled = true }
  }, [])

  if (apiReachable) return null

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 text-sm text-amber-900 flex items-start gap-2">
      <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
      <p className="leading-snug">
        <span className="font-semibold">Demo mode.</span>{' '}
        You're viewing the static UI on GitHub Pages — the backend isn't running here, so uploads and generation won't work.
        Clone{' '}
        <a
          href="https://github.com/mdSHash/mathcraft"
          target="_blank"
          rel="noreferrer"
          className="underline font-medium hover:text-amber-700"
        >
          the repo
        </a>{' '}
        and follow the README to run the full app locally.
      </p>
    </div>
  )
}
