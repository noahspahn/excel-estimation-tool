import { useEffect, useMemo, useState } from 'react'
import './App.css'
import TopNav from './TopNav'

const rawApi = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000'
const API = rawApi.replace(/\/+$/, '')
const AUTH_DISABLED = String((import.meta as any).env?.VITE_DISABLE_AUTH ?? 'true').toLowerCase() === 'true'

const STORAGE_KEY = 'subcontractor_workspace_v1'
const DRAFT_KEY = 'estimation_draft'

type ScrapeResult = {
  url: string
  final_url?: string | null
  success: boolean
  status_code?: number | null
  content_type?: string | null
  encoding?: string | null
  text_excerpt: string
  truncated?: boolean
  error?: string | null
}

type RequiredRole = {
  id: string
  role: string
  skills: string
  hours: number
  rate: string
  notes: string
}

type SubcontractorStatus = 'target' | 'contacted' | 'screening' | 'shortlisted' | 'selected' | 'declined'
type SubcontractorSource = 'upwork' | 'referral' | 'internal' | 'other'

type Subcontractor = {
  id: string
  name: string
  role: string
  skills: string
  rate: string
  availability: string
  location: string
  status: SubcontractorStatus
  source: SubcontractorSource
  profileUrl: string
  notes: string
}

type ProjectSnapshot = {
  name: string
  scope: string
  tags: string
  location: string
  clearance: string
  budget: string
  timeline: string
  modules: string[]
}

type UpworkState = {
  query: string
  lastScrape: ScrapeResult | null
}

type Workspace = {
  project: ProjectSnapshot
  requiredRoles: RequiredRole[]
  subcontractors: Subcontractor[]
  upwork: UpworkState
}

const STATUS_OPTIONS: SubcontractorStatus[] = [
  'target',
  'contacted',
  'screening',
  'shortlisted',
  'selected',
  'declined',
]

const SOURCE_OPTIONS: SubcontractorSource[] = ['upwork', 'referral', 'internal', 'other']

const defaultWorkspace: Workspace = {
  project: {
    name: '',
    scope: '',
    tags: '',
    location: '',
    clearance: '',
    budget: '',
    timeline: '',
    modules: [],
  },
  requiredRoles: [],
  subcontractors: [],
  upwork: {
    query: '',
    lastScrape: null,
  },
}

const makeId = (prefix: string) => `${prefix}_${Math.random().toString(36).slice(2, 10)}`

const normalizeWorkspace = (input: any): Workspace => {
  const project = { ...defaultWorkspace.project, ...(input?.project || {}) }
  project.modules = Array.isArray(project.modules) ? project.modules : []
  return {
    project,
    requiredRoles: Array.isArray(input?.requiredRoles) ? input.requiredRoles : [],
    subcontractors: Array.isArray(input?.subcontractors) ? input.subcontractors : [],
    upwork: { ...defaultWorkspace.upwork, ...(input?.upwork || {}) },
  }
}

const normalizeMap = (src: any): Record<string, any> => {
  if (Array.isArray(src)) {
    return src.reduce((acc, item, idx) => ({ ...acc, [String(idx)]: item }), {} as Record<string, any>)
  }
  return { ...(src || {}) }
}

const buildUpworkSearchUrl = (query: string) =>
  query ? `https://www.upwork.com/nx/search/talent/?q=${encodeURIComponent(query)}` : ''

const uniqueTokens = (tokens: string[]) => {
  const seen = new Set<string>()
  const result: string[] = []
  tokens.forEach((token) => {
    const trimmed = token.trim()
    if (!trimmed) return
    const key = trimmed.toLowerCase()
    if (seen.has(key)) return
    seen.add(key)
    result.push(trimmed)
  })
  return result
}

export default function Subcontractors() {
  const [workspace, setWorkspace] = useState<Workspace>(defaultWorkspace)
  const [modules, setModules] = useState<any[]>([])
  const [authToken, setAuthToken] = useState<string | null>(null)
  const [scrapeLoading, setScrapeLoading] = useState(false)
  const [scrapeError, setScrapeError] = useState<string | null>(null)
  const [draftMessage, setDraftMessage] = useState<string | null>(null)
  const [scratchpad, setScratchpad] = useState('')

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    try {
      const parsed = JSON.parse(raw)
      setWorkspace(normalizeWorkspace(parsed))
    } catch {}
  }, [])

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(workspace))
  }, [workspace])

  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (token) setAuthToken(token)
  }, [])

  useEffect(() => {
    fetch(`${API}/api/v1/modules`)
      .then((res) => res.json())
      .then((rows) => setModules(rows || []))
      .catch(() => {})
  }, [])

  const moduleMap = useMemo(() => {
    const map: Record<string, any> = {}
    modules.forEach((m) => {
      if (m?.id) map[m.id] = m
    })
    return map
  }, [modules])

  const moduleSummary = useMemo(() => {
    if (!workspace.project.modules.length) return ''
    return workspace.project.modules.map((id) => moduleMap[id]?.name || id).join(', ')
  }, [moduleMap, workspace.project.modules])

  const searchUrl = useMemo(
    () => buildUpworkSearchUrl(workspace.upwork.query),
    [workspace.upwork.query],
  )

  const selectedCount = useMemo(
    () => workspace.subcontractors.filter((s) => s.status === 'selected').length,
    [workspace.subcontractors],
  )

  const updateProjectField = (field: keyof ProjectSnapshot, value: string | string[]) => {
    setWorkspace((prev) => ({
      ...prev,
      project: { ...prev.project, [field]: value },
    }))
  }

  const addRequiredRole = (seed?: Partial<RequiredRole>) => {
    const next: RequiredRole = {
      id: makeId('role'),
      role: seed?.role || 'Role',
      skills: seed?.skills || '',
      hours: seed?.hours ?? 0,
      rate: seed?.rate || '',
      notes: seed?.notes || '',
    }
    setWorkspace((prev) => ({ ...prev, requiredRoles: [...prev.requiredRoles, next] }))
  }

  const updateRequiredRole = (id: string, patch: Partial<RequiredRole>) => {
    setWorkspace((prev) => ({
      ...prev,
      requiredRoles: prev.requiredRoles.map((r) => (r.id === id ? { ...r, ...patch } : r)),
    }))
  }

  const removeRequiredRole = (id: string) => {
    setWorkspace((prev) => ({
      ...prev,
      requiredRoles: prev.requiredRoles.filter((r) => r.id !== id),
    }))
  }

  const addSubcontractor = (seed?: Partial<Subcontractor>) => {
    const next: Subcontractor = {
      id: makeId('sub'),
      name: seed?.name || 'New Lead',
      role: seed?.role || '',
      skills: seed?.skills || '',
      rate: seed?.rate || '',
      availability: seed?.availability || '',
      location: seed?.location || '',
      status: seed?.status || 'target',
      source: seed?.source || 'upwork',
      profileUrl: seed?.profileUrl || '',
      notes: seed?.notes || '',
    }
    setWorkspace((prev) => ({ ...prev, subcontractors: [...prev.subcontractors, next] }))
  }

  const updateSubcontractor = (id: string, patch: Partial<Subcontractor>) => {
    setWorkspace((prev) => ({
      ...prev,
      subcontractors: prev.subcontractors.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    }))
  }

  const removeSubcontractor = (id: string) => {
    setWorkspace((prev) => ({
      ...prev,
      subcontractors: prev.subcontractors.filter((s) => s.id !== id),
    }))
  }

  const buildQueryFromScope = () => {
    const tags = workspace.project.tags.split(',').map((t) => t.trim())
    const roles = workspace.requiredRoles.map((r) => r.role.trim()).filter(Boolean)
    const location = workspace.project.location.trim()
    const combined = uniqueTokens([...tags, ...roles, location].filter(Boolean))
    if (combined.length > 0) return combined.slice(0, 10).join(' ')
    const fallback = workspace.project.scope.split(/\s+/).filter(Boolean).slice(0, 12)
    return fallback.join(' ')
  }

  const applyQueryFromScope = () => {
    const next = buildQueryFromScope()
    setWorkspace((prev) => ({ ...prev, upwork: { ...prev.upwork, query: next } }))
  }

  const openUpworkSearch = () => {
    if (!searchUrl) return
    window.open(searchUrl, '_blank', 'noreferrer')
  }

  const runScrape = async () => {
    setScrapeError(null)
    if (!searchUrl) {
      setScrapeError('Enter a search query first.')
      return
    }
    if (!AUTH_DISABLED && !authToken) {
      setScrapeError('Sign in on the estimator page before scraping.')
      return
    }
    setScrapeLoading(true)
    try {
      const res = await fetch(`${API}/api/v1/scrape/url`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(!AUTH_DISABLED && authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify({
          url: searchUrl,
          max_bytes: 200000,
          max_chars: 4000,
          timeout: 12.0,
        }),
      })
      if (!res.ok) {
        if (res.status === 401) {
          setScrapeError('Unauthorized. Please sign in again.')
        } else {
          const text = await res.text()
          setScrapeError(`Scrape failed (${res.status}): ${text || 'Unknown error'}`)
        }
        return
      }
      const data = await res.json()
      setWorkspace((prev) => ({ ...prev, upwork: { ...prev.upwork, lastScrape: data } }))
    } catch (err) {
      console.error('Upwork scrape error', err)
      setScrapeError('Network or server error while scraping.')
    } finally {
      setScrapeLoading(false)
    }
  }

  const addLeadsFromScratchpad = () => {
    const lines = scratchpad.split('\n').map((line) => line.trim()).filter(Boolean)
    if (!lines.length) return
    const leads = uniqueTokens(lines)
      .filter((line) => line.length >= 3)
      .slice(0, 25)
      .map((line) => {
        const clipped = line.length > 80 ? `${line.slice(0, 77)}...` : line
        return {
          name: clipped,
          source: 'upwork' as SubcontractorSource,
          status: 'target' as SubcontractorStatus,
          notes: workspace.upwork.query ? `Source query: ${workspace.upwork.query}` : '',
        }
      })
    if (leads.length === 0) return
    setWorkspace((prev) => ({
      ...prev,
      subcontractors: [
        ...prev.subcontractors,
        ...leads.map((lead) => ({
          id: makeId('sub'),
          name: lead.name,
          role: '',
          skills: '',
          rate: '',
          availability: '',
          location: '',
          status: lead.status,
          source: lead.source,
          profileUrl: '',
          notes: lead.notes,
        })),
      ],
    }))
  }

  const loadEstimatorDraft = () => {
    setDraftMessage(null)
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) {
      setDraftMessage('No estimator draft found. Save a draft from the estimator first.')
      return
    }
    try {
      const draft = JSON.parse(raw)
      const input = draft?.estimation_input || {}
      const result = draft?.estimation_result || {}
      const moduleIds = Array.isArray(input?.modules) ? input.modules : []
      const rolesMap = normalizeMap(result?.breakdown_by_role)
      const roleRows = Object.values(rolesMap).map((row: any) => ({
        id: makeId('role'),
        role: row?.role_name || 'Role',
        skills: '',
        hours: Number(row?.hours || 0),
        rate: row?.effective_rate ? `$${Number(row.effective_rate).toFixed(2)}/hr` : '',
        notes: '',
      }))
      const moduleTags = moduleIds.map((id: string) => moduleMap[id]?.name || id)
      const roleTags = roleRows.map((r) => r.role)
      const autoTags = uniqueTokens([...moduleTags, ...roleTags]).join(', ')
      const budgetValue = Number(result?.total_cost || 0)
      const budget = budgetValue > 0 ? `$${budgetValue.toFixed(0)}` : ''

      setWorkspace((prev) => ({
        ...prev,
        project: {
          ...prev.project,
          name: input?.project_name || prev.project.name,
          scope: input?.additional_comments || prev.project.scope,
          location: input?.site_location || prev.project.location,
          modules: moduleIds.length ? moduleIds : prev.project.modules,
          tags: prev.project.tags || autoTags,
          budget: budget || prev.project.budget,
        },
        requiredRoles: roleRows.length ? roleRows : prev.requiredRoles,
      }))
      setDraftMessage('Estimator draft loaded into this workspace.')
    } catch {
      setDraftMessage('Failed to parse estimator draft.')
    }
  }

  const exportWorkspace = () => {
    const blob = new Blob([JSON.stringify(workspace, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15)
    a.download = `subcontractors_${ts}.json`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const importWorkspace = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result))
        setWorkspace(normalizeWorkspace(parsed))
        setDraftMessage('Workspace imported.')
      } catch {
        setDraftMessage('Invalid workspace file.')
      }
    }
    reader.readAsText(file)
  }

  const resetWorkspace = () => {
    if (!confirm('Clear all subcontractor workspace data?')) return
    setWorkspace(defaultWorkspace)
    setScratchpad('')
    setScrapeError(null)
    setDraftMessage(null)
  }

  return (
    <div className="app app-shell subcontractor-page">
      <TopNav />
      <div className="subcontractor-header">
        <div>
          <h1 style={{ marginBottom: 6 }}>Subcontractor Manager</h1>
          <div className="subcontractor-note">
            Track required roles, manage leads, and scout Upwork for subcontractors.
          </div>
        </div>
        <div className="subcontractor-summary">
          <div><strong>Roles:</strong> {workspace.requiredRoles.length}</div>
          <div><strong>Leads:</strong> {workspace.subcontractors.length}</div>
          <div><strong>Selected:</strong> {selectedCount}</div>
        </div>
      </div>

      <section className="estimation-form">
        <h2>Project Scope</h2>
        <div className="form-grid">
          <label>Project Name
            <input
              value={workspace.project.name}
              onChange={(e) => updateProjectField('name', e.target.value)}
            />
          </label>
          <label>Location
            <input
              value={workspace.project.location}
              onChange={(e) => updateProjectField('location', e.target.value)}
            />
          </label>
          <label>Clearance
            <input
              value={workspace.project.clearance}
              onChange={(e) => updateProjectField('clearance', e.target.value)}
            />
          </label>
          <label>Budget Range
            <input
              value={workspace.project.budget}
              onChange={(e) => updateProjectField('budget', e.target.value)}
              placeholder="$250k-$400k"
            />
          </label>
          <label>Timeline
            <input
              value={workspace.project.timeline}
              onChange={(e) => updateProjectField('timeline', e.target.value)}
              placeholder="e.g., 6 months"
            />
          </label>
          <label>Skill Tags
            <input
              value={workspace.project.tags}
              onChange={(e) => updateProjectField('tags', e.target.value)}
              placeholder="networking, cabling, cloud migration"
            />
          </label>
        </div>
        <div style={{ marginTop: 10 }}>
          <label>Scope Summary
            <textarea
              value={workspace.project.scope}
              onChange={(e) => updateProjectField('scope', e.target.value)}
              rows={3}
              style={{ width: '100%', fontFamily: 'inherit' }}
              placeholder="Describe the scope that drives subcontractor needs."
            />
          </label>
        </div>
        {moduleSummary && (
          <div style={{ marginTop: 8 }} className="subcontractor-note">
            Estimator modules: {moduleSummary}
          </div>
        )}
        <div className="subcontractor-actions" style={{ marginTop: 10 }}>
          <button className="btn" onClick={loadEstimatorDraft}>Load from Estimator Draft</button>
          <button className="btn" onClick={exportWorkspace}>Export JSON</button>
          <label className="btn" style={{ cursor: 'pointer' }}>
            Import JSON
            <input
              type="file"
              accept="application/json"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) importWorkspace(file)
                e.currentTarget.value = ''
              }}
              style={{ display: 'none' }}
            />
          </label>
          <button className="btn" onClick={resetWorkspace}>Reset Workspace</button>
        </div>
        {draftMessage && (
          <div style={{ marginTop: 8 }} className="subcontractor-note">
            {draftMessage}
          </div>
        )}
      </section>

      <section className="estimation-form">
        <h2>Required Roles</h2>
        {workspace.requiredRoles.length === 0 ? (
          <div className="subcontractor-note">No required roles yet. Add roles or load from a draft.</div>
        ) : (
          <div className="subcontractor-stack">
            {workspace.requiredRoles.map((role) => (
              <div key={role.id} className="subcontractor-card">
                <div className="form-grid">
                  <label>Role
                    <input
                      value={role.role}
                      onChange={(e) => updateRequiredRole(role.id, { role: e.target.value })}
                    />
                  </label>
                  <label>Skills
                    <input
                      value={role.skills}
                      onChange={(e) => updateRequiredRole(role.id, { skills: e.target.value })}
                      placeholder="skills or certifications"
                    />
                  </label>
                  <label>Estimated Hours
                    <input
                      type="number"
                      min={0}
                      value={role.hours}
                      onChange={(e) => updateRequiredRole(role.id, { hours: Number(e.target.value || 0) })}
                    />
                  </label>
                  <label>Target Rate
                    <input
                      value={role.rate}
                      onChange={(e) => updateRequiredRole(role.id, { rate: e.target.value })}
                      placeholder="$85/hr"
                    />
                  </label>
                </div>
                <div style={{ marginTop: 8 }}>
                  <label>Notes
                    <textarea
                      value={role.notes}
                      onChange={(e) => updateRequiredRole(role.id, { notes: e.target.value })}
                      rows={2}
                      style={{ width: '100%', fontFamily: 'inherit' }}
                    />
                  </label>
                </div>
                <div className="subcontractor-actions" style={{ marginTop: 8 }}>
                  <button className="btn" onClick={() => removeRequiredRole(role.id)}>Remove Role</button>
                </div>
              </div>
            ))}
          </div>
        )}
        <button className="btn" style={{ marginTop: 10 }} onClick={() => addRequiredRole()}>
          Add Role
        </button>
      </section>

      <section className="estimation-form">
        <h2>Upwork Scout</h2>
        <div className="form-grid">
          <label>Search Query
            <input
              value={workspace.upwork.query}
              onChange={(e) => setWorkspace((prev) => ({ ...prev, upwork: { ...prev.upwork, query: e.target.value } }))}
              placeholder="cloud migration engineer"
            />
          </label>
        </div>
        <div style={{ marginTop: 8 }} className="subcontractor-note">
          Search URL: {searchUrl ? (
            <a href={searchUrl} target="_blank" rel="noreferrer">{searchUrl}</a>
          ) : (
            'Enter a query to generate an Upwork search URL.'
          )}
        </div>
        <div className="subcontractor-actions" style={{ marginTop: 10 }}>
          <button className="btn" onClick={applyQueryFromScope}>Build Query From Scope</button>
          <button className="btn" onClick={openUpworkSearch} disabled={!searchUrl}>Open Upwork Search</button>
          <button className="btn btn-primary" onClick={runScrape} disabled={scrapeLoading || !searchUrl}>
            {scrapeLoading ? 'Scraping...' : 'Scrape Upwork'}
          </button>
        </div>
        <div className="subcontractor-note" style={{ marginTop: 6 }}>
          Upwork pages are dynamic. If the scrape fails, open the search and paste highlights into the scratchpad.
        </div>
        {scrapeError && (
          <div style={{ marginTop: 8, color: 'crimson' }}>
            {scrapeError}
          </div>
        )}
        {workspace.upwork.lastScrape && (
          <div style={{ marginTop: 10 }}>
            <div className="subcontractor-note" style={{ marginBottom: 6 }}>
              Scrape status: {workspace.upwork.lastScrape.success ? 'OK' : 'Failed'}
              {workspace.upwork.lastScrape.status_code ? ` (${workspace.upwork.lastScrape.status_code})` : ''}
              {workspace.upwork.lastScrape.truncated ? ' - truncated' : ''}
            </div>
            <div className="subcontractor-excerpt">
              {workspace.upwork.lastScrape.text_excerpt || '(no text extracted)'}
            </div>
          </div>
        )}
        <div style={{ marginTop: 12 }}>
          <label>Lead Scratchpad
            <textarea
              value={scratchpad}
              onChange={(e) => setScratchpad(e.target.value)}
              rows={4}
              style={{ width: '100%', fontFamily: 'inherit' }}
              placeholder="Paste candidate names or snippets, one per line."
            />
          </label>
          <div className="subcontractor-actions" style={{ marginTop: 8 }}>
            <button
              className="btn"
              onClick={() => setScratchpad(workspace.upwork.lastScrape?.text_excerpt || '')}
              disabled={!workspace.upwork.lastScrape?.text_excerpt}
            >
              Use Scraped Excerpt
            </button>
            <button className="btn" onClick={addLeadsFromScratchpad} disabled={!scratchpad.trim()}>
              Create Leads From Lines
            </button>
            <button className="btn" onClick={() => setScratchpad('')} disabled={!scratchpad}>
              Clear Scratchpad
            </button>
          </div>
          <div className="subcontractor-note" style={{ marginTop: 6 }}>
            Each non-empty line becomes a new lead in the pipeline.
          </div>
        </div>
      </section>

      <section className="estimation-form">
        <h2>Subcontractor Pipeline</h2>
        {workspace.subcontractors.length === 0 ? (
          <div className="subcontractor-note">No subcontractors yet. Add leads or import a list.</div>
        ) : (
          <div className="subcontractor-stack">
            {workspace.subcontractors.map((sub) => (
              <div key={sub.id} className="subcontractor-card">
                <div className="form-grid">
                  <label>Name
                    <input value={sub.name} onChange={(e) => updateSubcontractor(sub.id, { name: e.target.value })} />
                  </label>
                  <label>Role
                    <input value={sub.role} onChange={(e) => updateSubcontractor(sub.id, { role: e.target.value })} />
                  </label>
                  <label>Skills
                    <input value={sub.skills} onChange={(e) => updateSubcontractor(sub.id, { skills: e.target.value })} />
                  </label>
                  <label>Rate
                    <input value={sub.rate} onChange={(e) => updateSubcontractor(sub.id, { rate: e.target.value })} />
                  </label>
                  <label>Availability
                    <input value={sub.availability} onChange={(e) => updateSubcontractor(sub.id, { availability: e.target.value })} />
                  </label>
                  <label>Location
                    <input value={sub.location} onChange={(e) => updateSubcontractor(sub.id, { location: e.target.value })} />
                  </label>
                  <label>Status
                    <select value={sub.status} onChange={(e) => updateSubcontractor(sub.id, { status: e.target.value as SubcontractorStatus })}>
                      {STATUS_OPTIONS.map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </label>
                  <label>Source
                    <select value={sub.source} onChange={(e) => updateSubcontractor(sub.id, { source: e.target.value as SubcontractorSource })}>
                      {SOURCE_OPTIONS.map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </label>
                  <label>Profile URL
                    <input value={sub.profileUrl} onChange={(e) => updateSubcontractor(sub.id, { profileUrl: e.target.value })} placeholder="https://..." />
                  </label>
                </div>
                <div style={{ marginTop: 8 }}>
                  <label>Notes
                    <textarea
                      value={sub.notes}
                      onChange={(e) => updateSubcontractor(sub.id, { notes: e.target.value })}
                      rows={2}
                      style={{ width: '100%', fontFamily: 'inherit' }}
                    />
                  </label>
                </div>
                <div className="subcontractor-actions" style={{ marginTop: 8 }}>
                  <button className="btn" onClick={() => removeSubcontractor(sub.id)}>Remove Lead</button>
                </div>
              </div>
            ))}
          </div>
        )}
        <button className="btn" style={{ marginTop: 10 }} onClick={() => addSubcontractor()}>
          Add Subcontractor
        </button>
      </section>
    </div>
  )
}
