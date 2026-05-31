// Resolves the backend base URL at runtime so the GitHub Pages bundle can
// point at a self-hosted backend (e.g. a Cloudflare Tunnel) without rebuilding.
//
// Resolution order:
//   1. localStorage override (set via the in-app "Connect backend" UI)
//   2. VITE_API_BASE_URL build-time env (for fixed self-hosted deploys)
//   3. Same-origin (local dev — Vite proxy forwards /api → :8000)

const STORAGE_KEY = 'mathcraft.apiBaseUrl'

function strip(url) {
  return (url || '').trim().replace(/\/+$/, '')
}

export function getApiBaseUrl() {
  if (typeof window !== 'undefined') {
    const override = window.localStorage.getItem(STORAGE_KEY)
    if (override) return strip(override)
  }
  const buildDefault = import.meta.env.VITE_API_BASE_URL
  if (buildDefault) return strip(buildDefault)
  return ''
}

export function setApiBaseUrl(url) {
  if (typeof window === 'undefined') return
  const cleaned = strip(url)
  if (!cleaned) {
    window.localStorage.removeItem(STORAGE_KEY)
  } else {
    window.localStorage.setItem(STORAGE_KEY, cleaned)
  }
}

export function getHealthUrl() {
  return `${getApiBaseUrl()}/api/health`
}

// True when running on a host that can't possibly co-host the backend
// (currently: GitHub Pages). Used to decide whether the "demo mode" hint
// should explain that a remote backend is required.
export function isStaticHost() {
  if (typeof window === 'undefined') return false
  return window.location.hostname.endsWith('github.io')
}
