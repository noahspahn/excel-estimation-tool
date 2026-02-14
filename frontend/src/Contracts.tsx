import { useEffect, useMemo, useState } from 'react'
import './App.css'
import TopNav from './TopNav'

const rawApi = (import.meta as any).env?.VITE_API_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000')
const API = rawApi.replace(/\/+$/, '')
const AUTH_DISABLED = String((import.meta as any).env?.VITE_DISABLE_AUTH ?? 'false').toLowerCase() === 'true'

type ContractStatus = 'new' | 'in_progress' | 'submitted' | 'awarded' | 'lost'

type ContractRecord = {
  id: string
  source: string
  source_id?: string | null
  title?: string | null
  agency?: string | null
  sub_agency?: string | null
  office?: string | null
  naics?: string | null
  psc?: string | null
  set_aside?: string | null
  posted_at?: string | null
  due_at?: string | null
  value?: string | null
  location?: string | null
  url?: string | null
  synopsis?: string | null
  contract_excerpt?: string | null
  status: ContractStatus
  proposal_id?: string | null
  report_submitted_at?: string | null
  decision_date?: string | null
  awardee_name?: string | null
  award_value?: number | null
  award_notes?: string | null
  win_factors?: string | null
  loss_factors?: string | null
  analysis_notes?: string | null
  tags?: string[]
  last_seen_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

type ContractStats = {
  total: number
  by_status: Record<string, number>
  awarded: number
  lost: number
  win_rate: number
  avg_award_value?: number | null
  avg_lost_value?: number | null
  top_agencies_awarded?: { name: string; count: number }[]
  top_agencies_lost?: { name: string; count: number }[]
  top_naics_awarded?: { name: string; count: number }[]
  top_naics_lost?: { name: string; count: number }[]
  last_sync?: string | null
  last_sync_error?: string | null
}

const STATUS_OPTIONS: ContractStatus[] = [
  'new',
  'in_progress',
  'submitted',
  'awarded',
  'lost',
]

const toDateInput = (value?: string | null) => (value ? value.slice(0, 10) : '')

const formatDateLabel = (value?: string | null) => (value ? value.slice(0, 10) : '-')

export default function Contracts() {
  const [contracts, setContracts] = useState<ContractRecord[]>([])
  const [stats, setStats] = useState<ContractStats | null>(null)
  const [statusFilter, setStatusFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [statsLoading, setStatsLoading] = useState(false)
  const [syncBusy, setSyncBusy] = useState(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)
  const [authToken, setAuthToken] = useState<string | null>(null)
  const [editBuffer, setEditBuffer] = useState<Record<string, Partial<ContractRecord>>>({})
  const [newContract, setNewContract] = useState({
    title: '',
    agency: '',
    due_at: '',
    url: '',
    synopsis: '',
  })

  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (token) setAuthToken(token)
  }, [])

  const headers = useMemo(() => {
    const base: Record<string, string> = { 'Content-Type': 'application/json' }
    if (!AUTH_DISABLED && authToken) {
      base.Authorization = `Bearer ${authToken}`
    }
    return base
  }, [authToken])

  const loadStats = async () => {
    setStatsLoading(true)
    try {
      const res = await fetch(`${API}/api/v1/contracts/stats`, { headers })
      if (!res.ok) throw new Error('Failed to load stats')
      const data = await res.json()
      setStats(data)
    } catch {
      setStats(null)
    } finally {
      setStatsLoading(false)
    }
  }

  const loadContracts = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (statusFilter !== 'all') params.set('status', statusFilter)
      if (query.trim()) params.set('q', query.trim())
      const url = `${API}/api/v1/contracts?${params.toString()}`
      const res = await fetch(url, { headers })
      if (!res.ok) throw new Error('Failed to load contracts')
      const data = await res.json()
      setContracts(data || [])
    } catch {
      setContracts([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadContracts()
  }, [statusFilter, query, headers])

  useEffect(() => {
    loadStats()
  }, [headers])

  const refreshAll = async () => {
    await Promise.all([loadContracts(), loadStats()])
  }

  const syncSam = async () => {
    setSyncBusy(true)
    setSyncMessage(null)
    try {
      const res = await fetch(`${API}/api/v1/contracts/sam/sync`, {
        method: 'POST',
        headers,
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data?.detail || 'Sync failed')
      }
      setSyncMessage(`Sync ${data?.status || 'done'}: ${data?.inserted || 0} new, ${data?.updated || 0} updated.`)
      await refreshAll()
    } catch (err: any) {
      setSyncMessage(err?.message || 'Sync failed')
    } finally {
      setSyncBusy(false)
    }
  }

  const updateDraft = (id: string, patch: Partial<ContractRecord>) => {
    setEditBuffer((prev) => ({
      ...prev,
      [id]: { ...prev[id], ...patch },
    }))
  }

  const saveContract = async (id: string) => {
    const patch = editBuffer[id]
    if (!patch || Object.keys(patch).length === 0) return
    try {
      const res = await fetch(`${API}/api/v1/contracts/${id}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify(patch),
      })
      if (!res.ok) throw new Error('Update failed')
      const updated = await res.json()
      setContracts((prev) => prev.map((row) => (row.id === id ? updated : row)))
      setEditBuffer((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      await loadStats()
    } catch {
      setSyncMessage('Failed to save contract changes.')
    }
  }

  const addManualContract = async () => {
    if (!newContract.title.trim()) {
      setSyncMessage('Enter a title to add a manual contract.')
      return
    }
    try {
      const res = await fetch(`${API}/api/v1/contracts`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          title: newContract.title.trim(),
          agency: newContract.agency.trim() || undefined,
          due_at: newContract.due_at || undefined,
          url: newContract.url.trim() || undefined,
          synopsis: newContract.synopsis.trim() || undefined,
          status: 'new',
        }),
      })
      if (!res.ok) throw new Error('Failed to add contract')
      setNewContract({ title: '', agency: '', due_at: '', url: '', synopsis: '' })
      await refreshAll()
    } catch {
      setSyncMessage('Failed to add manual contract.')
    }
  }

  const statCards = [
    { label: 'Total', value: stats?.total ?? '-' },
    { label: 'New', value: stats?.by_status?.new ?? 0 },
    { label: 'In Progress', value: stats?.by_status?.in_progress ?? 0 },
    { label: 'Submitted', value: stats?.by_status?.submitted ?? 0 },
    { label: 'Awarded', value: stats?.by_status?.awarded ?? 0 },
    { label: 'Lost', value: stats?.by_status?.lost ?? 0 },
    { label: 'Win Rate', value: stats ? `${stats.win_rate}%` : '-' },
  ]

  return (
    <div className="app app-shell">
      <TopNav />
      <div className="subcontractor-header">
        <div>
          <h1 style={{ marginBottom: 6 }}>Contract Stats</h1>
          <div className="subcontractor-note">
            Track pipeline status, award outcomes, and insights from SAM.gov opportunities.
          </div>
        </div>
        <div className="subcontractor-actions">
          <button className="btn" onClick={refreshAll} disabled={loading || statsLoading}>
            Refresh
          </button>
          <button className="btn btn-primary" onClick={syncSam} disabled={syncBusy}>
            {syncBusy ? 'Syncing...' : 'Sync SAM.gov'}
          </button>
        </div>
      </div>

      {syncMessage && (
        <div className="subcontractor-note" style={{ marginBottom: 12 }}>
          {syncMessage}
        </div>
      )}

      <section className="estimation-form">
        <h2>Snapshot</h2>
        <div className="stat-grid">
          {statCards.map((card) => (
            <div key={card.label} className="stat-card">
              <div className="stat-label">{card.label}</div>
              <div className="stat-value">{card.value}</div>
            </div>
          ))}
        </div>
        <div className="stat-row">
          <div>
            <strong>Avg Award Value:</strong>{' '}
            {stats?.avg_award_value != null ? `$${stats.avg_award_value.toLocaleString()}` : '-'}
          </div>
          <div>
            <strong>Avg Lost Value:</strong>{' '}
            {stats?.avg_lost_value != null ? `$${stats.avg_lost_value.toLocaleString()}` : '-'}
          </div>
          <div>
            <strong>Last Sync:</strong> {stats?.last_sync ? stats.last_sync.slice(0, 19) : 'n/a'}
          </div>
        </div>
        {stats?.last_sync_error && (
          <div style={{ marginTop: 6, color: 'crimson' }}>
            Sync error: {stats.last_sync_error}
          </div>
        )}
        <div className="stat-grid" style={{ marginTop: 12 }}>
          <div className="stat-card">
            <div className="stat-label">Top Agencies Won</div>
            {(stats?.top_agencies_awarded || []).length > 0 ? (
              (stats?.top_agencies_awarded || []).map((row) => (
                <div key={row.name} className="stat-list-item">
                  {row.name} ({row.count})
                </div>
              ))
            ) : (
              <div className="subcontractor-note">No wins logged yet.</div>
            )}
          </div>
          <div className="stat-card">
            <div className="stat-label">Top Agencies Lost</div>
            {(stats?.top_agencies_lost || []).length > 0 ? (
              (stats?.top_agencies_lost || []).map((row) => (
                <div key={row.name} className="stat-list-item">
                  {row.name} ({row.count})
                </div>
              ))
            ) : (
              <div className="subcontractor-note">No losses logged yet.</div>
            )}
          </div>
          <div className="stat-card">
            <div className="stat-label">Top NAICS Won</div>
            {(stats?.top_naics_awarded || []).length > 0 ? (
              (stats?.top_naics_awarded || []).map((row) => (
                <div key={row.name} className="stat-list-item">
                  {row.name} ({row.count})
                </div>
              ))
            ) : (
              <div className="subcontractor-note">No NAICS wins logged yet.</div>
            )}
          </div>
          <div className="stat-card">
            <div className="stat-label">Top NAICS Lost</div>
            {(stats?.top_naics_lost || []).length > 0 ? (
              (stats?.top_naics_lost || []).map((row) => (
                <div key={row.name} className="stat-list-item">
                  {row.name} ({row.count})
                </div>
              ))
            ) : (
              <div className="subcontractor-note">No NAICS losses logged yet.</div>
            )}
          </div>
        </div>
      </section>

      <section className="estimation-form">
        <h2>New Manual Contract</h2>
        <div className="form-grid">
          <label>Title
            <input
              value={newContract.title}
              onChange={(e) => setNewContract((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="Opportunity title"
            />
          </label>
          <label>Agency
            <input
              value={newContract.agency}
              onChange={(e) => setNewContract((prev) => ({ ...prev, agency: e.target.value }))}
              placeholder="Agency name"
            />
          </label>
          <label>Due Date
            <input
              type="date"
              value={newContract.due_at}
              onChange={(e) => setNewContract((prev) => ({ ...prev, due_at: e.target.value }))}
            />
          </label>
          <label>URL
            <input
              value={newContract.url}
              onChange={(e) => setNewContract((prev) => ({ ...prev, url: e.target.value }))}
              placeholder="https://sam.gov/..."
            />
          </label>
        </div>
        <div style={{ marginTop: 8 }}>
          <label>Synopsis
            <textarea
              value={newContract.synopsis}
              onChange={(e) => setNewContract((prev) => ({ ...prev, synopsis: e.target.value }))}
              rows={2}
              style={{ width: '100%', fontFamily: 'inherit' }}
            />
          </label>
        </div>
        <button className="btn" style={{ marginTop: 8 }} onClick={addManualContract}>
          Add Manual Contract
        </button>
      </section>

      <section className="estimation-form">
        <h2>Pipeline</h2>
        <div className="subcontractor-actions" style={{ marginBottom: 12 }}>
          <label>
            Status
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ marginLeft: 6 }}
            >
              <option value="all">All</option>
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </label>
          <label>
            Search
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="title, agency, NAICS"
              style={{ marginLeft: 6 }}
            />
          </label>
        </div>
        {loading ? (
          <div className="subcontractor-note">Loading contracts...</div>
        ) : contracts.length === 0 ? (
          <div className="subcontractor-note">No contracts found for this filter.</div>
        ) : (
          <div className="subcontractor-stack">
            {contracts.map((contract) => {
              const draft = editBuffer[contract.id] || {}
              const statusValue = (draft.status || contract.status) as ContractStatus
              return (
                <div key={contract.id} className="subcontractor-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                    <div>
                      <div style={{ fontWeight: 600 }}>{draft.title ?? contract.title ?? 'Untitled contract'}</div>
                      <div className="subcontractor-note">
                        {contract.agency || 'Unknown agency'} · Due {formatDateLabel(contract.due_at)} · {contract.naics || 'NAICS n/a'}
                      </div>
                    </div>
                    <div className="subcontractor-actions">
                      {contract.url && (
                        <a className="btn" href={contract.url} target="_blank" rel="noreferrer">
                          Open Source
                        </a>
                      )}
                      <button className="btn" onClick={() => saveContract(contract.id)}>
                        Save Changes
                      </button>
                    </div>
                  </div>

                  <div className="form-grid" style={{ marginTop: 8 }}>
                    <label>Status
                      <select
                        value={statusValue}
                        onChange={(e) => updateDraft(contract.id, { status: e.target.value as ContractStatus })}
                      >
                        {STATUS_OPTIONS.map((opt) => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    </label>
                    <label>Proposal ID
                      <input
                        value={draft.proposal_id ?? contract.proposal_id ?? ''}
                        onChange={(e) => updateDraft(contract.id, { proposal_id: e.target.value })}
                        placeholder="prop_123"
                      />
                    </label>
                    <label>Due Date
                      <input
                        type="date"
                        value={toDateInput(draft.due_at ?? contract.due_at)}
                        onChange={(e) => updateDraft(contract.id, { due_at: e.target.value || null })}
                      />
                    </label>
                    <label>Set-Aside
                      <input
                        value={draft.set_aside ?? contract.set_aside ?? ''}
                        onChange={(e) => updateDraft(contract.id, { set_aside: e.target.value })}
                      />
                    </label>
                  </div>

                  <details style={{ marginTop: 8 }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Outcome & Analysis</summary>
                    <div className="form-grid" style={{ marginTop: 8 }}>
                      <label>Decision Date
                        <input
                          type="date"
                          value={toDateInput(draft.decision_date ?? contract.decision_date)}
                          onChange={(e) => updateDraft(contract.id, { decision_date: e.target.value || null })}
                        />
                      </label>
                      <label>Report Submitted
                        <input
                          type="date"
                          value={toDateInput(draft.report_submitted_at ?? contract.report_submitted_at)}
                          onChange={(e) => updateDraft(contract.id, { report_submitted_at: e.target.value || null })}
                        />
                      </label>
                      <label>Awardee / Winner
                        <input
                          value={draft.awardee_name ?? contract.awardee_name ?? ''}
                          onChange={(e) => updateDraft(contract.id, { awardee_name: e.target.value })}
                        />
                      </label>
                      <label>Award Value
                        <input
                          type="number"
                          value={draft.award_value ?? contract.award_value ?? ''}
                          onChange={(e) => updateDraft(contract.id, { award_value: e.target.value ? Number(e.target.value) : null })}
                        />
                      </label>
                      <label>Tags
                        <input
                          value={(draft.tags ?? contract.tags ?? []).join(', ')}
                          onChange={(e) => updateDraft(contract.id, { tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean) })}
                          placeholder="cloud, security, integrator"
                        />
                      </label>
                    </div>
                    <div style={{ marginTop: 8 }}>
                      <label>Award Notes
                        <textarea
                          value={draft.award_notes ?? contract.award_notes ?? ''}
                          onChange={(e) => updateDraft(contract.id, { award_notes: e.target.value })}
                          rows={2}
                          style={{ width: '100%', fontFamily: 'inherit' }}
                        />
                      </label>
                    </div>
                    <div style={{ marginTop: 8 }}>
                      <label>Win Factors
                        <textarea
                          value={draft.win_factors ?? contract.win_factors ?? ''}
                          onChange={(e) => updateDraft(contract.id, { win_factors: e.target.value })}
                          rows={2}
                          style={{ width: '100%', fontFamily: 'inherit' }}
                        />
                      </label>
                    </div>
                    <div style={{ marginTop: 8 }}>
                      <label>Loss Factors
                        <textarea
                          value={draft.loss_factors ?? contract.loss_factors ?? ''}
                          onChange={(e) => updateDraft(contract.id, { loss_factors: e.target.value })}
                          rows={2}
                          style={{ width: '100%', fontFamily: 'inherit' }}
                        />
                      </label>
                    </div>
                    <div style={{ marginTop: 8 }}>
                      <label>Analysis Notes
                        <textarea
                          value={draft.analysis_notes ?? contract.analysis_notes ?? ''}
                          onChange={(e) => updateDraft(contract.id, { analysis_notes: e.target.value })}
                          rows={2}
                          style={{ width: '100%', fontFamily: 'inherit' }}
                        />
                      </label>
                    </div>
                  </details>

                  {(contract.synopsis || contract.contract_excerpt) && (
                    <div style={{ marginTop: 8 }} className="subcontractor-note">
                      {contract.contract_excerpt || contract.synopsis}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
