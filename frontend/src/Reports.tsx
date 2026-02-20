import { useEffect, useMemo, useState } from 'react'
import TopNav from './TopNav'
import './App.css'

const rawApi =
  (import.meta as any).env?.VITE_API_URL ||
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000')
const API = rawApi.replace(/\/+$/, '')
const AUTH_DISABLED = String((import.meta as any).env?.VITE_DISABLE_AUTH ?? 'false').toLowerCase() === 'true'

type ReportRow = {
  id: string
  report_label?: string | null
  filename?: string | null
  content_type?: string | null
  size_bytes?: number | null
  created_at?: string | null
  updated_at?: string | null
  created_by?: string | null
  tool_version?: string | null
  proposal_version?: number | null
  total_cost?: number | null
  total_hours?: number | null
  include_ai?: boolean
  proposal_id?: string | null
  proposal_title?: string | null
  proposal_public_id?: string | null
  url?: string | null
}

function formatDate(value?: string | null) {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString()
}

function formatBytes(value?: number | null) {
  if (value == null || Number.isNaN(value)) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

export default function Reports() {
  const [reports, setReports] = useState<ReportRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [authToken, setAuthToken] = useState<string | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (token) setAuthToken(token)
  }, [])

  const headers = useMemo(() => {
    const base: Record<string, string> = {}
    if (!AUTH_DISABLED && authToken) {
      base.Authorization = `Bearer ${authToken}`
    }
    return base
  }, [authToken])

  const loadReports = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/api/v1/reports?presign=true`, { headers })
      if (!res.ok) {
        const detail = await res.text().catch(() => '')
        throw new Error(detail || 'Failed to load reports')
      }
      const data = await res.json()
      setReports(Array.isArray(data) ? data : [])
    } catch (e: any) {
      setReports([])
      setError(e?.message || 'Failed to load reports')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (AUTH_DISABLED || authToken) {
      loadReports()
    }
  }, [authToken])

  const deleteReport = async (reportId: string) => {
    if (!confirm('Delete this saved report?')) return
    try {
      setError(null)
      const res = await fetch(`${API}/api/v1/reports/${reportId}`, {
        method: 'DELETE',
        headers,
      })
      if (!res.ok) {
        const detail = await res.text().catch(() => '')
        throw new Error(detail || 'Failed to delete report')
      }
      await loadReports()
    } catch (e: any) {
      setError(e?.message || 'Failed to delete report')
    }
  }

  const openEstimatorWithReport = (reportId: string, overwrite: boolean) => {
    const params = new URLSearchParams({ load_report_id: reportId })
    if (overwrite) {
      params.set('overwrite_report_id', reportId)
    }
    window.location.href = `/?${params.toString()}`
  }

  return (
    <div className="app app-shell">
      <TopNav />
      <div className="subcontractor-header">
        <div>
          <h1 style={{ marginBottom: 6 }}>Saved Reports</h1>
          <div className="subcontractor-note">
            Browse generated reports, download PDFs, restore payloads into the estimator, or overwrite existing entries.
          </div>
        </div>
        <div className="subcontractor-actions">
          <button className="btn" onClick={loadReports} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {!AUTH_DISABLED && !authToken && (
        <div className="subcontractor-note" style={{ marginBottom: 12 }}>
          Sign in from the Estimator page to view and manage saved reports.
        </div>
      )}
      {error && (
        <div className="subcontractor-note" style={{ marginBottom: 12, color: 'crimson' }}>
          {error}
        </div>
      )}

      {(AUTH_DISABLED || authToken) && (
        <section className="estimation-form">
          <h2>Report Library</h2>
          {loading ? (
            <div className="subcontractor-note">Loading reports...</div>
          ) : reports.length === 0 ? (
            <div className="subcontractor-note">No saved reports yet.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Report</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Proposal</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Created</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Tool</th>
                  <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Cost</th>
                  <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Hours</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((row) => (
                  <tr key={row.id}>
                    <td style={{ padding: 8 }}>
                      <div style={{ fontWeight: 600 }}>{row.report_label || row.filename || row.id}</div>
                      <div style={{ fontSize: 12, color: '#666' }}>
                        {row.filename || '-'} - {formatBytes(row.size_bytes)}
                      </div>
                    </td>
                    <td style={{ padding: 8 }}>
                      <div>{row.proposal_title || 'Untitled Proposal'}</div>
                      <div style={{ fontSize: 12, color: '#666' }}>
                        {row.proposal_public_id || row.proposal_id || '-'}
                      </div>
                    </td>
                    <td style={{ padding: 8 }}>
                      <div>{formatDate(row.created_at)}</div>
                      <div style={{ fontSize: 12, color: '#666' }}>{row.created_by || '-'}</div>
                    </td>
                    <td style={{ padding: 8 }}>
                      <div>{row.tool_version || '-'}</div>
                      <div style={{ fontSize: 12, color: '#666' }}>
                        {row.proposal_version != null ? `Proposal v${row.proposal_version}` : 'No proposal version'}
                      </div>
                    </td>
                    <td style={{ padding: 8, textAlign: 'right' }}>
                      {row.total_cost != null ? `$${Number(row.total_cost).toLocaleString()}` : '-'}
                    </td>
                    <td style={{ padding: 8, textAlign: 'right' }}>
                      {row.total_hours != null ? Number(row.total_hours).toLocaleString() : '-'}
                    </td>
                    <td style={{ padding: 8 }}>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {row.url ? (
                          <a className="btn" href={row.url} target="_blank" rel="noreferrer">
                            Download
                          </a>
                        ) : (
                          <span className="btn" style={{ opacity: 0.5, pointerEvents: 'none' }}>
                            Download
                          </span>
                        )}
                        <button className="btn" onClick={() => openEstimatorWithReport(row.id, false)}>
                          Load
                        </button>
                        <button className="btn" onClick={() => openEstimatorWithReport(row.id, true)}>
                          Load + Overwrite
                        </button>
                        <button className="btn" onClick={() => deleteReport(row.id)}>
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  )
}
