const rawApi =
  (import.meta as any).env?.VITE_API_URL ||
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000')

export function getApiBase(): string {
  return String(rawApi).replace(/\/+$/, '')
}
