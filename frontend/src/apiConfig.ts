export type BackendTarget = 'legacy' | 'next'

const BACKEND_TARGET_KEY = 'backend_target'

const rawApi =
  (import.meta as any).env?.VITE_API_URL ||
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000')
const normalizedApi = String(rawApi).replace(/\/+$/, '')

function normalizeTarget(value: unknown): BackendTarget {
  return String(value || '').toLowerCase() === 'next' ? 'next' : 'legacy'
}

export function getBackendTarget(): BackendTarget {
  if (typeof window === 'undefined') {
    return normalizeTarget((import.meta as any).env?.VITE_BACKEND_TARGET)
  }
  const stored = window.localStorage.getItem(BACKEND_TARGET_KEY)
  if (stored) {
    return normalizeTarget(stored)
  }
  return normalizeTarget((import.meta as any).env?.VITE_BACKEND_TARGET)
}

export function setBackendTarget(target: BackendTarget): void {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(BACKEND_TARGET_KEY, normalizeTarget(target))
}

export function getApiBase(): string {
  return getBackendTarget() === 'next' ? `${normalizedApi}/api-next` : normalizedApi
}
