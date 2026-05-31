import { useState, useEffect } from 'react'
import { booksApi } from '../api/client'

export function useBooks() {
  const [books, setBooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const extractErrorMessage = (err, fallback) => {
    const detail = err.response?.data?.detail
    if (!detail) return err.message || fallback
    return typeof detail === 'string' ? detail : JSON.stringify(detail)
  }

  const fetchBooks = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await booksApi.list()
      setBooks(res.data)
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to fetch books'))
    } finally {
      setLoading(false)
    }
  }

  const uploadBook = async (formData, onProgress) => {
    try {
      const res = await booksApi.upload(formData, (progressEvent) => {
        if (onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percent)
        }
      })
      setBooks((prev) => [...prev, res.data])
      return res.data
    } catch (err) {
      const msg = extractErrorMessage(err, 'Upload failed')
      throw new Error(msg)
    }
  }

  const deleteBook = async (bookId) => {
    try {
      await booksApi.delete(bookId)
      setBooks((prev) => prev.filter((b) => b.id !== bookId))
    } catch (err) {
      const msg = extractErrorMessage(err, 'Failed to delete book')
      throw new Error(msg)
    }
  }

  const getOutline = async (bookId) => {
    try {
      const res = await booksApi.getOutline(bookId)
      return res.data
    } catch (err) {
      const msg = extractErrorMessage(err, 'Failed to fetch outline')
      throw new Error(msg)
    }
  }

  useEffect(() => {
    fetchBooks()
  }, [])

  return { books, loading, error, fetchBooks, uploadBook, deleteBook, getOutline }
}
