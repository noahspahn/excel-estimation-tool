import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import './App.css'
import TopNav from './TopNav'

const rawApi = (import.meta as any).env?.VITE_API_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000')
const API = rawApi.replace(/\/+$/, '')
const AUTH_DISABLED = String((import.meta as any).env?.VITE_DISABLE_AUTH ?? 'false').toLowerCase() === 'true'

type VersionInfo = { id: string; version: number; title?: string; created_at?: string }
type PromptMap = Record<string, string>

const DEFAULT_SECTIONS = ['executive_summary', 'assumptions', 'risks']

const DEFAULT_RACI_ROWS = [
  { milestone: 'SIT sign-off', responsible: '', accountable: '', consulted: '', informed: '' },
  { milestone: 'UAT data validation', responsible: '', accountable: '', consulted: '', informed: '' },
  { milestone: 'Security policy review', responsible: '', accountable: '', consulted: '', informed: '' },
]

const DEFAULT_ROADMAP_PHASES = [
  {
    phase: 'Phase 1',
    title: 'Core modernization and stabilization',
    timeline: '0-18 months',
    description: 'Deliver the current scope modules as the foundational platform for modernization.',
  },
  {
    phase: 'Phase 2',
    title: 'Potential scalability',
    timeline: '18-36 months',
    description: 'Add future capabilities such as AI-driven predictive maintenance or automated compliance reporting.',
  },
  {
    phase: 'Phase 3',
    title: 'Long-term vision',
    timeline: '3-5 years',
    description: 'Enable secure, citizen-facing services leveraging the Phase 1 API and modular architecture.',
  },
]

const normalizeMap = (src: any): Record<string, any> => {
  if (Array.isArray(src)) {
    return src.reduce((acc, item, idx) => ({ ...acc, [String(idx)]: item }), {} as Record<string, any>)
  }
  return { ...(src || {}) }
}

const countModules = (payload: any) => {
  const fromInput = Array.isArray(payload?.estimation_input?.modules) ? payload.estimation_input.modules.length : 0
  if (fromInput > 0) return fromInput
  const mods = payload?.estimation_result?.breakdown_by_module
  if (Array.isArray(mods)) return mods.length
  if (mods && typeof mods === 'object') return Object.keys(mods).length
  return 0
}

const formatSectionTitle = (key: string) => key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export default function Preview() {
  const { id } = useParams()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [proposalId, setProposalId] = useState<string | null>(null)
  const [payload, setPayload] = useState<any | null>(null)
  const [baselinePayload, setBaselinePayload] = useState<any | null>(null)
  const [versions, setVersions] = useState<VersionInfo[]>([])
  const [fromVer, setFromVer] = useState<number | null>(null)
  const [toVer, setToVer] = useState<number | null>(null)
  const [diffs, setDiffs] = useState<any[] | null>(null)
  const [editMode, setEditMode] = useState(true)
  const [dirty, setDirty] = useState(false)
  const [rawPayload, setRawPayload] = useState('')
  const [moduleSubtasksText, setModuleSubtasksText] = useState('')
  const [aiBusy, setAiBusy] = useState<string | null>(null)
  const [aiError, setAiError] = useState<string | null>(null)
  const [sectionPrompts, setSectionPrompts] = useState<PromptMap>({})
  const [newSectionName, setNewSectionName] = useState('')
  const [newSectionPrompt, setNewSectionPrompt] = useState('')
  const [authToken, setAuthToken] = useState<string | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (token) setAuthToken(token)
  }, [])

  useEffect(() => {
    if (!id) return
    setLoading(true)
    fetch(`${API}/api/v1/proposals/public/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error('Not found')
        return res.json()
      })
      .then((data) => {
        const loaded = data?.payload || null
        setPayload(loaded)
        setBaselinePayload(loaded)
        setProposalId(data?.id || null)
        setRawPayload(JSON.stringify(loaded || {}, null, 2))
        setModuleSubtasksText(JSON.stringify(loaded?.module_subtasks || [], null, 2))
        const prompts: PromptMap = {}
        Object.keys(loaded?.narrative_sections || {}).forEach((k) => { prompts[k] = '' })
        setSectionPrompts(prompts)
        setDirty(false)
      })
      .catch((e) => setError(e?.message || 'Failed to load'))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!proposalId) return
    if (!AUTH_DISABLED && !authToken) return
    fetch(`${API}/api/v1/proposals/${proposalId}/versions`, {
      headers: !AUTH_DISABLED && authToken ? { Authorization: `Bearer ${authToken}` } : {},
    })
      .then((res) => res.json())
      .then((rows: VersionInfo[]) => {
        setVersions(rows || [])
        if (rows.length >= 2) {
          setFromVer(rows[rows.length - 2].version)
          setToVer(rows[rows.length - 1].version)
        } else if (rows.length === 1) {
          setFromVer(rows[0].version)
          setToVer(rows[0].version)
        }
      })
      .catch(() => {})
  }, [proposalId, authToken])

  useEffect(() => {
    setRawPayload(JSON.stringify(payload || {}, null, 2))
    setModuleSubtasksText(JSON.stringify(payload?.module_subtasks || [], null, 2))
  }, [payload])

  const runDiff = async () => {
    if (!proposalId || fromVer == null || toVer == null) return
    if (!AUTH_DISABLED && !authToken) return
    const res = await fetch(`${API}/api/v1/proposals/${proposalId}/diff?from_version=${fromVer}&to_version=${toVer}`, {
      headers: !AUTH_DISABLED && authToken ? { Authorization: `Bearer ${authToken}` } : {},
    })
    if (!res.ok) { setDiffs([]); return }
    const data = await res.json()
    setDiffs(data?.diffs || [])
  }

  const updateEstimationInput = (field: string, value: any) => {
    setPayload((prev: any) => ({
      ...(prev || {}),
      estimation_input: { ...(prev?.estimation_input || {}), [field]: value },
    }))
    setDirty(true)
  }

  const updateResultField = (field: string, value: any) => {
    setPayload((prev: any) => ({
      ...(prev || {}),
      estimation_result: { ...(prev?.estimation_result || {}), [field]: value },
    }))
    setDirty(true)
  }

  const updateModuleRow = (rowKey: string, patch: Record<string, any>) => {
    setPayload((prev: any) => {
      const next = { ...(prev || {}) }
      const result = { ...(next.estimation_result || {}) }
      const modules = normalizeMap(result.breakdown_by_module)
      modules[rowKey] = { ...(modules[rowKey] || {}), ...patch }
      result.breakdown_by_module = modules
      next.estimation_result = result
      return next
    })
    setDirty(true)
  }

  const removeModuleRow = (rowKey: string) => {
    setPayload((prev: any) => {
      const next = { ...(prev || {}) }
      const result = { ...(next.estimation_result || {}) }
      const modules = normalizeMap(result.breakdown_by_module)
      delete modules[rowKey]
      result.breakdown_by_module = modules
      next.estimation_result = result
      return next
    })
    setDirty(true)
  }

  const updateRoleRow = (rowKey: string, patch: Record<string, any>) => {
    setPayload((prev: any) => {
      const next = { ...(prev || {}) }
      const result = { ...(next.estimation_result || {}) }
      const roles = normalizeMap(result.breakdown_by_role)
      roles[rowKey] = { ...(roles[rowKey] || {}), ...patch }
      result.breakdown_by_role = roles
      next.estimation_result = result
      return next
    })
    setDirty(true)
  }

  const removeRoleRow = (rowKey: string) => {
    setPayload((prev: any) => {
      const next = { ...(prev || {}) }
      const result = { ...(next.estimation_result || {}) }
      const roles = normalizeMap(result.breakdown_by_role)
      delete roles[rowKey]
      result.breakdown_by_role = roles
      next.estimation_result = result
      return next
    })
    setDirty(true)
  }

  const updateListItem = (key: 'odc_items' | 'fixed_price_items', idx: number, patch: Record<string, any>) => {
    const list = Array.isArray(payload?.estimation_input?.[key]) ? [...payload.estimation_input[key]] : []
    list[idx] = { ...(list[idx] || {}), ...patch }
    updateEstimationInput(key, list)
  }

  const updateRaciRow = (idx: number, patch: Record<string, string>) => {
    const list = Array.isArray(payload?.estimation_input?.raci_matrix)
      ? [...payload.estimation_input.raci_matrix]
      : []
    list[idx] = { ...(list[idx] || {}), ...patch }
    updateEstimationInput('raci_matrix', list)
  }

  const addRaciRow = () => {
    const list = Array.isArray(payload?.estimation_input?.raci_matrix)
      ? [...payload.estimation_input.raci_matrix]
      : []
    list.push({ milestone: '', responsible: '', accountable: '', consulted: '', informed: '' })
    updateEstimationInput('raci_matrix', list)
  }

  const removeRaciRow = (idx: number) => {
    const list = Array.isArray(payload?.estimation_input?.raci_matrix)
      ? [...payload.estimation_input.raci_matrix]
      : []
    list.splice(idx, 1)
    updateEstimationInput('raci_matrix', list)
  }

  const updateRoadmapPhase = (idx: number, patch: Record<string, string>) => {
    const list = Array.isArray(payload?.estimation_input?.roadmap_phases)
      ? [...payload.estimation_input.roadmap_phases]
      : []
    list[idx] = { ...(list[idx] || {}), ...patch }
    updateEstimationInput('roadmap_phases', list)
  }

  const updateHistoricalEstimate = (idx: number, patch: Record<string, any>) => {
    const list = Array.isArray(payload?.estimation_input?.historical_estimates)
      ? [...payload.estimation_input.historical_estimates]
      : []
    list[idx] = { ...(list[idx] || {}), ...patch }
    updateEstimationInput('historical_estimates', list)
  }

  const addHistoricalEstimate = () => {
    const list = Array.isArray(payload?.estimation_input?.historical_estimates)
      ? [...payload.estimation_input.historical_estimates]
      : []
    list.push({ name: '', actual_hours: null, actual_total_cost: null, selected: true })
    updateEstimationInput('historical_estimates', list)
  }

  const removeHistoricalEstimate = (idx: number) => {
    const list = Array.isArray(payload?.estimation_input?.historical_estimates)
      ? [...payload.estimation_input.historical_estimates]
      : []
    list.splice(idx, 1)
    updateEstimationInput('historical_estimates', list)
  }

  const addListItem = (key: 'odc_items' | 'fixed_price_items') => {
    const list = Array.isArray(payload?.estimation_input?.[key]) ? [...payload.estimation_input[key]] : []
    list.push({ description: '', price: 0 })
    updateEstimationInput(key, list)
  }

  const removeListItem = (key: 'odc_items' | 'fixed_price_items', idx: number) => {
    const list = Array.isArray(payload?.estimation_input?.[key]) ? [...payload.estimation_input[key]] : []
    list.splice(idx, 1)
    updateEstimationInput(key, list)
  }

  const setSubtasks = (list: any[]) => {
    setPayload((prev: any) => ({ ...(prev || {}), module_subtasks: list }))
    setModuleSubtasksText(JSON.stringify(list || [], null, 2))
    setDirty(true)
  }

  const updateSubtask = (idx: number, patch: Record<string, any>) => {
    const list = Array.isArray(payload?.module_subtasks) ? [...payload.module_subtasks] : []
    list[idx] = { ...(list[idx] || {}), ...patch }
    setSubtasks(list)
  }

  const removeSubtask = (idx: number) => {
    const list = Array.isArray(payload?.module_subtasks) ? [...payload.module_subtasks] : []
    list.splice(idx, 1)
    setSubtasks(list)
  }

  const addSubtask = () => {
    const list = Array.isArray(payload?.module_subtasks) ? [...payload.module_subtasks] : []
    list.push({
      sequence: list.length + 1,
      module_name: 'New Module',
      focus_area: '',
      work_scope: '',
      estimate_basis: '',
      period_of_performance: '',
      reasonableness: '',
      customer_context: '',
      tasks: [],
      total_hours: 0,
    })
    setSubtasks(list)
  }

  const recalcTotalHours = (tasks: any[]) => tasks.reduce((sum, t) => sum + Number(t?.hours || 0), 0)

  const updateTask = (subIdx: number, taskIdx: number, patch: Record<string, any>) => {
    const list = Array.isArray(payload?.module_subtasks) ? [...payload.module_subtasks] : []
    if (!list[subIdx]) return
    const st = { ...(list[subIdx] || {}) }
    const tasks = Array.isArray(st.tasks) ? [...st.tasks] : []
    tasks[taskIdx] = { ...(tasks[taskIdx] || { title: '', calculation: '', hours: 0 }), ...patch }
    st.tasks = tasks
    st.total_hours = recalcTotalHours(tasks)
    list[subIdx] = st
    setSubtasks(list)
  }

  const addTask = (subIdx: number) => {
    const list = Array.isArray(payload?.module_subtasks) ? [...payload.module_subtasks] : []
    if (!list[subIdx]) return
    const st = { ...(list[subIdx] || {}) }
    const tasks = Array.isArray(st.tasks) ? [...st.tasks] : []
    tasks.push({ title: 'New Task', calculation: '', hours: 0 })
    st.tasks = tasks
    st.total_hours = recalcTotalHours(tasks)
    list[subIdx] = st
    setSubtasks(list)
  }

  const removeTask = (subIdx: number, taskIdx: number) => {
    const list = Array.isArray(payload?.module_subtasks) ? [...payload.module_subtasks] : []
    if (!list[subIdx]) return
    const st = { ...(list[subIdx] || {}) }
    const tasks = Array.isArray(st.tasks) ? [...st.tasks] : []
    tasks.splice(taskIdx, 1)
    st.tasks = tasks
    st.total_hours = recalcTotalHours(tasks)
    list[subIdx] = st
    setSubtasks(list)
  }

  const applyRawJson = () => {
    try {
      const parsed = JSON.parse(rawPayload || '{}')
      setPayload(parsed)
      setDirty(true)
      setAiError(null)
    } catch {
      setAiError('Invalid JSON in raw payload editor.')
    }
  }

  const applyModuleSubtasks = () => {
    try {
      const parsed = JSON.parse(moduleSubtasksText || '[]')
      setPayload((prev: any) => ({ ...(prev || {}), module_subtasks: parsed }))
      setDirty(true)
      setAiError(null)
    } catch {
      setAiError('Module subtasks must be valid JSON.')
    }
  }

  const resetEdits = () => {
    setPayload(baselinePayload)
    setRawPayload(JSON.stringify(baselinePayload || {}, null, 2))
    setModuleSubtasksText(JSON.stringify(baselinePayload?.module_subtasks || [], null, 2))
    const prompts: PromptMap = {}
    Object.keys(baselinePayload?.narrative_sections || {}).forEach((k) => { prompts[k] = '' })
    setSectionPrompts(prompts)
    setDirty(false)
    setAiError(null)
  }

  const handleNarrativeChange = (key: string, value: string) => {
    setPayload((prev: any) => ({
      ...(prev || {}),
      narrative_sections: { ...(prev?.narrative_sections || {}), [key]: value },
    }))
    setDirty(true)
  }

  const addNarrativeSection = (key: string) => {
    if (!key) return
    handleNarrativeChange(key, '')
    setSectionPrompts((prev) => ({ ...prev, [key]: '' }))
  }

  const rewriteSection = async (sectionKey: string, promptOverride?: string) => {
    if (!payload) return
    setAiError(null)
    setAiBusy(sectionKey)
    try {
      const moduleCount = countModules(payload)
      const res = await fetch(`${API}/api/v1/narrative/section`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          section: sectionKey,
          prompt: promptOverride ?? sectionPrompts[sectionKey] ?? '',
          current_text: (payload.narrative_sections || {})[sectionKey] || '',
          tone: payload.tone || 'professional',
          estimation_data: payload,
          input_summary: {
            complexity: payload.estimation_input?.complexity,
            module_count: moduleCount,
          },
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.detail || 'Failed to generate text for this section.')
      }
      const data = await res.json()
      const text = typeof data?.text === 'string' ? data.text : data?.[sectionKey]
      if (!text) throw new Error('No text returned from AI.')
      handleNarrativeChange(sectionKey, text)
    } catch (e: any) {
      setAiError(e?.message || 'Unable to update section.')
    } finally {
      setAiBusy(null)
    }
  }

  const generateNewSection = async () => {
    const key = newSectionName.trim().toLowerCase().replace(/\s+/g, '_')
    if (!key) return
    addNarrativeSection(key)
    await rewriteSection(key, newSectionPrompt || undefined)
    setNewSectionName('')
    setNewSectionPrompt('')
  }

  const downloadPayload = () => {
    if (!payload) return
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'proposal_payload.json'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  if (loading) return <div className="app preview-status">Loading...</div>
  if (error) return <div className="app preview-status preview-error">{error}</div>
  if (!payload) return <div className="app preview-status">No data</div>

  const est = payload.estimation_result || {}
  const narr = payload.narrative_sections || {}
  const ei = payload.estimation_input || {}
  const modules = normalizeMap(est.breakdown_by_module)
  const roles = normalizeMap(est.breakdown_by_role)
  const moduleSubtasks = Array.isArray(payload?.module_subtasks) ? payload.module_subtasks : []
  const narrativeKeys = Object.keys(narr).length > 0 ? Object.keys(narr) : DEFAULT_SECTIONS
  const raciRows = Array.isArray(ei.raci_matrix) && ei.raci_matrix.length ? ei.raci_matrix : DEFAULT_RACI_ROWS
  const roadmapRows = Array.isArray(ei.roadmap_phases) && ei.roadmap_phases.length ? ei.roadmap_phases : DEFAULT_ROADMAP_PHASES
  const historicalRows = Array.isArray(ei.historical_estimates) ? ei.historical_estimates : []

  return (
    <div className="app preview-page">
      <TopNav />
      <div style={{ marginBottom: 12, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
          <input type="checkbox" checked={editMode} onChange={(e) => setEditMode(e.target.checked)} />
          Enable editing
        </label>
        {dirty && <span style={{ fontSize: 12, color: '#b26a00' }}>Unsaved changes in preview</span>}
        <button className="btn" onClick={resetEdits} disabled={!baselinePayload}>Reset to loaded</button>
        <button className="btn" onClick={downloadPayload}>Download JSON</button>
      </div>

      <h1>Proposal Preview</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8 }}>
        <div><strong>Project:</strong> {ei.project_name || '-'}</div>
        <div><strong>POC:</strong> {ei.government_poc || '-'}</div>
        <div><strong>FY:</strong> {ei.fy || '-'}</div>
        <div><strong>Site Location:</strong> {ei.site_location || '-'}</div>
        <div><strong>Complexity:</strong> {ei.complexity || 'M'}</div>
        <div><strong>Modules:</strong> {countModules(payload)}</div>
        <div><strong>Sites:</strong> {ei.sites || 1}</div>
      </div>

      <h2 style={{ marginTop: 16 }}>Project & Scope</h2>
      <div className="form-grid">
        <label>Project Name
          <input value={ei.project_name || ''} onChange={(e) => updateEstimationInput('project_name', e.target.value)} disabled={!editMode} />
        </label>
        <label>Government POC
          <input value={ei.government_poc || ''} onChange={(e) => updateEstimationInput('government_poc', e.target.value)} disabled={!editMode} />
        </label>
        <label>Account Manager
          <input value={ei.account_manager || ''} onChange={(e) => updateEstimationInput('account_manager', e.target.value)} disabled={!editMode} />
        </label>
        <label>Service Delivery Mgr
          <input value={ei.service_delivery_mgr || ''} onChange={(e) => updateEstimationInput('service_delivery_mgr', e.target.value)} disabled={!editMode} />
        </label>
        <label>Service Delivery Exec
          <input value={ei.service_delivery_exec || ''} onChange={(e) => updateEstimationInput('service_delivery_exec', e.target.value)} disabled={!editMode} />
        </label>
        <label>Site Location
          <input value={ei.site_location || ''} onChange={(e) => updateEstimationInput('site_location', e.target.value)} disabled={!editMode} />
        </label>
        <label>Fiscal Year
          <input value={ei.fy || ''} onChange={(e) => updateEstimationInput('fy', e.target.value)} disabled={!editMode} />
        </label>
        <label>Email
          <input value={ei.email || ''} onChange={(e) => updateEstimationInput('email', e.target.value)} disabled={!editMode} />
        </label>
        <label>RAP #
          <input value={ei.rap_number || ''} onChange={(e) => updateEstimationInput('rap_number', e.target.value)} disabled={!editMode} />
        </label>
        <label>PSI Code
          <input value={ei.psi_code || ''} onChange={(e) => updateEstimationInput('psi_code', e.target.value)} disabled={!editMode} />
        </label>
      </div>
      <div style={{ marginTop: 8 }}>
        <label>Additional Comments
          <textarea value={ei.additional_comments || ''} onChange={(e) => updateEstimationInput('additional_comments', e.target.value)} rows={2} style={{ width: '100%' }} disabled={!editMode} />
        </label>
      </div>

      <h2 style={{ marginTop: 16 }}>Value & ROI Inputs</h2>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
        Inputs that drive the 5-year net fiscal benefit summary.
      </div>
      <div className="form-grid">
        <label>Emergency CapEx Event Cost (Low)
          <input
            type="number"
            value={ei.roi_capex_event_cost_low ?? ''}
            onChange={(e) => updateEstimationInput('roi_capex_event_cost_low', e.target.value === '' ? null : Number(e.target.value))}
            disabled={!editMode}
          />
        </label>
        <label>Emergency CapEx Event Cost (High)
          <input
            type="number"
            value={ei.roi_capex_event_cost_high ?? ''}
            onChange={(e) => updateEstimationInput('roi_capex_event_cost_high', e.target.value === '' ? null : Number(e.target.value))}
            disabled={!editMode}
          />
        </label>
        <label>CapEx Event Interval (Months)
          <input
            type="number"
            value={ei.roi_capex_event_interval_months ?? ''}
            onChange={(e) => updateEstimationInput('roi_capex_event_interval_months', e.target.value === '' ? null : Number(e.target.value))}
            disabled={!editMode}
          />
        </label>
        <label>Downtime Cost per Hour
          <input
            type="number"
            value={ei.roi_downtime_cost_per_hour ?? ''}
            onChange={(e) => updateEstimationInput('roi_downtime_cost_per_hour', e.target.value === '' ? null : Number(e.target.value))}
            disabled={!editMode}
          />
        </label>
        <label>Current Availability (%)
          <input
            type="number"
            value={ei.roi_current_availability ?? ''}
            onChange={(e) => updateEstimationInput('roi_current_availability', e.target.value === '' ? null : Number(e.target.value))}
            disabled={!editMode}
          />
        </label>
        <label>Target Availability (%)
          <input
            type="number"
            value={ei.roi_target_availability ?? ''}
            onChange={(e) => updateEstimationInput('roi_target_availability', e.target.value === '' ? null : Number(e.target.value))}
            disabled={!editMode}
          />
        </label>
        <label>Legacy Support Savings (Annual)
          <input
            type="number"
            value={ei.roi_legacy_support_savings_annual ?? ''}
            onChange={(e) => updateEstimationInput('roi_legacy_support_savings_annual', e.target.value === '' ? null : Number(e.target.value))}
            disabled={!editMode}
          />
        </label>
      </div>

      <h2 style={{ marginTop: 16 }}>Roles & Responsibilities (RACI)</h2>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
        This appendix will be included in the report and should be treated as a binding contract artifact.
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Milestone</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Responsible</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Accountable</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Consulted</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Informed</th>
              {editMode && <th style={{ width: 1 }} />}
            </tr>
          </thead>
          <tbody>
            {raciRows.map((row: any, idx: number) => (
              <tr key={idx}>
                <td style={{ padding: 6 }}>
                  <input value={row.milestone || ''} onChange={(e) => updateRaciRow(idx, { milestone: e.target.value })} disabled={!editMode} />
                </td>
                <td style={{ padding: 6 }}>
                  <input value={row.responsible || ''} onChange={(e) => updateRaciRow(idx, { responsible: e.target.value })} disabled={!editMode} />
                </td>
                <td style={{ padding: 6 }}>
                  <input value={row.accountable || ''} onChange={(e) => updateRaciRow(idx, { accountable: e.target.value })} disabled={!editMode} />
                </td>
                <td style={{ padding: 6 }}>
                  <input value={row.consulted || ''} onChange={(e) => updateRaciRow(idx, { consulted: e.target.value })} disabled={!editMode} />
                </td>
                <td style={{ padding: 6 }}>
                  <input value={row.informed || ''} onChange={(e) => updateRaciRow(idx, { informed: e.target.value })} disabled={!editMode} />
                </td>
                {editMode && (
                  <td style={{ padding: 6 }}>
                    <button className="btn" onClick={() => removeRaciRow(idx)}>Remove</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editMode && (
        <button className="btn" style={{ marginTop: 8 }} onClick={addRaciRow}>
          Add RACI Row
        </button>
      )}

      <h2 style={{ marginTop: 16 }}>Future-Proofing Roadmap</h2>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
        Define phased implementation aligned to the 5-10 year strategy.
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {roadmapRows.map((phase: any, idx: number) => (
          <div key={idx} style={{ border: '1px solid #eee', borderRadius: 8, padding: 10, background: '#fafafa' }}>
            <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
              <label>Phase
                <input value={phase.phase || ''} onChange={(e) => updateRoadmapPhase(idx, { phase: e.target.value })} disabled={!editMode} />
              </label>
              <label>Timeline
                <input value={phase.timeline || ''} onChange={(e) => updateRoadmapPhase(idx, { timeline: e.target.value })} disabled={!editMode} />
              </label>
              <label>Title
                <input value={phase.title || ''} onChange={(e) => updateRoadmapPhase(idx, { title: e.target.value })} disabled={!editMode} />
              </label>
            </div>
            <label style={{ marginTop: 8, display: 'block' }}>Description
              <textarea value={phase.description || ''} onChange={(e) => updateRoadmapPhase(idx, { description: e.target.value })} rows={2} style={{ width: '100%' }} disabled={!editMode} />
            </label>
          </div>
        ))}
      </div>

      <h2 style={{ marginTop: 16 }}>Scope Options</h2>
      <div className="form-grid">
        <label>Modules (comma separated)
          <input
            value={Array.isArray(ei.modules) ? ei.modules.join(', ') : ''}
            onChange={(e) => updateEstimationInput('modules', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
            disabled={!editMode}
          />
        </label>
        <label>Complexity
          <select value={ei.complexity || 'M'} onChange={(e) => updateEstimationInput('complexity', e.target.value)} disabled={!editMode}>
            <option value="S">S</option>
            <option value="M">M</option>
            <option value="L">L</option>
            <option value="XL">XL</option>
          </select>
        </label>
        <label>Sites
          <input type="number" min={1} value={ei.sites || 1} onChange={(e) => updateEstimationInput('sites', Number(e.target.value || 1))} disabled={!editMode} />
        </label>
        <label>Period of Performance
          <input value={ei.period_of_performance || ''} onChange={(e) => updateEstimationInput('period_of_performance', e.target.value)} disabled={!editMode} />
        </label>
        <label>Estimating Method
          <select value={ei.estimating_method || 'engineering'} onChange={(e) => updateEstimationInput('estimating_method', e.target.value)} disabled={!editMode}>
            <option value="engineering">Engineering Discrete</option>
            <option value="historical">Historical Actuals</option>
          </select>
        </label>
        <label>
          <input type="checkbox" checked={!!ei.overtime} onChange={(e) => updateEstimationInput('overtime', e.target.checked)} disabled={!editMode} style={{ marginRight: 8 }} />
          Overtime
        </label>
        <label>Environment
          <input value={ei.environment || ''} onChange={(e) => updateEstimationInput('environment', e.target.value)} disabled={!editMode} />
        </label>
        <label>Integration Level
          <input value={ei.integration_level || ''} onChange={(e) => updateEstimationInput('integration_level', e.target.value)} disabled={!editMode} />
        </label>
        <label>Geography
          <input value={ei.geography || ''} onChange={(e) => updateEstimationInput('geography', e.target.value)} disabled={!editMode} />
        </label>
        <label>Clearance Level
          <input value={ei.clearance_level || ''} onChange={(e) => updateEstimationInput('clearance_level', e.target.value)} disabled={!editMode} />
        </label>
      </div>
      {String(ei.estimating_method || 'engineering').toLowerCase() === 'historical' && (
        <div style={{ marginTop: 8 }}>
          <h4>Historical Actuals</h4>
          {historicalRows.length > 0 ? (
            historicalRows.map((item: any, idx: number) => (
              <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <input
                    type="checkbox"
                    checked={item?.selected !== false}
                    onChange={(e) => updateHistoricalEstimate(idx, { selected: e.target.checked })}
                    disabled={!editMode}
                  />
                  Use
                </label>
                <input
                  placeholder="Historical win name"
                  value={item?.name || ''}
                  onChange={(e) => updateHistoricalEstimate(idx, { name: e.target.value })}
                  disabled={!editMode}
                  style={{ minWidth: 200, flex: 1 }}
                />
                <input
                  type="number"
                  placeholder="Actual Hours"
                  value={item?.actual_hours ?? ''}
                  onChange={(e) => updateHistoricalEstimate(idx, { actual_hours: e.target.value === '' ? null : Number(e.target.value) })}
                  disabled={!editMode}
                  style={{ width: 140 }}
                />
                <input
                  type="number"
                  placeholder="Actual Total Cost"
                  value={item?.actual_total_cost ?? ''}
                  onChange={(e) => updateHistoricalEstimate(idx, { actual_total_cost: e.target.value === '' ? null : Number(e.target.value) })}
                  disabled={!editMode}
                  style={{ width: 160 }}
                />
                {editMode && (
                  <button className="btn" onClick={() => removeHistoricalEstimate(idx)}>Remove</button>
                )}
              </div>
            ))
          ) : (
            <div style={{ fontSize: 12, color: '#666' }}>No historical wins added yet.</div>
          )}
          {editMode && <button className="btn" onClick={addHistoricalEstimate}>Add Historical Win</button>}
        </div>
      )}

      <h2 style={{ marginTop: 16 }}>Financial Summary (editable)</h2>
      <div className="form-grid">
        <label>Total Labor Hours
          <input type="number" value={est.total_labor_hours ?? 0} onChange={(e) => updateResultField('total_labor_hours', Number(e.target.value || 0))} disabled={!editMode} />
        </label>
        <label>Total Labor Cost
          <input type="number" value={est.total_labor_cost ?? 0} onChange={(e) => updateResultField('total_labor_cost', Number(e.target.value || 0))} disabled={!editMode} />
        </label>
        <label>Management Reserve
          <input type="number" value={est.risk_reserve ?? 0} onChange={(e) => updateResultField('risk_reserve', Number(e.target.value || 0))} disabled={!editMode} />
        </label>
        <label>Overhead Cost
          <input type="number" value={est.overhead_cost ?? 0} onChange={(e) => updateResultField('overhead_cost', Number(e.target.value || 0))} disabled={!editMode} />
        </label>
        <label>Total Cost
          <input type="number" value={est.total_cost ?? 0} onChange={(e) => updateResultField('total_cost', Number(e.target.value || 0))} disabled={!editMode} />
        </label>
        <label>Effective Hourly Rate
          <input type="number" value={est.effective_hourly_rate ?? 0} onChange={(e) => updateResultField('effective_hourly_rate', Number(e.target.value || 0))} disabled={!editMode} />
        </label>
      </div>

      <h2 style={{ marginTop: 16 }}>Other Costs</h2>
      <div className="form-grid">
        <label>Hardware Subtotal
          <input type="number" value={ei.hardware_subtotal ?? 0} onChange={(e) => updateEstimationInput('hardware_subtotal', Number(e.target.value || 0))} disabled={!editMode} />
        </label>
        <label>Warranty Months
          <input type="number" value={ei.warranty_months ?? 0} onChange={(e) => updateEstimationInput('warranty_months', Number(e.target.value || 0))} disabled={!editMode} />
        </label>
        <label>Warranty Cost
          <input type="number" value={ei.warranty_cost ?? 0} onChange={(e) => updateEstimationInput('warranty_cost', Number(e.target.value || 0))} disabled={!editMode} />
        </label>
      </div>
      <div style={{ marginTop: 8 }}>
        <h4>Other Direct Costs</h4>
        {Array.isArray(ei.odc_items) && ei.odc_items.length > 0 ? (
          ei.odc_items.map((item: any, idx: number) => (
            <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
              <input placeholder="Description" value={item.description || ''} onChange={(e) => updateListItem('odc_items', idx, { description: e.target.value })} disabled={!editMode} />
              <input placeholder="Price" type="number" value={item.price || 0} onChange={(e) => updateListItem('odc_items', idx, { price: Number(e.target.value || 0) })} disabled={!editMode} />
              {editMode && <button className="btn" onClick={() => removeListItem('odc_items', idx)}>Remove</button>}
            </div>
          ))
        ) : (
          <div style={{ fontSize: 12, color: '#666' }}>No ODC items yet.</div>
        )}
        {editMode && <button className="btn" onClick={() => addListItem('odc_items')}>Add ODC Item</button>}
      </div>
      <div style={{ marginTop: 8 }}>
        <h4>Fixed Price Items</h4>
        {Array.isArray(ei.fixed_price_items) && ei.fixed_price_items.length > 0 ? (
          ei.fixed_price_items.map((item: any, idx: number) => (
            <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
              <input placeholder="Description" value={item.description || ''} onChange={(e) => updateListItem('fixed_price_items', idx, { description: e.target.value })} disabled={!editMode} />
              <input placeholder="Price" type="number" value={item.price || 0} onChange={(e) => updateListItem('fixed_price_items', idx, { price: Number(e.target.value || 0) })} disabled={!editMode} />
              {editMode && <button className="btn" onClick={() => removeListItem('fixed_price_items', idx)}>Remove</button>}
            </div>
          ))
        ) : (
          <div style={{ fontSize: 12, color: '#666' }}>No fixed-price items yet.</div>
        )}
        {editMode && <button className="btn" onClick={() => addListItem('fixed_price_items')}>Add Fixed-Price Item</button>}
      </div>

      <h2 style={{ marginTop: 16 }}>Module Breakdown</h2>
      {Object.keys(modules).length > 0 ? (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Key</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Module</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Focus</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Hours</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Cost</th>
              {editMode && <th style={{ width: 1 }} />}
            </tr>
          </thead>
          <tbody>
            {Object.entries(modules).map(([k, m]) => (
              <tr key={k}>
                <td style={{ padding: 6 }}>{k}</td>
                <td style={{ padding: 6 }}>
                  <input value={m.module_name || ''} onChange={(e) => updateModuleRow(k, { module_name: e.target.value })} disabled={!editMode} />
                </td>
                <td style={{ padding: 6 }}>
                  <input value={m.focus_area || ''} onChange={(e) => updateModuleRow(k, { focus_area: e.target.value })} disabled={!editMode} />
                </td>
                <td style={{ padding: 6, textAlign: 'right' }}>
                  <input type="number" value={m.hours ?? 0} onChange={(e) => updateModuleRow(k, { hours: Number(e.target.value || 0) })} disabled={!editMode} style={{ width: 100 }} />
                </td>
                <td style={{ padding: 6, textAlign: 'right' }}>
                  <input type="number" value={m.cost ?? 0} onChange={(e) => updateModuleRow(k, { cost: Number(e.target.value || 0) })} disabled={!editMode} style={{ width: 120 }} />
                </td>
                {editMode && (
                  <td style={{ padding: 6 }}>
                    <button className="btn" onClick={() => removeModuleRow(k)}>Remove</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div style={{ fontSize: 12, color: '#666' }}>No module breakdown available.</div>
      )}
      {editMode && (
        <button className="btn" style={{ marginTop: 8 }} onClick={() => updateModuleRow(`module_${Date.now()}`, { module_name: 'New Module', focus_area: '', hours: 0, cost: 0 })}>
          Add Module Row
        </button>
      )}

      <h2 style={{ marginTop: 16 }}>Resource Breakdown</h2>
      {Object.keys(roles).length > 0 ? (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Key</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Role</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Hours</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Rate</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Cost</th>
              {editMode && <th style={{ width: 1 }} />}
            </tr>
          </thead>
          <tbody>
            {Object.entries(roles).map(([k, r]) => (
              <tr key={k}>
                <td style={{ padding: 6 }}>{k}</td>
                <td style={{ padding: 6 }}>
                  <input value={r.role_name || ''} onChange={(e) => updateRoleRow(k, { role_name: e.target.value })} disabled={!editMode} />
                </td>
                <td style={{ padding: 6, textAlign: 'right' }}>
                  <input type="number" value={r.hours ?? 0} onChange={(e) => updateRoleRow(k, { hours: Number(e.target.value || 0) })} disabled={!editMode} style={{ width: 100 }} />
                </td>
                <td style={{ padding: 6, textAlign: 'right' }}>
                  <input type="number" value={r.effective_rate ?? 0} onChange={(e) => updateRoleRow(k, { effective_rate: Number(e.target.value || 0) })} disabled={!editMode} style={{ width: 120 }} />
                </td>
                <td style={{ padding: 6, textAlign: 'right' }}>
                  <input type="number" value={r.cost ?? 0} onChange={(e) => updateRoleRow(k, { cost: Number(e.target.value || 0) })} disabled={!editMode} style={{ width: 120 }} />
                </td>
                {editMode && (
                  <td style={{ padding: 6 }}>
                    <button className="btn" onClick={() => removeRoleRow(k)}>Remove</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div style={{ fontSize: 12, color: '#666' }}>No resource breakdown available.</div>
      )}
      {editMode && (
        <button className="btn" style={{ marginTop: 8 }} onClick={() => updateRoleRow(`role_${Date.now()}`, { role_name: 'New Role', hours: 0, effective_rate: 0, cost: 0 })}>
          Add Role Row
        </button>
      )}

      <h2 style={{ marginTop: 16 }}>Module Subtasks</h2>
      {moduleSubtasks.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {moduleSubtasks.map((st: any, idx: number) => (
            <div key={idx} style={{ border: '1px solid #ddd', borderRadius: 6, padding: 10, background: '#fafafa' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ fontWeight: 600 }}>
                  {(st.sequence ?? idx + 1)}. {st.module_name || 'Module'} {st.focus_area ? `(${st.focus_area})` : ''}
                </div>
                {editMode && (
                  <button className="btn" onClick={() => removeSubtask(idx)}>Remove</button>
                )}
              </div>
              <div className="form-grid" style={{ marginTop: 8 }}>
                <label>Module Name
                  <input value={st.module_name || ''} onChange={(e) => updateSubtask(idx, { module_name: e.target.value })} />
                </label>
                <label>Focus Area
                  <input value={st.focus_area || ''} onChange={(e) => updateSubtask(idx, { focus_area: e.target.value })} />
                </label>
                <label>Sequence
                  <input type="number" value={st.sequence ?? idx + 1} onChange={(e) => updateSubtask(idx, { sequence: Number(e.target.value || idx + 1) })} />
                </label>
                <label>Total Hours
                  <input type="number" value={st.total_hours ?? 0} onChange={(e) => updateSubtask(idx, { total_hours: Number(e.target.value || 0) })} />
                </label>
                <label>Period of Performance
                  <input value={st.period_of_performance || ''} onChange={(e) => updateSubtask(idx, { period_of_performance: e.target.value })} />
                </label>
                <label>Reasonableness
                  <input value={st.reasonableness || ''} onChange={(e) => updateSubtask(idx, { reasonableness: e.target.value })} />
                </label>
              </div>
              <div style={{ marginTop: 8 }}>
                <label style={{ display: 'block', fontWeight: 600 }}>Work Scope</label>
                <textarea
                  value={st.work_scope || ''}
                  onChange={(e) => updateSubtask(idx, { work_scope: e.target.value })}
                  rows={3}
                  style={{ width: '100%', fontFamily: 'inherit' }}
                  placeholder="Describe the work scope..."
                />
              </div>
              <div style={{ marginTop: 8 }}>
                <label style={{ display: 'block', fontWeight: 600 }}>Estimate Basis</label>
                <textarea
                  value={st.estimate_basis || ''}
                  onChange={(e) => updateSubtask(idx, { estimate_basis: e.target.value })}
                  rows={2}
                  style={{ width: '100%', fontFamily: 'inherit' }}
                  placeholder="Basis of estimate..."
                />
              </div>
              <div style={{ marginTop: 8 }}>
                <label style={{ display: 'block', fontWeight: 600 }}>Customer Context</label>
                <textarea
                  value={st.customer_context || ''}
                  onChange={(e) => updateSubtask(idx, { customer_context: e.target.value })}
                  rows={2}
                  style={{ width: '100%', fontFamily: 'inherit' }}
                  placeholder="Context to weave into tasks..."
                />
              </div>
              <div style={{ marginTop: 10 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Tasks</div>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Title</th>
                      <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Calc</th>
                      <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 4 }}>Hours</th>
                      {editMode && <th style={{ width: 1 }} />}
                    </tr>
                  </thead>
                  <tbody>
                    {(st.tasks || []).map((t: any, tIdx: number) => (
                      <tr key={tIdx}>
                        <td style={{ padding: 4 }}>
                          <input value={t.title || ''} onChange={(e) => updateTask(idx, tIdx, { title: e.target.value })} />
                        </td>
                        <td style={{ padding: 4 }}>
                          <input value={t.calculation || ''} onChange={(e) => updateTask(idx, tIdx, { calculation: e.target.value })} />
                        </td>
                        <td style={{ padding: 4, textAlign: 'right' }}>
                          <input type="number" value={t.hours ?? 0} onChange={(e) => updateTask(idx, tIdx, { hours: Number(e.target.value || 0) })} style={{ width: 100 }} />
                        </td>
                        {editMode && (
                          <td style={{ padding: 4 }}>
                            <button className="btn" onClick={() => removeTask(idx, tIdx)}>Remove</button>
                          </td>
                        )}
                      </tr>
                    ))}
                    <tr>
                      <td style={{ padding: 4, fontWeight: 600 }}>Subtask Total</td>
                      <td />
                      <td style={{ padding: 4, textAlign: 'right', fontWeight: 600 }}>{Number(st.total_hours || 0).toFixed(1)}</td>
                      {editMode && <td />}
                    </tr>
                  </tbody>
                </table>
                {editMode && <button className="btn" style={{ marginTop: 6 }} onClick={() => addTask(idx)}>Add Task</button>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: '#666' }}>No subtasks yet.</div>
      )}
      {editMode && (
        <button className="btn" style={{ marginTop: 8 }} onClick={addSubtask}>
          Add Subtask
        </button>
      )}

      <h3 style={{ marginTop: 12 }}>Raw Subtasks JSON</h3>
      <p style={{ fontSize: 12, color: '#555', marginTop: 0 }}>Paste JSON to replace the structured subtasks above.</p>
      <textarea
        rows={8}
        value={moduleSubtasksText}
        onChange={(e) => setModuleSubtasksText(e.target.value)}
        style={{ width: '100%', fontFamily: 'monospace', fontSize: 12 }}
        disabled={!editMode}
      />
      {editMode && <button className="btn" style={{ marginTop: 8 }} onClick={applyModuleSubtasks}>Apply Subtasks JSON</button>}

      <h2 style={{ marginTop: 16 }}>Narrative & Prompts</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
        <label>Tone
          <input value={payload.tone || 'professional'} onChange={(e) => { setPayload((prev: any) => ({ ...(prev || {}), tone: e.target.value })); setDirty(true) }} style={{ marginLeft: 8 }} />
        </label>
        {aiError && <span style={{ color: 'crimson', fontSize: 12 }}>{aiError}</span>}
      </div>
      {narrativeKeys.map((k) => (
        <div key={k} style={{ marginBottom: 16, border: '1px solid #ddd', borderRadius: 6, padding: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <strong>{formatSectionTitle(k)}</strong>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                placeholder="Prompt for this section (optional)"
                value={sectionPrompts[k] || ''}
                onChange={(e) => setSectionPrompts((prev) => ({ ...prev, [k]: e.target.value }))}
                style={{ minWidth: 200 }}
              />
              <button className="btn" onClick={() => rewriteSection(k)} disabled={aiBusy === k}>
                {aiBusy === k ? 'Rewriting...' : 'Rewrite with prompt'}
              </button>
            </div>
          </div>
          <textarea
            value={narr[k] || ''}
            onChange={(e) => handleNarrativeChange(k, e.target.value)}
            rows={4}
            style={{ width: '100%', marginTop: 8, fontFamily: 'inherit' }}
            placeholder={`Write ${formatSectionTitle(k)}...`}
          />
          <div style={{ textAlign: 'right', fontSize: 12, color: '#666' }}>{(narr[k] || '').trim().split(/\s+/).filter(Boolean).length} words</div>
        </div>
      ))}
      {editMode && (
        <div style={{ marginBottom: 16, border: '1px solid #eee', borderRadius: 6, padding: 10 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Add new section / blurb</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input placeholder="Section key (e.g., highlights)" value={newSectionName} onChange={(e) => setNewSectionName(e.target.value)} />
            <input placeholder="Prompt to guide the new blurb" value={newSectionPrompt} onChange={(e) => setNewSectionPrompt(e.target.value)} style={{ flex: 1, minWidth: 220 }} />
            <button className="btn" onClick={generateNewSection} disabled={aiBusy === 'new'}>Generate</button>
            <button className="btn" onClick={() => addNarrativeSection(newSectionName.trim().toLowerCase().replace(/\s+/g, '_'))}>Add empty</button>
          </div>
        </div>
      )}

      <h2 style={{ marginTop: 16 }}>Raw Payload (advanced)</h2>
      <textarea
        rows={8}
        value={rawPayload}
        onChange={(e) => setRawPayload(e.target.value)}
        style={{ width: '100%', fontFamily: 'monospace', fontSize: 12 }}
        disabled={!editMode}
      />
      {editMode && <button className="btn" style={{ marginTop: 8 }} onClick={applyRawJson}>Apply Raw JSON</button>}

      {proposalId && (
        <div style={{ marginTop: 24 }}>
          <h2>Versions</h2>
          {versions.length === 0 ? (
            <div>No versions available.</div>
          ) : (
            <div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <label>From
                  <select value={fromVer ?? ''} onChange={(e) => setFromVer(Number(e.target.value))} style={{ marginLeft: 6 }}>
                    {versions.map((v) => <option key={v.id} value={v.version}>{v.version} {v.title ? `- ${v.title}` : ''}</option>)}
                  </select>
                </label>
                <label>To
                  <select value={toVer ?? ''} onChange={(e) => setToVer(Number(e.target.value))} style={{ marginLeft: 6 }}>
                    {versions.map((v) => <option key={v.id} value={v.version}>{v.version} {v.title ? `- ${v.title}` : ''}</option>)}
                  </select>
                </label>
                <button className="btn" onClick={runDiff}>Compare</button>
              </div>

              {diffs && (
                <div style={{ marginTop: 12 }}>
                  <h3>Differences</h3>
                  {diffs.length === 0 ? (
                    <div>No differences</div>
                  ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr>
                          <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Path</th>
                          <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>From</th>
                          <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>To</th>
                          <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Change</th>
                        </tr>
                      </thead>
                      <tbody>
                        {diffs.map((d, i) => (
                          <tr key={i}>
                            <td style={{ padding: 6, verticalAlign: 'top' }}>{d.path}</td>
                            <td style={{ padding: 6, verticalAlign: 'top' }}>{formatVal(d.left)}</td>
                            <td style={{ padding: 6, verticalAlign: 'top' }}>{formatVal(d.right)}</td>
                            <td style={{ padding: 6, verticalAlign: 'top' }}>{d.change}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function formatVal(v: any) {
  if (v == null) return '-'
  if (typeof v === 'string') return v
  try { return JSON.stringify(v) } catch { return String(v) }
}
