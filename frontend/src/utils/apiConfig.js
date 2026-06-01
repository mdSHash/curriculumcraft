// Resolves the backend base URL at runtime so the GitHub Pages bundle can
// point at a self-hosted backend (e.g. a Cloudflare Tunnel) without rebuilding.
//
// Resolution order:
//   1. localStorage override (set via the in-app "Connect backend" UI)
//   2. VITE_API_BASE_URL build-time env (for fixed self-hosted deploys)
//   3. Same-origin (local dev — Vite proxy forwards /api → :8000)
//
// localStorage key is derived from BRAND.slug so renaming the product
// doesn't strand existing users on a stale URL. A one-time migration
// copies any value at the legacy `mathcraft.*` key into the new one.

import { BRAND } from '../config/brand'

const STORAGE_KEY = `${BRAND.slug}.apiBaseUrl`
const LEGACY_STORAGE_KEY = `${BRAND.legacySlug}.apiBaseUrl`

let _migrated = false

function migrateLegacyKey() {
  // Run once per session. Idempotent — once the legacy key is moved or
  // removed, re-running is a no-op.
  if (_migrated || typeof window === 'undefined') return
  _migrated = true
  try {
    const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY)
    const current = window.localStorage.getItem(STORAGE_KEY)
    if (legacy && !current) {
      window.localStorage.setItem(STORAGE_KEY, legacy)
    }
    if (legacy) {
      window.localStorage.removeItem(LEGACY_STORAGE_KEY)
    }
  } catch {
    // localStorage may be unavailable (private mode, quota, etc.) — fail open.
  }
}

function strip(url) {
  return (url || '').trim().replace(/\/+$/, '')
}

export function getOverrideUrl() {
  if (typeof window === 'undefined') return ''
  migrateLegacyKey()
  return strip(window.localStorage.getItem(STORAGE_KEY) || '')
}

export function getBuildDefaultUrl() {
  return strip(import.meta.env.VITE_API_BASE_URL || '')
}

export function getApiBaseUrl() {
  return getOverrideUrl() || getBuildDefaultUrl()
}

export function setApiBaseUrl(url) {
  if (typeof window === 'undefined') return
  migrateLegacyKey()
  const cleaned = strip(url)
  if (!cleaned) {
    window.localStorage.removeItem(STORAGE_KEY)
  } else {
    window.localStorage.setItem(STORAGE_KEY, cleaned)
  }
}

export function clearApiBaseUrl() {
  if (typeof window === 'undefined') return
  migrateLegacyKey()
  window.localStorage.removeItem(STORAGE_KEY)
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
