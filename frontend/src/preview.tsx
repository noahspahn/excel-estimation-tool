import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'

const API = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000'

type VersionInfo = { id: string; version: number; title?: string; created_at?: string }

export default function Preview() {
  const { id } = useParams()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [proposalId, setProposalId] = useState<string | null>(null)
  const [payload, setPayload] = useState<any | null>(null)
  const [versions, setVersions] = useState<VersionInfo[]>([])
  const [fromVer, setFromVer] = useState<number | null>(null)
  const [toVer, setToVer] = useState<number | null>(null)
  const [diffs, setDiffs] = useState<any[] | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    fetch(`${API}/api/v1/proposals/public/${id}`)
      .then(res => {
        if (!res.ok) throw new Error('Not found')
        return res.json()
      })
      .then(data => {
        setPayload(data?.payload || null)
        setProposalId(data?.id || null)
      })
      .catch(e => setError(e?.message || 'Failed to load'))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!proposalId) return
    fetch(`${API}/api/v1/proposals/${proposalId}/versions`)
      .then(res => res.json())
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
  }, [proposalId])

  const runDiff = async () => {
    if (!proposalId || fromVer == null || toVer == null) return
    const res = await fetch(`${API}/api/v1/proposals/${proposalId}/diff?from_version=${fromVer}&to_version=${toVer}`)
    if (!res.ok) { setDiffs([]); return }
    const data = await res.json()
    setDiffs(data?.diffs || [])
  }

  if (loading) return <div style={{ padding: 20 }}>Loading...</div>
  if (error) return <div style={{ padding: 20, color: 'crimson' }}>{error}</div>
  if (!payload) return <div style={{ padding: 20 }}>No data</div>

  const est = payload.estimation_result || {}
  const narr = payload.narrative_sections || {}
  const ei = payload.estimation_input || {}

  return (
    <div style={{ padding: 20, fontFamily: 'Arial, sans-serif' }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← Back to Editor</Link>
      </div>
      <h1>Proposal Preview</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(220px, 1fr))', gap: 8 }}>
        <div><strong>Project:</strong> {ei.project_name || '-'}</div>
        <div><strong>POC:</strong> {ei.government_poc || '-'}</div>
        <div><strong>FY:</strong> {ei.fy || '-'}</div>
        <div><strong>Site Location:</strong> {ei.site_location || '-'}</div>
      </div>

      <h2 style={{ marginTop: 16 }}>Summary</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(220px, 1fr))', gap: 8 }}>
        <div><strong>Total Hours:</strong> {Number(est.total_labor_hours || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}</div>
        <div><strong>Total Cost:</strong> ${Number(est.total_cost || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
        <div><strong>Effective Rate:</strong> ${Number(est.effective_hourly_rate || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}/hr</div>
        <div><strong>Modules:</strong> {(ei.modules || []).length}</div>
        <div><strong>Complexity:</strong> {ei.complexity || 'M'}</div>
        <div><strong>Sites:</strong> {ei.sites || 1}</div>
      </div>

      <h2 style={{ marginTop: 16 }}>Module Breakdown</h2>
      {est.breakdown_by_module ? (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Module</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Focus</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Hours</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Cost</th>
            </tr>
          </thead>
          <tbody>
            {Object.values(est.breakdown_by_module).map((m: any, idx: number) => (
              <tr key={idx}>
                <td style={{ padding: 6 }}>{(m as any).module_name}</td>
                <td style={{ padding: 6 }}>{(m as any).focus_area}</td>
                <td style={{ textAlign: 'right', padding: 6 }}>{Number((m as any).hours).toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
                <td style={{ textAlign: 'right', padding: 6 }}>${Number((m as any).cost).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <div>No module breakdown</div>}

      <h2 style={{ marginTop: 16 }}>Resource Breakdown</h2>
      {est.breakdown_by_role ? (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Role</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Hours</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Rate</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Cost</th>
            </tr>
          </thead>
          <tbody>
            {Object.values(est.breakdown_by_role).map((r: any, idx: number) => (
              <tr key={idx}>
                <td style={{ padding: 6 }}>{(r as any).role_name}</td>
                <td style={{ textAlign: 'right', padding: 6 }}>{Number((r as any).hours).toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
                <td style={{ textAlign: 'right', padding: 6 }}>${Number((r as any).effective_rate).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                <td style={{ textAlign: 'right', padding: 6 }}>${Number((r as any).cost).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <div>No role breakdown</div>}

      <h2 style={{ marginTop: 16 }}>Narrative</h2>
      <div style={{ marginTop: 12, padding: 12, border: '1px solid #ddd', borderRadius: 6 }}>
        {Object.entries(narr).map(([k, v]) => (
          <div key={k} style={{ marginBottom: 12 }}>
            <strong>{k.replace('_',' ').toUpperCase()}</strong>
            <div style={{ whiteSpace: 'pre-wrap', marginTop: 4 }}>{String(v)}</div>
          </div>
        ))}
      </div>

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
                    {versions.map(v => <option key={v.id} value={v.version}>{v.version} {v.title ? `- ${v.title}` : ''}</option>)}
                  </select>
                </label>
                <label>To
                  <select value={toVer ?? ''} onChange={(e) => setToVer(Number(e.target.value))} style={{ marginLeft: 6 }}>
                    {versions.map(v => <option key={v.id} value={v.version}>{v.version} {v.title ? `- ${v.title}` : ''}</option>)}
                  </select>
                </label>
                <button onClick={runDiff}>Compare</button>
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
