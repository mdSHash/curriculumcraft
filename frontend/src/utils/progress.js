// Progress display helpers.
//
// We have two sources of progress for a long-running generation:
//   1. The backend's reported `progress` (0-100) when it's available — preferred.
//   2. A time-based asymptotic curve that creeps toward 95% over the
//      expected duration — fallback when the backend doesn't report progress
//      (e.g. an old build) or hasn't reported anything yet.
//
// The displayed value is the MAX of the two so progress only ever moves
// forward, never snaps backwards if the backend reports a lower percent
// than the time estimate already showed.

const DEFAULT_EXPECTED_SECONDS = 90 // optimistic ~1.5 min target
const TIME_ASYMPTOTE = 95           // never let the time estimate hit 100

/**
 * Asymptotic time-based progress estimate.
 *
 * Formula: 95 * (1 - exp(-elapsed / expected))
 *   - 0s   → 0%
 *   - 30s  → ~27% (at expected=90s)
 *   - 90s  → ~60%
 *   - 180s → ~85%
 *   - ∞    → 95%
 */
export function timeBasedProgress(elapsedSeconds, expectedSeconds = DEFAULT_EXPECTED_SECONDS) {
  if (!elapsedSeconds || elapsedSeconds <= 0) return 0
  const tau = Math.max(20, expectedSeconds)
  const fraction = 1 - Math.exp(-elapsedSeconds / tau)
  return Math.min(TIME_ASYMPTOTE, Math.max(0, fraction * TIME_ASYMPTOTE))
}

/**
 * Pick the best progress value to display.
 *
 * @param {object} args
 * @param {number|null} args.serverProgress  0-100 from backend, or null/undefined
 * @param {number} args.elapsedSeconds       seconds since the request started
 * @param {number} [args.expectedSeconds]    expected total duration
 * @returns {number} 0-100
 */
export function displayProgress({ serverProgress, elapsedSeconds, expectedSeconds }) {
  const time = timeBasedProgress(elapsedSeconds, expectedSeconds)
  const server = typeof serverProgress === 'number' && serverProgress > 0 ? serverProgress : 0
  // Cap at 99 while not finished — only "ready" status reaches 100.
  return Math.min(99, Math.max(time, server))
}

/** Format seconds as mm:ss. */
export function formatElapsed(seconds) {
  const s = Math.max(0, Math.floor(seconds))
  const mm = Math.floor(s / 60)
  const ss = s % 60
  return `${mm}:${ss.toString().padStart(2, '0')}`
}
