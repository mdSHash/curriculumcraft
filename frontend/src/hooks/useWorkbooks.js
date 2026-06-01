import { useState, useEffect, useRef } from 'react'
import { workbooksApi } from '../api/client'

export function useWorkbooks() {
  const [workbooks, setWorkbooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const pollIntervalRef = useRef(null)

  const extractErrorMessage = (err, fallback) => {
    const detail = err.response?.data?.detail
    if (!detail) return err.message || fallback
    return typeof detail === 'string' ? detail : JSON.stringify(detail)
  }

  const fetchWorkbooks = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await workbooksApi.list()
      setWorkbooks(res.data)
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to fetch workbooks'))
    } finally {
      setLoading(false)
    }
  }

  const generateWorkbook = async (config) => {
    try {
      const res = await workbooksApi.generate(config)
      setWorkbooks((prev) => [...prev, res.data])
      return res.data
    } catch (err) {
      const msg = extractErrorMessage(err, 'Failed to generate workbook')
      throw new Error(msg)
    }
  }

  const pollStatus = (workbookId, onReady, onTransientError) => {
    // Robust polling with exponential backoff on transient errors.
    // Pre-Phase-4 behavior was: ANY thrown error stopped polling, which
    // meant a single 502 during HF Space cold-start (30-60s) would freeze
    // the UI on 'generating' forever even though the backend completed.
    //
    // New behavior:
    //   - Successful tick: reset backoff to base (2s).
    //   - Transient error: exponential backoff 2 → 4 → 8 → 16 → 30s cap,
    //     up to 5 consecutive failures. Caller is notified via
    //     onTransientError so the UI can show 'reconnecting...'.
    //   - 6th consecutive failure: stop polling and report error.
    //   - Status='ready' or 'error': stop polling and report.

    if (pollIntervalRef.current) {
      clearTimeout(pollIntervalRef.current)
      pollIntervalRef.current = null
    }

    const BASE_DELAY = 2000
    const MAX_DELAY = 30000
    const MAX_FAILURES = 5
    let consecutiveFailures = 0
    let cancelled = false

    const tick = async () => {
      if (cancelled) return
      try {
        const res = await workbooksApi.getStatus(workbookId)
        consecutiveFailures = 0
        const { status } = res.data

        if (status === 'ready' || status === 'error') {
          pollIntervalRef.current = null
          setWorkbooks((prev) =>
            prev.map((wb) => (wb.id === workbookId ? { ...wb, status } : wb))
          )
          if (onReady) onReady(res.data)
          return
        }

        // Still generating: reschedule at base interval.
        pollIntervalRef.current = setTimeout(tick, BASE_DELAY)
      } catch (err) {
        consecutiveFailures += 1
        if (consecutiveFailures > MAX_FAILURES) {
          pollIntervalRef.current = null
          if (onReady) onReady({ id: workbookId, status: 'error', error: 'Polling gave up after repeated failures' })
          return
        }
        // Notify caller so it can render 'reconnecting…' without aborting.
        if (onTransientError) {
          try { onTransientError(consecutiveFailures, err) } catch { /* swallow */ }
        }
        // Exponential backoff: 2 → 4 → 8 → 16 → 30 (capped).
        const delay = Math.min(BASE_DELAY * Math.pow(2, consecutiveFailures - 1), MAX_DELAY)
        pollIntervalRef.current = setTimeout(tick, delay)
      }
    }

    pollIntervalRef.current = setTimeout(tick, BASE_DELAY)

    // Returned cleanup function lets callers cancel the poll explicitly
    // (e.g. on component unmount) without relying on ref teardown.
    return () => {
      cancelled = true
      if (pollIntervalRef.current) {
        clearTimeout(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
    }
  }

  const downloadWorkbook = async (workbookId) => {
    try {
      const res = await workbooksApi.download(workbookId)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `workbook-${workbookId}.docx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      const msg = extractErrorMessage(err, 'Failed to download workbook')
      throw new Error(msg)
    }
  }

  const deleteWorkbook = async (workbookId) => {
    try {
      await workbooksApi.delete(workbookId)
      setWorkbooks((prev) => prev.filter((wb) => wb.id !== workbookId))
    } catch (err) {
      const msg = extractErrorMessage(err, 'Failed to delete workbook')
      throw new Error(msg)
    }
  }

  useEffect(() => {
    fetchWorkbooks()
    return () => {
      if (pollIntervalRef.current) {
        clearTimeout(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
    }
  }, [])

  return {
    workbooks,
    loading,
    error,
    fetchWorkbooks,
    generateWorkbook,
    pollStatus,
    downloadWorkbook,
    deleteWorkbook,
  }
}
