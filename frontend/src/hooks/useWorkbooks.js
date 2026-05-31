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

  const pollStatus = async (workbookId, onReady) => {
    // Clear any existing poll
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await workbooksApi.getStatus(workbookId)
        const { status } = res.data

        if (status === 'ready' || status === 'error') {
          clearInterval(pollIntervalRef.current)
          pollIntervalRef.current = null

          // Update workbook in list
          setWorkbooks((prev) =>
            prev.map((wb) => (wb.id === workbookId ? { ...wb, status } : wb))
          )

          if (onReady) {
            onReady(res.data)
          }
        }
      } catch (err) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
    }, 2000)
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
        clearInterval(pollIntervalRef.current)
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
