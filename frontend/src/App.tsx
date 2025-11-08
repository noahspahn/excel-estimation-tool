import React, { useState, useEffect } from 'react'

const API = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [backendStatus, setBackendStatus] = useState('Checking...')
  const [modules, setModules] = useState<any[]>([])
  const [selectedModules, setSelectedModules] = useState<string[]>([])
  const [complexity, setComplexity] = useState<'S' | 'M' | 'L' | 'XL'>('M')
  const [downloading, setDownloading] = useState(false)
  const [includeAI, setIncludeAI] = useState(false)
  const [tone, setTone] = useState('professional')
  const [loadingNarrative, setLoadingNarrative] = useState(false)
  const [narrative, setNarrative] = useState<Record<string, string> | null>(null)

  // Report preview state
  const [estimate, setEstimate] = useState<any | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [editableNarrative, setEditableNarrative] = useState<Record<string, string>>({})

  // Extended input state (from Excel INPUT)
  const [projectName, setProjectName] = useState('')
  const [governmentPOC, setGovernmentPOC] = useState('')
  const [accountManager, setAccountManager] = useState('')
  const [serviceDeliveryMgr, setServiceDeliveryMgr] = useState('')
  const [serviceDeliveryExec, setServiceDeliveryExec] = useState('')
  const [siteLocation, setSiteLocation] = useState('')
  const [email, setEmail] = useState('')
  const [fy, setFy] = useState('')
  const [rapNumber, setRapNumber] = useState('')
  const [psiCode, setPsiCode] = useState('')
  const [additionalComments, setAdditionalComments] = useState('')
  const [sites, setSites] = useState<number>(1)
  const [overtime, setOvertime] = useState<boolean>(false)
  const [odcItems, setOdcItems] = useState<{ description: string; price: number }[]>([])
  const [fixedPriceItems, setFixedPriceItems] = useState<{ description: string; price: number }[]>([])
  const [hardwareSubtotal, setHardwareSubtotal] = useState<number>(0)
  const [warrantyMonths, setWarrantyMonths] = useState<number>(0)
  const [warrantyCost, setWarrantyCost] = useState<number>(0)

  useEffect(() => {
    // Test backend connection
    fetch(`${API}/health`)
      .then(res => res.json())
      .then(data => setBackendStatus(data.status || 'Connected'))
      .catch(() => setBackendStatus('Backend not connected'))

    // Fetch modules
    fetch(`${API}/api/v1/modules`)
      .then(res => res.json())
      .then(data => setModules(data || []))
      .catch(err => console.error('Failed to fetch modules:', err))
  }, [])

  const toggleModule = (id: string) => {
    setSelectedModules(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  const downloadReport = async () => {
    if (selectedModules.length === 0) {
      alert('Please select at least one module.')
      return
    }
    setDownloading(true)
    try {
      // If the user has edited narrative, pass it through and skip server-side AI
      const hasCustomNarrative = Object.keys(editableNarrative || {}).length > 0
      const qs = `?include_ai=${includeAI && !hasCustomNarrative}&tone=${encodeURIComponent(tone)}`
      const res = await fetch(`${API}/api/v1/report${qs}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          modules: selectedModules,
          complexity,
          environment: 'production',
          integration_level: 'moderate_integration',
          geography: 'dc_metro',
          clearance_level: 'secret',
          is_prime_contractor: true,
          custom_role_overrides: {},
          // extended fields
          project_name: projectName,
          government_poc: governmentPOC,
          account_manager: accountManager,
          service_delivery_mgr: serviceDeliveryMgr,
          service_delivery_exec: serviceDeliveryExec,
          site_location: siteLocation,
          email,
          fy,
          rap_number: rapNumber,
          psi_code: psiCode,
          additional_comments: additionalComments,
          sites,
          overtime,
          odc_items: odcItems,
          fixed_price_items: fixedPriceItems,
          hardware_subtotal: hardwareSubtotal,
          warranty_months: warrantyMonths,
          warranty_cost: warrantyCost,
          narrative_sections: hasCustomNarrative ? editableNarrative : undefined
        })
      })
      if (!res.ok) throw new Error('Failed to generate report')
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15)
      a.download = `estimation_report_${ts}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error(err)
      alert('Report generation failed')
    } finally {
      setDownloading(false)
    }
  }

  const previewNarrative = async () => {
    if (selectedModules.length === 0) {
      alert('Please select at least one module.')
      return
    }
    setLoadingNarrative(true)
    setNarrative(null)
    try {
      const res = await fetch(`${API}/api/v1/narrative`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          modules: selectedModules,
          complexity,
          environment: 'production',
          integration_level: 'moderate_integration',
          geography: 'dc_metro',
          clearance_level: 'secret',
          is_prime_contractor: true,
          custom_role_overrides: {},
          tone,
          sections: ['executive_summary','assumptions','risks','recommendations']
        })
      })
      if (!res.ok) {
        let detail = 'Failed to generate narrative'
        try {
          const err = await res.json()
          if (err?.detail) detail = err.detail
        } catch {}
        throw new Error(detail)
      }
      const data = await res.json()
      const narr = data?.narrative || {}
      setNarrative(narr)
      setEditableNarrative(narr)
    } catch (e: any) {
      console.error(e)
      alert(e?.message || 'Narrative generation failed (check OPENAI_API_KEY on backend).')
    } finally {
      setLoadingNarrative(false)
    }
  }

  const previewReport = async () => {
    if (selectedModules.length === 0) {
      alert('Please select at least one module.')
      return
    }
    setPreviewLoading(true)
    setShowPreview(false)
    try {
      // 1) Get estimate payload
      const estRes = await fetch(`${API}/api/v1/estimate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          modules: selectedModules,
          complexity,
          environment: 'production',
          integration_level: 'moderate_integration',
          geography: 'dc_metro',
          clearance_level: 'secret',
          is_prime_contractor: true,
          custom_role_overrides: {},
          project_name: projectName,
          government_poc: governmentPOC,
          account_manager: accountManager,
          service_delivery_mgr: serviceDeliveryMgr,
          service_delivery_exec: serviceDeliveryExec,
          site_location: siteLocation,
          email,
          fy,
          rap_number: rapNumber,
          psi_code: psiCode,
          additional_comments: additionalComments,
          sites,
          overtime,
          odc_items: odcItems,
          fixed_price_items: fixedPriceItems,
          hardware_subtotal: hardwareSubtotal,
          warranty_months: warrantyMonths,
          warranty_cost: warrantyCost,
        })
      })
      if (!estRes.ok) throw new Error('Failed to calculate estimate')
      const estData = await estRes.json()
      setEstimate(estData?.estimation_result || null)

      // 2) Optionally fetch AI narrative
      if (includeAI) {
        const nRes = await fetch(`${API}/api/v1/narrative`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            modules: selectedModules,
            complexity,
            environment: 'production',
            integration_level: 'moderate_integration',
            geography: 'dc_metro',
            clearance_level: 'secret',
            is_prime_contractor: true,
            custom_role_overrides: {},
            project_name: projectName,
            government_poc: governmentPOC,
            account_manager: accountManager,
            service_delivery_mgr: serviceDeliveryMgr,
            service_delivery_exec: serviceDeliveryExec,
            site_location: siteLocation,
            email,
            fy,
            rap_number: rapNumber,
            psi_code: psiCode,
            additional_comments: additionalComments,
            sites,
            overtime,
            odc_items: odcItems,
            fixed_price_items: fixedPriceItems,
            hardware_subtotal: hardwareSubtotal,
            warranty_months: warrantyMonths,
            warranty_cost: warrantyCost,
            tone,
            sections: ['executive_summary','assumptions','risks','recommendations']
          })
        })
        const payload = nRes.ok ? await nRes.json() : { narrative: {} }
        const narr = payload?.narrative || {}
        setNarrative(narr)
        setEditableNarrative(narr)
      } else {
        // Initialize empty editable narrative structure
        const base: Record<string, string> = {
          executive_summary: '',
          assumptions: '',
          risks: '',
          recommendations: ''
        }
        setNarrative(base)
        setEditableNarrative(base)
      }

      setShowPreview(true)
    } catch (e: any) {
      console.error(e)
      alert(e?.message || 'Failed to build report preview')
    } finally {
      setPreviewLoading(false)
    }
  }

  const clearAll = () => {
    setSelectedModules([])
    setComplexity('M')
    setIncludeAI(false)
    setTone('professional')
    setNarrative(null)
    setEditableNarrative({})
    setEstimate(null)
    setShowPreview(false)
    setProjectName('')
    setGovernmentPOC('')
    setAccountManager('')
    setServiceDeliveryMgr('')
    setServiceDeliveryExec('')
    setSiteLocation('')
    setEmail('')
    setFy('')
    setRapNumber('')
    setPsiCode('')
    setAdditionalComments('')
    setSites(1)
    setOvertime(false)
    setOdcItems([])
    setFixedPriceItems([])
    setHardwareSubtotal(0)
    setWarrantyMonths(0)
    setWarrantyCost(0)
  }

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>Estimation Tool</h1>
      <p>Backend Status: <strong>{backendStatus}</strong></p>
      
      <h2>Available Modules</h2>
      {modules.length > 0 ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          {modules.map((module: any) => (
            <label key={module.id} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                checked={selectedModules.includes(module.id)}
                onChange={() => toggleModule(module.id)}
              />
              <span>
                {module.name} ({module.focus_area}) - {Object.values(module.base_hours_by_role).map(Number).reduce((a, b) => a + b, 0)} base hours
              </span>
            </label>
          ))}
        </div>
      ) : (
        <p>Loading modules...</p>
      )}

      <div style={{ marginTop: 16 }}>
        <label>
          Complexity:
          <select value={complexity} onChange={(e) => setComplexity(e.target.value as any)} style={{ marginLeft: 8 }}>
            <option value="S">Small (S)</option>
            <option value="M">Medium (M)</option>
            <option value="L">Large (L)</option>
            <option value="XL">Extra Large (XL)</option>
          </select>
        </label>
      </div>

      <h2 style={{ marginTop: 24 }}>Project Information</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(240px, 1fr))', gap: 8 }}>
        <label>Project Name
          <input value={projectName} onChange={(e) => setProjectName(e.target.value)} style={{ width: '100%' }} />
        </label>
        <label>Fiscal Year (FY)
          <input value={fy} onChange={(e) => setFy(e.target.value)} style={{ width: '100%' }} />
        </label>
        <label>Government POC
          <input value={governmentPOC} onChange={(e) => setGovernmentPOC(e.target.value)} style={{ width: '100%' }} />
        </label>
        <label>Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: '100%' }} />
        </label>
        <label>Account Manager
          <input value={accountManager} onChange={(e) => setAccountManager(e.target.value)} style={{ width: '100%' }} />
        </label>
        <label>Service Delivery Mgr
          <input value={serviceDeliveryMgr} onChange={(e) => setServiceDeliveryMgr(e.target.value)} style={{ width: '100%' }} />
        </label>
        <label>Service Delivery Exec
          <input value={serviceDeliveryExec} onChange={(e) => setServiceDeliveryExec(e.target.value)} style={{ width: '100%' }} />
        </label>
        <label>Site Location
          <input value={siteLocation} onChange={(e) => setSiteLocation(e.target.value)} style={{ width: '100%' }} />
        </label>
        <label>RAP #
          <input value={rapNumber} onChange={(e) => setRapNumber(e.target.value)} style={{ width: '100%' }} />
        </label>
        <label>PSI Code
          <input value={psiCode} onChange={(e) => setPsiCode(e.target.value)} style={{ width: '100%' }} />
        </label>
      </div>
      <div style={{ marginTop: 8 }}>
        <label>Additional Comments
          <textarea value={additionalComments} onChange={(e) => setAdditionalComments(e.target.value)} rows={2} style={{ width: '100%' }} />
        </label>
      </div>

      <h2 style={{ marginTop: 24 }}>Scope Options</h2>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <label>Number of Sites
          <input type="number" min={1} value={sites} onChange={(e) => setSites(Math.max(1, parseInt(e.target.value || '1')))} style={{ width: 100, marginLeft: 8 }} />
        </label>
        <label>
          <input type="checkbox" checked={overtime} onChange={(e) => setOvertime(e.target.checked)} style={{ marginRight: 8 }} />
          Overtime Required
        </label>
      </div>

      <h2 style={{ marginTop: 24 }}>Other Costs</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(240px, 1fr))', gap: 8 }}>
        <label>Hardware Subtotal ($)
          <input type="number" min={0} value={hardwareSubtotal} onChange={(e) => setHardwareSubtotal(Number(e.target.value || 0))} style={{ width: '100%' }} />
        </label>
        <div />
        <label>Warranty Months
          <input type="number" min={0} value={warrantyMonths} onChange={(e) => setWarrantyMonths(Number(e.target.value || 0))} style={{ width: '100%' }} />
        </label>
        <label>Warranty Cost ($)
          <input type="number" min={0} value={warrantyCost} onChange={(e) => setWarrantyCost(Number(e.target.value || 0))} style={{ width: '100%' }} />
        </label>
      </div>

      <div style={{ marginTop: 12 }}>
        <h3>Other Direct Costs</h3>
        {odcItems.map((item, idx) => (
          <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <input placeholder="Description" value={item.description} onChange={(e) => setOdcItems(prev => prev.map((x, i) => i===idx ? { ...x, description: e.target.value } : x))} style={{ flex: 1 }} />
            <input placeholder="Price" type="number" min={0} value={item.price} onChange={(e) => setOdcItems(prev => prev.map((x, i) => i===idx ? { ...x, price: Number(e.target.value || 0) } : x))} style={{ width: 140 }} />
            <button onClick={() => setOdcItems(prev => prev.filter((_, i) => i!==idx))}>Remove</button>
          </div>
        ))}
        <button onClick={() => setOdcItems(prev => [...prev, { description: '', price: 0 }])}>Add ODC Item</button>
      </div>

      <div style={{ marginTop: 12 }}>
        <h3>Fixed-Price Items</h3>
        {fixedPriceItems.map((item, idx) => (
          <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <input placeholder="Description" value={item.description} onChange={(e) => setFixedPriceItems(prev => prev.map((x, i) => i===idx ? { ...x, description: e.target.value } : x))} style={{ flex: 1 }} />
            <input placeholder="Price" type="number" min={0} value={item.price} onChange={(e) => setFixedPriceItems(prev => prev.map((x, i) => i===idx ? { ...x, price: Number(e.target.value || 0) } : x))} style={{ width: 140 }} />
            <button onClick={() => setFixedPriceItems(prev => prev.filter((_, i) => i!==idx))}>Remove</button>
          </div>
        ))}
        <button onClick={() => setFixedPriceItems(prev => [...prev, { description: '', price: 0 }])}>Add Fixed-Price Item</button>
      </div>

      <h2>Quick Test Calculation</h2>
      <button onClick={() => {
        fetch(`${API}/api/v1/calculate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ base_hours: 100, complexity: 'M' })
        })
        .then(res => res.json())
        .then(data => alert(`Estimated cost: $${data.total_cost}`))
        .catch(err => alert('Calculation failed'))
      }}>
        Test Calculation (100 hours, Medium complexity)
      </button>

      <h2 style={{ marginTop: 24 }}>Report</h2>
      <div style={{ marginBottom: 8 }}>
        <label style={{ marginRight: 12 }}>
          <input type="checkbox" checked={includeAI} onChange={(e) => setIncludeAI(e.target.checked)} /> Include AI narrative
        </label>
        <label>
          Tone:
          <select value={tone} onChange={(e) => setTone(e.target.value)} style={{ marginLeft: 8 }}>
            <option value="professional">Professional</option>
            <option value="executive">Executive</option>
            <option value="technical">Technical</option>
            <option value="friendly">Friendly</option>
          </select>
        </label>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={previewReport} disabled={previewLoading}>
          {previewLoading ? 'Building Preview...' : 'Preview Report'}
        </button>
        <button onClick={downloadReport} disabled={downloading}>
          {downloading ? 'Generating...' : 'Download PDF Report'}
        </button>
        <button onClick={clearAll}>
          Clear Inputs
        </button>
      </div>

      <h2 style={{ marginTop: 24 }}>Narrative</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
        <button onClick={previewNarrative} disabled={loadingNarrative}>
          {loadingNarrative ? 'Generating...' : 'Generate Narrative'}
        </button>
        <button onClick={() => setEditableNarrative({})}>Clear Narrative</button>
      </div>
      {showPreview && estimate && (
        <div style={{ marginTop: 12, padding: 12, border: '1px solid #ddd', borderRadius: 6 }}>
          <h3>Report Preview</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(200px, 1fr))', gap: 8 }}>
            <div><strong>Total Hours:</strong> {Number(estimate.total_labor_hours).toLocaleString(undefined, { maximumFractionDigits: 1 })}</div>
            <div><strong>Total Cost:</strong> ${Number(estimate.total_cost).toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
            <div><strong>Effective Rate:</strong> ${Number(estimate.effective_hourly_rate).toLocaleString(undefined, { maximumFractionDigits: 2 })}/hr</div>
            <div><strong>Modules:</strong> {selectedModules.length}</div>
            <div><strong>Complexity:</strong> {complexity}</div>
            <div><strong>Sites:</strong> {sites}</div>
            <div><strong>Overtime:</strong> {overtime ? 'Yes' : 'No'}</div>
          </div>

          <div style={{ marginTop: 16 }}>
            <h4>Module Breakdown</h4>
            {estimate.breakdown_by_module ? (
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
                  {Object.values(estimate.breakdown_by_module).map((m: any, idx: number) => (
                    <tr key={idx}>
                      <td style={{ padding: 6 }}>{m.module_name}</td>
                      <td style={{ padding: 6 }}>{m.focus_area}</td>
                      <td style={{ textAlign: 'right', padding: 6 }}>{Number(m.hours).toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
                      <td style={{ textAlign: 'right', padding: 6 }}>${Number(m.cost).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <div>No module breakdown available.</div>}
          </div>

          <div style={{ marginTop: 16 }}>
            <h4>Resource Breakdown</h4>
            {estimate.breakdown_by_role ? (
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
                  {Object.values(estimate.breakdown_by_role).map((r: any, idx: number) => (
                    <tr key={idx}>
                      <td style={{ padding: 6 }}>{r.role_name}</td>
                      <td style={{ textAlign: 'right', padding: 6 }}>{Number(r.hours).toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
                      <td style={{ textAlign: 'right', padding: 6 }}>${Number(r.effective_rate).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                      <td style={{ textAlign: 'right', padding: 6 }}>${Number(r.cost).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <div>No role breakdown available.</div>}
          </div>

          <div style={{ marginTop: 16 }}>
            <h4>Other Costs</h4>
            <div><strong>Hardware Subtotal:</strong> ${hardwareSubtotal.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
            <div><strong>Warranty:</strong> {warrantyMonths} months, ${warrantyCost.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
            {odcItems.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div><strong>Other Direct Costs:</strong></div>
                <ul>
                  {odcItems.map((x, i) => (
                    <li key={i}>{x.description || 'Item'} — ${x.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}</li>
                  ))}
                </ul>
              </div>
            )}
            {fixedPriceItems.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div><strong>Fixed-Price Items:</strong></div>
                <ul>
                  {fixedPriceItems.map((x, i) => (
                    <li key={i}>{x.description || 'Item'} — ${x.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div style={{ marginTop: 16 }}>
            <h4>Editable Narrative</h4>
            {['executive_summary','assumptions','risks','recommendations'].map((k) => (
              <div key={k} style={{ marginBottom: 12 }}>
                <label style={{ display: 'block', fontWeight: 600 }}>{k.replace('_',' ').toUpperCase()}</label>
                <textarea
                  value={editableNarrative?.[k] || ''}
                  onChange={(e) => setEditableNarrative(prev => ({ ...prev, [k]: e.target.value }))}
                  rows={4}
                  style={{ width: '100%', padding: 8, fontFamily: 'inherit' }}
                  placeholder={`Write ${k.replace('_',' ')}...`}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default App
