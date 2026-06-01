import { useEffect, useState } from 'react'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import Modal from '../common/Modal'
import Button from '../common/Button'
import { getApiBaseUrl, setApiBaseUrl } from '../../utils/apiConfig'

const TEST_TIMEOUT_MS = 8000

async function testHealth(baseUrl) {
  const url = `${baseUrl.replace(/\/+$/, '')}/api/health`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TEST_TIMEOUT_MS)
  try {
    const res = await fetch(url, { method: 'GET', cache: 'no-store', signal: controller.signal })
    return res.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

export default function BackendSettingsModal({ isOpen, onClose, onSaved }) {
  const [value, setValue] = useState('')
  const [state, setState] = useState({ kind: 'idle' })

  useEffect(() => {
    if (isOpen) {
      setValue(getApiBaseUrl())
      setState({ kind: 'idle' })
    }
  }, [isOpen])

  const handleTest = async () => {
    if (!value.trim()) return
    setState({ kind: 'testing' })
    const ok = await testHealth(value)
    setState({ kind: ok ? 'ok' : 'fail' })
  }

  const handleSave = () => {
    setApiBaseUrl(value)
    onSaved?.()
    onClose()
  }

  const handleClear = () => {
    setApiBaseUrl('')
    setValue('')
    onSaved?.()
    onClose()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Connect to your backend">
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          Paste the public URL of your locally-running CurriculumCraft backend (for example, a{' '}
          <code className="px-1 py-0.5 bg-gray-100 rounded text-xs">*.trycloudflare.com</code>{' '}
          tunnel). The setting is stored in this browser only.
        </p>

        <div>
          <label htmlFor="api-url" className="block text-sm font-medium text-gray-700 mb-1.5">
            Backend URL
          </label>
          <input
            id="api-url"
            type="url"
            value={value}
            onChange={(e) => { setValue(e.target.value); setState({ kind: 'idle' }) }}
            placeholder="https://your-tunnel.trycloudflare.com"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent text-sm font-mono"
            autoComplete="off"
            spellCheck={false}
          />
        </div>

        {state.kind === 'testing' && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Loader2 size={16} className="animate-spin" /> Testing connection…
          </div>
        )}
        {state.kind === 'ok' && (
          <div className="flex items-center gap-2 text-sm text-green-700">
            <CheckCircle2 size={16} /> Backend is reachable.
          </div>
        )}
        {state.kind === 'fail' && (
          <div className="flex items-start gap-2 text-sm text-red-700">
            <XCircle size={16} className="mt-0.5 flex-shrink-0" />
            <span>
              Couldn't reach <code className="px-1 py-0.5 bg-red-50 rounded text-xs">{value}/api/health</code>.{' '}
              Check that the backend is running and the tunnel URL is correct.
            </span>
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          <button
            onClick={handleClear}
            className="text-sm text-gray-500 hover:text-gray-700 underline"
            type="button"
          >
            Clear / reset to default
          </button>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={handleTest} disabled={!value.trim() || state.kind === 'testing'}>
              Test
            </Button>
            <Button onClick={handleSave} disabled={!value.trim()}>
              Save
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  )
}
