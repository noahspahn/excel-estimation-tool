import { useState, useEffect } from 'react'
import TopNav from './TopNav'
import './App.css'
import { getApiBase } from './apiConfig'

const API = getApiBase()

const COGNITO_CLIENT_ID = (import.meta as any).env?.VITE_COGNITO_CLIENT_ID
const COGNITO_REGION = (import.meta as any).env?.VITE_COGNITO_REGION
const COGNITO_ENDPOINT = COGNITO_REGION
  ? `https://cognito-idp.${COGNITO_REGION}.amazonaws.com/`
  : null

const IS_LOCALHOST =
  typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1')

const DEV_STUB_EMAIL = (import.meta as any).env?.VITE_DEV_STUB_EMAIL || 'noahspahn@gmail.com'
const AUTH_DISABLED = String((import.meta as any).env?.VITE_DISABLE_AUTH ?? 'false').toLowerCase() === 'true'

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

function App() {
  const appVersion = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : ''
  const [backendStatus, setBackendStatus] = useState('Checking...')
  const [modules, setModules] = useState<any[]>([])
  const [selectedModules, setSelectedModules] = useState<string[]>([])
  const [complexity, setComplexity] = useState<'S' | 'M' | 'L' | 'XL'>('M')
  const [downloading, setDownloading] = useState(false)
  const [includeAI, setIncludeAI] = useState(true)
  const [tone, setTone] = useState('professional')
  const [styleGuide, setStyleGuide] = useState('')
  const [loadingNarrative, setLoadingNarrative] = useState(false)
  const [, setNarrative] = useState<Record<string, string> | null>(null)
  const [narrativeSectionBusy, setNarrativeSectionBusy] = useState<string | null>(null)
  const [narrativeSectionError, setNarrativeSectionError] = useState<string | null>(null)

  // Report preview state
  const [estimate, setEstimate] = useState<any | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [editableNarrative, setEditableNarrative] = useState<Record<string, string>>({})
  const [readOnly, setReadOnly] = useState(false)
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [sharePublicId, setSharePublicId] = useState<string | null>(null)
  const [previewIdInput, setPreviewIdInput] = useState<string>('')
  const [proposalId, setProposalId] = useState<string | null>(null)
  const [overwriteReportId, setOverwriteReportId] = useState<string | null>(null)
  const [reportLoadNotice, setReportLoadNotice] = useState<string | null>(null)
  const [queryReportApplied, setQueryReportApplied] = useState(false)
  const [prereqWarnings, setPrereqWarnings] = useState<string[]>([])
  const [authEmail, setAuthEmail] = useState<string | null>(null)
  const [authToken, setAuthToken] = useState<string | null>(null)
  // const [authRequestToken, setAuthRequestToken] = useState<string | null>(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [hasShareParam, setHasShareParam] = useState(false)
  const [autoScraped, setAutoScraped] = useState(false)
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signin')
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginError, setLoginError] = useState<string | null>(null)
  const [loginBusy, setLoginBusy] = useState(false)
  const [signupEmail, setSignupEmail] = useState('')
  const [signupPassword, setSignupPassword] = useState('')
  const [signupCode, setSignupCode] = useState('')
  const [signupError, setSignupError] = useState<string | null>(null)
  const [signupInfo, setSignupInfo] = useState<string | null>(null)
  const [signupBusy, setSignupBusy] = useState(false)
  const [awaitingVerification, setAwaitingVerification] = useState(false)
  const [devLoginBusy, setDevLoginBusy] = useState(false)
  const isAuthenticated = AUTH_DISABLED || (!!authToken && !!authEmail)
  const shouldEnforceAuth = !AUTH_DISABLED

  // Simple scraping test state
  const [scrapeUrl, setScrapeUrl] = useState('https://docs.google.com/document/d/1uGMj74V3aCBx9IgOiVzWk6MzN713lkDDnFSrzjKFl0w/edit?tab=t.0#heading=h.345z0enrcnzu')
  const [scrapeLoading, setScrapeLoading] = useState(false)
  const [scrapeError, setScrapeError] = useState<string | null>(null)
  const [scrapeResult, setScrapeResult] = useState<{
    url: string
    final_url?: string | null
    success: boolean
    status_code?: number | null
    content_type?: string | null
    encoding?: string | null
    text_excerpt: string
    truncated?: boolean
    error?: string | null
  } | null>(null)

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
  const [securityProtocols, setSecurityProtocols] = useState('')
  const [complianceFrameworks, setComplianceFrameworks] = useState('')
  const [additionalAssumptions, setAdditionalAssumptions] = useState('')
  const [sites, setSites] = useState<number>(1)
  const [overtime, setOvertime] = useState<boolean>(false)
  const [periodOfPerformance, setPeriodOfPerformance] = useState('')
  const [estimatingMethod, setEstimatingMethod] = useState<'engineering' | 'historical'>('engineering')
  const [historicalEstimates, setHistoricalEstimates] = useState<{ name: string; actual_hours: string; actual_total_cost: string; selected: boolean }[]>([])
  const [raciMatrix, setRaciMatrix] = useState(() => DEFAULT_RACI_ROWS.map((row) => ({ ...row })))
  const [roadmapPhases, setRoadmapPhases] = useState(() => DEFAULT_ROADMAP_PHASES.map((row) => ({ ...row })))
  const [roiCapexLow, setRoiCapexLow] = useState('')
  const [roiCapexHigh, setRoiCapexHigh] = useState('')
  const [roiCapexIntervalMonths, setRoiCapexIntervalMonths] = useState('')
  const [roiDowntimeCostPerHour, setRoiDowntimeCostPerHour] = useState('')
  const [roiCurrentAvailability, setRoiCurrentAvailability] = useState('')
  const [roiTargetAvailability, setRoiTargetAvailability] = useState('')
  const [roiLegacySupportAnnual, setRoiLegacySupportAnnual] = useState('')
  const [odcItems, setOdcItems] = useState<{ description: string; price: number }[]>([])
  const [fixedPriceItems, setFixedPriceItems] = useState<{ description: string; price: number }[]>([])
  const [hardwareSubtotal, setHardwareSubtotal] = useState<number>(0)
  const [warrantyMonths, setWarrantyMonths] = useState<number>(0)
  const [warrantyCost, setWarrantyCost] = useState<number>(0)
  const [subtaskPreview, setSubtaskPreview] = useState<any[] | null>(null)
  const [subtaskStatus, setSubtaskStatus] = useState<string | null>(null)
  const [subtaskError, setSubtaskError] = useState<string | null>(null)
  const [subtaskLoading, setSubtaskLoading] = useState(false)
  const [subtaskRaw, setSubtaskRaw] = useState<string | null>(null)
  const [assumptionsBusy, setAssumptionsBusy] = useState(false)
  const [assumptionsError, setAssumptionsError] = useState<string | null>(null)
  const [commentsBusy, setCommentsBusy] = useState(false)
  const [commentsError, setCommentsError] = useState<string | null>(null)
  const [securityBusy, setSecurityBusy] = useState(false)
  const [securityError, setSecurityError] = useState<string | null>(null)
  const [complianceBusy, setComplianceBusy] = useState(false)
  const [complianceError, setComplianceError] = useState<string | null>(null)

  useEffect(() => {
    // Test backend connection
    fetch(`${API}/api/health`)
      .then(res => {
        if (!res.ok) throw new Error(`health ${res.status}`)
        return res.json()
      })
      .then(data => setBackendStatus(data.status || 'Connected'))
      .catch(() => setBackendStatus('Backend not connected'))

    // Fetch modules
    fetch(`${API}/api/v1/modules`)
      .then(res => {
        if (!res.ok) throw new Error(`modules ${res.status}`)
        return res.json()
      })
      .then(data => setModules(Array.isArray(data) ? data : []))
      .catch(err => {
        setModules([])
        console.error('Failed to fetch modules:', err)
      })

    // Load shared read-only proposal if ?share= param
    const sp = new URLSearchParams(window.location.search)
    const share = sp.get('share')
    if (share) {
      setHasShareParam(true)
      fetch(`${API}/api/v1/proposals/public/${share}`)
        .then(res => {
          if (!res.ok) throw new Error('Share link not found')
          return res.json()
        })
        .then((data) => {
          const payload = data?.payload || {}
          const ei = payload.estimation_input || {}
          setSelectedModules(ei.modules || [])
          setComplexity(ei.complexity || 'M')
          setProjectName(ei.project_name || '')
          setGovernmentPOC(ei.government_poc || '')
          setAccountManager(ei.account_manager || '')
          setServiceDeliveryMgr(ei.service_delivery_mgr || '')
          setServiceDeliveryExec(ei.service_delivery_exec || '')
          setSiteLocation(ei.site_location || '')
          setEmail(ei.email || '')
          setFy(ei.fy || '')
          setRapNumber(ei.rap_number || '')
          setPsiCode(ei.psi_code || '')
          setAdditionalComments(ei.additional_comments || '')
          setSecurityProtocols(ei.security_protocols || '')
          setComplianceFrameworks(ei.compliance_frameworks || '')
          setAdditionalAssumptions(ei.additional_assumptions || '')
          setSites(ei.sites || 1)
          setOvertime(!!ei.overtime)
          setPeriodOfPerformance(ei.period_of_performance || '')
          setEstimatingMethod((ei.estimating_method as any) || 'engineering')
          setHistoricalEstimates(normalizeHistoricalEstimates(ei.historical_estimates))
          setRaciMatrix(Array.isArray(ei.raci_matrix) && ei.raci_matrix.length
            ? ei.raci_matrix
            : DEFAULT_RACI_ROWS.map((row) => ({ ...row })))
          setRoadmapPhases(Array.isArray(ei.roadmap_phases) && ei.roadmap_phases.length
            ? ei.roadmap_phases
            : DEFAULT_ROADMAP_PHASES.map((row) => ({ ...row })))
          setRoiCapexLow(ei.roi_capex_event_cost_low != null ? String(ei.roi_capex_event_cost_low) : '')
          setRoiCapexHigh(ei.roi_capex_event_cost_high != null ? String(ei.roi_capex_event_cost_high) : '')
          setRoiCapexIntervalMonths(ei.roi_capex_event_interval_months != null ? String(ei.roi_capex_event_interval_months) : '')
          setRoiDowntimeCostPerHour(ei.roi_downtime_cost_per_hour != null ? String(ei.roi_downtime_cost_per_hour) : '')
          setRoiCurrentAvailability(ei.roi_current_availability != null ? String(ei.roi_current_availability) : '')
          setRoiTargetAvailability(ei.roi_target_availability != null ? String(ei.roi_target_availability) : '')
          setRoiLegacySupportAnnual(ei.roi_legacy_support_savings_annual != null ? String(ei.roi_legacy_support_savings_annual) : '')
          setOdcItems(ei.odc_items || [])
          setFixedPriceItems(ei.fixed_price_items || [])
          setHardwareSubtotal(ei.hardware_subtotal || 0)
          setWarrantyMonths(ei.warranty_months || 0)
          setWarrantyCost(ei.warranty_cost || 0)
          setTone(payload.tone || 'professional')
          setStyleGuide(payload.style_guide || '')
          const narr = payload.narrative_sections || {}
          setNarrative(narr)
          setEditableNarrative(narr)
          setEstimate(payload.estimation_result || null)
      setShowPreview(true)
      setReadOnly(true)
      setShareUrl(window.location.href)
      setPreviewIdInput(share)
        })
        .catch(err => {
          console.error(err)
          setReadOnly(false)
        })
    }
  }, [])

  useEffect(() => {
    // Handle Cognito redirect with tokens in URL hash (#id_token=...)
    const hash = window.location.hash.replace(/^#/, '')
    if (hash) {
      const params = new URLSearchParams(hash)
      const idToken = params.get('id_token')
      if (idToken) {
        try {
          const payloadRaw = idToken.split('.')[1] || ''
          const padded = payloadRaw.replace(/-/g, '+').replace(/_/g, '/')
          const jsonStr = atob(padded)
          const payload = JSON.parse(jsonStr)
          const email = typeof payload?.email === 'string' ? payload.email : null
          localStorage.setItem('auth_token', idToken)
          if (email) localStorage.setItem('auth_email', email)
          setAuthToken(idToken)
          setAuthEmail(email)
        } catch (e) {
          console.error('Failed to parse Cognito id_token', e)
        }
        // Clean hash from URL
        window.history.replaceState(null, document.title, window.location.pathname + window.location.search)
      }
    }
  }, [])

  useEffect(() => {
    const t = localStorage.getItem('auth_token')
    const e = localStorage.getItem('auth_email')
    if (t) setAuthToken(t)
    if (e) setAuthEmail(e)
    setAuthChecked(true)
  }, [])

  useEffect(() => {
    if (autoScraped || hasShareParam || readOnly) return
    if (!authChecked) return
    if (!AUTH_DISABLED && !authToken) return
    setAutoScraped(true)
    runScrapeTest()
  }, [autoScraped, hasShareParam, readOnly, authChecked, authToken])

  const toggleModule = (id: string) => {
    if (readOnly) return
    setSelectedModules(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  const handleLogin = async () => {
    setLoginError(null)
    setSignupError(null)
    setSignupInfo(null)
    const email = loginEmail.trim()
    if (!email || !loginPassword) {
      setLoginError('Enter email and password')
      return
    }
    if (!COGNITO_ENDPOINT || !COGNITO_CLIENT_ID) {
      setLoginError('Auth not configured')
      return
    }
    setLoginBusy(true)
    try {
      const res = await fetch(COGNITO_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
        },
        body: JSON.stringify({
          AuthFlow: 'USER_PASSWORD_AUTH',
          ClientId: COGNITO_CLIENT_ID,
          AuthParameters: {
            USERNAME: email,
            PASSWORD: loginPassword,
          },
        }),
      })
      const data: any = await res.json()
      if (!res.ok) {
        const msg = data?.message || data?.__type || 'Login failed'
        setLoginError(msg)
        return
      }
      const idToken: string | undefined = data?.AuthenticationResult?.IdToken
      if (!idToken) {
        setLoginError('No token returned')
        return
      }
      try {
        const payloadRaw = idToken.split('.')[1] || ''
        const jsonStr = atob(payloadRaw.replace(/-/g, '+').replace(/_/g, '/'))
        const payload = JSON.parse(jsonStr)
        const emailClaim =
          typeof payload?.email === 'string' ? payload.email : email
        localStorage.setItem('auth_token', idToken)
        if (emailClaim) localStorage.setItem('auth_email', emailClaim)
        setAuthToken(idToken)
        setAuthEmail(emailClaim)
        setLoginPassword('')
      } catch (e) {
        console.error('Failed to parse Cognito id_token', e)
        setLoginError('Login succeeded but token parsing failed')
      }
    } catch (err) {
      console.error(err)
      setLoginError('Network or server error')
    } finally {
      setLoginBusy(false)
    }
  }

  const handleSignup = async () => {
    setSignupError(null)
    setSignupInfo(null)
    const email = signupEmail.trim()
    if (!email || !signupPassword) {
      setSignupError('Enter email and password')
      return
    }
    if (!email.includes('@')) {
      setSignupError('Enter a valid email address')
      return
    }
    if (!COGNITO_ENDPOINT || !COGNITO_CLIENT_ID) {
      setSignupError('Auth not configured')
      return
    }
    setSignupBusy(true)
    try {
      const res = await fetch(COGNITO_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': 'AWSCognitoIdentityProviderService.SignUp',
        },
        body: JSON.stringify({
          ClientId: COGNITO_CLIENT_ID,
          Username: email,
          Password: signupPassword,
          UserAttributes: [
            { Name: 'email', Value: email },
          ],
        }),
      })
      const data: any = await res.json()
      if (!res.ok) {
        const msg = data?.message || data?.__type || 'Sign up failed'
        setSignupError(msg)
        return
      }
      setAwaitingVerification(true)
      setSignupInfo('Check your email for a verification code, then enter it below.')
    } catch (err) {
      console.error(err)
      setSignupError('Network or server error')
    } finally {
      setSignupBusy(false)
    }
  }

  const handleDevStubLogin = async () => {
    setLoginError(null)
    setSignupError(null)
    setSignupInfo(null)

    if (!IS_LOCALHOST) {
      setLoginError('Dev stub login is only available on localhost.')
      return
    }
    if (!DEV_STUB_EMAIL) {
      setLoginError('Set VITE_DEV_STUB_EMAIL in your frontend .env to use dev stub login.')
      return
    }

    setDevLoginBusy(true)
    try {
      const reqRes = await fetch(`${API}/api/v1/auth/request_link`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: DEV_STUB_EMAIL }),
      })
      const reqData: any = await reqRes.json().catch(() => ({}))
      if (!reqRes.ok) {
        const msg = reqData?.detail || reqData?.error || 'Dev auth request failed'
        setLoginError(msg)
        return
      }
      const magicToken: string | undefined = reqData?.token
      if (!magicToken) {
        setLoginError('Dev auth did not return a magic token')
        return
      }

      const exRes = await fetch(`${API}/api/v1/auth/exchange`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: magicToken }),
      })
      const exData: any = await exRes.json().catch(() => ({}))
      if (!exRes.ok) {
        const msg = exData?.detail || exData?.error || 'Dev token exchange failed'
        setLoginError(msg)
        return
      }

      const accessToken: string | undefined = exData?.access_token
      const email: string | null =
        typeof exData?.email === 'string' ? exData.email : DEV_STUB_EMAIL

      if (!accessToken) {
        setLoginError('Dev exchange did not return an access token')
        return
      }

      localStorage.setItem('auth_token', accessToken)
      if (email) localStorage.setItem('auth_email', email)
      setAuthToken(accessToken)
      setAuthEmail(email)
    } catch (err) {
      console.error('Dev stub login error', err)
      setLoginError('Dev stub login failed (network or server error)')
    } finally {
      setDevLoginBusy(false)
    }
  }

  const extractScrapeSuggestions = (text: string) => {
    const cleaned = String(text || '').replace(/\r/g, '\n')
    const lines = cleaned.split('\n').map(line => line.trim()).filter(Boolean)
    const findLine = (regex: RegExp) => lines.find(line => regex.test(line))
    const extractAfterLabel = (regex: RegExp) => {
      const line = findLine(regex)
      if (!line) return ''
      return line.replace(regex, '').replace(/^[:\s-]+/, '').trim()
    }
    const extractByPatterns = (patterns: RegExp[]) => {
      for (const pattern of patterns) {
        const match = cleaned.match(pattern)
        if (match && match[1]) return match[1].trim()
      }
      return ''
    }

    let projectName =
      extractByPatterns([
        /Request for Proposal\s*\(RFP\)\s*-\s*([^\n]+)/i,
        /RFP\s*-\s*([^\n]+)/i,
        /Opportunity Title\s*[:\-]\s*([^\n]+)/i,
        /Solicitation Title\s*[:\-]\s*([^\n]+)/i,
        /Notice Title\s*[:\-]\s*([^\n]+)/i,
        /Title\s*[:\-]\s*([^\n]+)/i,
        /Subject\s*[:\-]\s*([^\n]+)/i,
      ]) ||
      extractAfterLabel(/^(title|solicitation title|notice title|opportunity title)\s*[:\-]/i) ||
      ''
    if (!projectName && lines.length) {
      const firstLine = lines[0]
      if (firstLine.length <= 120) projectName = firstLine
    }

    const siteLocation =
      extractByPatterns([
        /Site Location\s*[:\-]\s*([^\n]+)/i,
        /Place of Performance\s*[:\-]\s*([^\n]+)/i,
        /Primary Place of Performance\s*[:\-]\s*([^\n]+)/i,
        /Location\s*[:\-]\s*([^\n]+)/i,
      ]) ||
      extractAfterLabel(/^(place of performance|location|site location|place of delivery)\s*[:\-]/i) ||
      ''
    const governmentPOC =
      extractByPatterns([
        /Government POC\s*[:\-]\s*([^\n]+)/i,
        /Procurement Officer,?\s*([A-Za-z .'-]+)/i,
        /Point of Contact\s*[:\-]\s*([^\n]+)/i,
        /Contracting Officer\s*[:\-]\s*([^\n]+)/i,
        /Primary POC\s*[:\-]\s*([^\n]+)/i,
        /Primary Contact\s*[:\-]\s*([^\n]+)/i,
        /Contract Specialist\s*[:\-]\s*([^\n]+)/i,
        /\bCOR\b\s*[:\-]\s*([^\n]+)/i,
      ]) ||
      extractAfterLabel(/^(point of contact|poc|contracting officer|contact name)\s*[:\-]/i) ||
      ''
    const accountManager =
      extractByPatterns([/Account Manager\s*[:\-]\s*([^\n]+)/i]) || ''
    const serviceDeliveryMgr =
      extractByPatterns([/Service Delivery Manager\s*[:\-]\s*([^\n]+)/i]) || ''
    const serviceDeliveryExec =
      extractByPatterns([/Service Delivery Executive\s*[:\-]\s*([^\n]+)/i]) || ''
    const rapNumber =
      extractByPatterns([
        /RAP\s*#?\s*[:\-]\s*([A-Za-z0-9-]+)/i,
        /Solicitation Number\s*[:\-]\s*([A-Za-z0-9-]+)/i,
        /Solicitation\s*#\s*[:\-]?\s*([A-Za-z0-9-]+)/i,
        /Solicitation ID\s*[:\-]\s*([A-Za-z0-9-]+)/i,
        /Notice ID\s*[:\-]\s*([A-Za-z0-9-]+)/i,
        /Opportunity ID\s*[:\-]\s*([A-Za-z0-9-]+)/i,
      ]) || ''
    const psiCode =
      extractByPatterns([/PSI\s*Code\s*[:\-]\s*([A-Za-z0-9-]+)/i]) || ''

    const emailMatch = cleaned.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i)
    const email = emailMatch ? emailMatch[0] : ''

    const fyMatch =
      cleaned.match(/\bFY\s*([0-9]{4})\b/i) || cleaned.match(/\bFiscal Year\s*([0-9]{4})\b/i)
    const fy = fyMatch ? fyMatch[1] : ''

    const complianceCandidates: { label: string; re: RegExp }[] = [
      { label: 'NIST 800-53', re: /NIST\s*800-53/i },
      { label: 'NIST 800-171', re: /NIST\s*800-171/i },
      { label: 'NIST', re: /\bNIST\b/i },
      { label: 'RMF', re: /\bRMF\b/i },
      { label: 'DFARS', re: /\bDFARS\b/i },
      { label: 'CMMC', re: /\bCMMC\b/i },
      { label: 'FedRAMP', re: /\bFedRAMP\b/i },
      { label: 'FISMA', re: /\bFISMA\b/i },
      { label: 'HIPAA', re: /\bHIPAA\b/i },
      { label: 'CJIS', re: /\bCJIS\b/i },
      { label: 'ISO 27001', re: /ISO\s*27001/i },
      { label: 'SOC 2', re: /\bSOC\s*2\b/i },
      { label: 'PCI DSS', re: /\bPCI\s*DSS\b/i },
      { label: 'State Data Security Guidelines', re: /State Data Security Guidelines/i },
    ]
    const complianceHits = complianceCandidates
      .filter(item => item.re.test(cleaned))
      .map(item => item.label)
    const complianceFrameworks = Array.from(new Set(complianceHits)).join(', ')

    const securityCandidates: { label: string; re: RegExp }[] = [
      { label: 'Multi-factor authentication (MFA)', re: /\bMFA\b|multi[-\s]?factor/i },
      { label: 'Encryption at rest/in transit', re: /encryption|encrypt/i },
      { label: 'Zero Trust', re: /zero[-\s]?trust/i },
      { label: 'SIEM monitoring', re: /\bSIEM\b/i },
      { label: 'Incident response', re: /incident response/i },
      { label: 'Access control', re: /access control/i },
      { label: 'Continuous monitoring', re: /continuous monitoring/i },
      { label: 'Vulnerability management', re: /vulnerabil/i },
      { label: 'Firewall modernization', re: /firewall/i },
      { label: 'IDS/IPS', re: /\bIDS\/IPS\b|\bIDS\b|\bIPS\b/i },
      { label: 'Threat protection', re: /threat protection/i },
    ]
    const securityHits = securityCandidates
      .filter(item => item.re.test(cleaned))
      .map(item => item.label)
    const securityProtocols = Array.from(new Set(securityHits)).join(', ')

    return {
      projectName,
      accountManager,
      serviceDeliveryMgr,
      serviceDeliveryExec,
      siteLocation,
      governmentPOC,
      email,
      fy,
      rapNumber,
      psiCode,
      complianceFrameworks,
      securityProtocols,
    }
  }

  const applyScrapeSuggestions = (text: string) => {
    const suggestions = extractScrapeSuggestions(text || '')
    if (suggestions.projectName && !projectName) setProjectName(suggestions.projectName)
    if (suggestions.accountManager && !accountManager) setAccountManager(suggestions.accountManager)
    if (suggestions.serviceDeliveryMgr && !serviceDeliveryMgr) setServiceDeliveryMgr(suggestions.serviceDeliveryMgr)
    if (suggestions.serviceDeliveryExec && !serviceDeliveryExec) setServiceDeliveryExec(suggestions.serviceDeliveryExec)
    if (suggestions.siteLocation && !siteLocation) setSiteLocation(suggestions.siteLocation)
    if (suggestions.governmentPOC && !governmentPOC) setGovernmentPOC(suggestions.governmentPOC)
    if (suggestions.email && !email) setEmail(suggestions.email)
    if (suggestions.fy && !fy) setFy(suggestions.fy)
    if (suggestions.rapNumber && !rapNumber) setRapNumber(suggestions.rapNumber)
    if (suggestions.psiCode && !psiCode) setPsiCode(suggestions.psiCode)
    if (suggestions.securityProtocols && !securityProtocols) setSecurityProtocols(suggestions.securityProtocols)
    if (suggestions.complianceFrameworks && !complianceFrameworks) setComplianceFrameworks(suggestions.complianceFrameworks)
  }

  const buildScrapePromptPayload = () => {
    const moduleNames = selectedModules.map((id) => {
      const mod = modules.find((m) => m.id === id)
      return mod?.name || id
    })
    return {
      scraped_text: scrapeResult?.text_excerpt || '',
      project_name: projectName || undefined,
      site_location: siteLocation || undefined,
      government_poc: governmentPOC || undefined,
      fy: fy || undefined,
      selected_modules: moduleNames,
    }
  }

  const generatePromptedText = async (
    endpoint: string,
    label: string,
    onSuccess: (text: string) => void,
    setBusy: (busy: boolean) => void,
    setError: (msg: string | null) => void,
  ) => {
    setError(null)
    if (!scrapeResult?.success || !scrapeResult.text_excerpt) {
      setError(`Scrape the contract first to generate ${label}.`)
      return
    }
    if (!AUTH_DISABLED && !authToken) {
      setError(`Sign in to generate ${label}.`)
      return
    }
    setBusy(true)
    try {
      const res = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(!AUTH_DISABLED && authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify(buildScrapePromptPayload()),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.detail || `Failed to generate ${label}.`)
      }
      const data = await res.json()
      const text = (data?.text || '').trim()
      if (!text) {
        throw new Error(`No ${label} returned from the model.`)
      }
      onSuccess(text)
    } catch (e: any) {
      setError(e?.message || `Failed to generate ${label}.`)
    } finally {
      setBusy(false)
    }
  }

  const generateAdditionalAssumptions = async () => {
    await generatePromptedText(
      '/api/v1/assumptions/generate',
      'assumptions',
      setAdditionalAssumptions,
      setAssumptionsBusy,
      setAssumptionsError,
    )
  }

  const generateAdditionalComments = async () => {
    await generatePromptedText(
      '/api/v1/comments/generate',
      'additional comments',
      setAdditionalComments,
      setCommentsBusy,
      setCommentsError,
    )
  }

  const generateSecurityProtocols = async () => {
    await generatePromptedText(
      '/api/v1/security-protocols/generate',
      'security protocols',
      setSecurityProtocols,
      setSecurityBusy,
      setSecurityError,
    )
  }

  const generateComplianceFrameworks = async () => {
    await generatePromptedText(
      '/api/v1/compliance-frameworks/generate',
      'compliance frameworks',
      setComplianceFrameworks,
      setComplianceBusy,
      setComplianceError,
    )
  }

  const runScrapeTest = async () => {
    setScrapeError(null)
    setScrapeResult(null)
    const url = scrapeUrl.trim()
    if (!url) {
      setScrapeError('Enter a URL to scrape')
      return
    }
    if (!AUTH_DISABLED && !authToken) {
      setScrapeError('Sign in to run scraping tests')
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
          url,
          max_bytes: 200000,
          max_chars: 8000,
          timeout: 10.0,
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
      setScrapeResult(data)
      if (data?.success && data?.text_excerpt) {
        applyScrapeSuggestions(data.text_excerpt)
      }
    } catch (e) {
      console.error('Scrape error', e)
      setScrapeError('Network or server error while scraping')
    } finally {
      setScrapeLoading(false)
    }
  }

  const handleConfirmSignup = async () => {
    setSignupError(null)
    if (!awaitingVerification) {
      setSignupError('Request a verification code first')
      return
    }
    const email = signupEmail.trim()
    const code = signupCode.trim()
    if (!email || !code) {
      setSignupError('Enter email and verification code')
      return
    }
    if (!COGNITO_ENDPOINT || !COGNITO_CLIENT_ID) {
      setSignupError('Auth not configured')
      return
    }
    setSignupBusy(true)
    try {
      const res = await fetch(COGNITO_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': 'AWSCognitoIdentityProviderService.ConfirmSignUp',
        },
        body: JSON.stringify({
          ClientId: COGNITO_CLIENT_ID,
          Username: email,
          ConfirmationCode: code,
        }),
      })
      const data: any = await res.json()
      if (!res.ok) {
        const msg = data?.message || data?.__type || 'Verification failed'
        setSignupError(msg)
        return
      }
      setSignupInfo('Account confirmed. You can now sign in.')
      setSignupCode('')
      setAwaitingVerification(false)
      setAuthMode('signin')
      setLoginEmail(email)
      setLoginError(null)
    } catch (err) {
      console.error(err)
      setSignupError('Network or server error')
    } finally {
      setSignupBusy(false)
    }
  }

  // Recompute prerequisite warnings when selection or modules change
  useEffect(() => {
    if (!Array.isArray(modules)) {
      setPrereqWarnings([])
      return
    }
    const modMap: Record<string, any> = {}
    modules.forEach(m => { modMap[m.id] = m })
    const missing: string[] = []
    selectedModules.forEach(mid => {
      const m = modMap[mid]
      if (m?.prerequisites?.length) {
        m.prerequisites.forEach((p: string) => {
          if (!selectedModules.includes(p)) {
            const pName = modMap[p]?.name || p
            missing.push(`${m.name} requires ${pName}`)
          }
        })
      }
    })
    setPrereqWarnings(Array.from(new Set(missing)))
  }, [selectedModules, modules])

  const saveReportToServer = async () => {
    if (selectedModules.length === 0) {
      alert('Please select at least one module.')
      return
    }
    if (prereqWarnings.length > 0) {
      if (!confirm('Some prerequisites are missing. Continue anyway?')) return
    }
    if (!AUTH_DISABLED && !authToken) {
      alert('Please sign in to generate a saved report.')
      return
    }
    setDownloading(true)
    try {
      let reportProposalId = proposalId
      if (!reportProposalId) {
        reportProposalId = await initializeProposal()
      }
      if (!reportProposalId) {
        alert('Unable to initialize a proposal. Report was not generated.')
        return
      }
      const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
      // If the user has edited narrative, pass it through and skip server-side AI
      const hasCustomNarrative = Object.keys(editableNarrative || {}).length > 0
      const qs = `?include_ai=${includeAI && !hasCustomNarrative}&tone=${encodeURIComponent(tone)}`
      const contractUrl = scrapeResult?.success ? (scrapeResult.final_url || scrapeResult.url) : undefined
      const contractExcerpt = scrapeResult?.success ? (scrapeResult.text_excerpt || '') : undefined
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (!AUTH_DISABLED && authToken) headers.Authorization = `Bearer ${authToken}`
      const res = await fetch(`${API}/api/v1/report/jobs${qs}`, {
        method: 'POST',
        headers,
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
          security_protocols: securityProtocols,
          compliance_frameworks: complianceFrameworks,
          additional_assumptions: additionalAssumptions,
          sites,
          overtime,
          period_of_performance: periodOfPerformance,
          estimating_method: estimatingMethod,
          historical_estimates: serializeHistoricalEstimates(),
          raci_matrix: raciMatrix,
          roadmap_phases: roadmapPhases,
          odc_items: odcItems,
          fixed_price_items: fixedPriceItems,
          hardware_subtotal: hardwareSubtotal,
          warranty_months: warrantyMonths,
          warranty_cost: warrantyCost,
          roi_capex_event_cost_low: asNumber(roiCapexLow),
          roi_capex_event_cost_high: asNumber(roiCapexHigh),
          roi_capex_event_interval_months: asNumber(roiCapexIntervalMonths),
          roi_downtime_cost_per_hour: asNumber(roiDowntimeCostPerHour),
          roi_current_availability: asNumber(roiCurrentAvailability),
          roi_target_availability: asNumber(roiTargetAvailability),
          roi_legacy_support_savings_annual: asNumber(roiLegacySupportAnnual),
          tool_version: appVersion || undefined,
          proposal_id: reportProposalId || undefined,
          proposal_version: versions?.length ? versions[versions.length - 1]?.version : undefined,
          save_report: true,
          overwrite_report_id: overwriteReportId || undefined,
          report_label: projectName || undefined,
          use_ai_subtasks: includeAI,
          narrative_sections: hasCustomNarrative ? editableNarrative : undefined,
          contract_url: contractUrl,
          contract_excerpt: contractExcerpt,
          style_guide: styleGuide || undefined,
        })
      })
      if (!res.ok) throw new Error('Failed to queue report save job')
      const queued = await res.json().catch(() => ({}))
      const jobId = queued?.job_id
      if (!jobId) throw new Error('Report job id was not returned by the API')
      setReportLoadNotice(`Report save queued (${jobId}).`)

      const deadline = Date.now() + 10 * 60 * 1000
      let done = false
      while (!done && Date.now() < deadline) {
        await sleep(2000)
        const statusRes = await fetch(`${API}/api/v1/report/jobs/${encodeURIComponent(jobId)}`, { headers })
        if (!statusRes.ok) throw new Error('Failed to fetch report job status')
        const statusData = await statusRes.json().catch(() => ({}))
        const status = statusData?.status
        if (status === 'queued' || status === 'running') {
          setReportLoadNotice(`Report save in progress (${jobId})...`)
          continue
        }
        if (status === 'failed') {
          throw new Error(statusData?.error || 'Report save job failed')
        }
        if (status === 'completed') {
          const result = statusData?.result || {}
          const reportId = result?.report_id || result?.storage_record?.id || null
          const reportStatus = result?.report_status
          if (reportId) setOverwriteReportId(reportId)
          setReportLoadNotice(
            reportId
              ? reportStatus === 'overwritten'
                ? `Report ${reportId} overwritten and saved to server. Download from the Reports table below.`
                : `Report ${reportId} saved to server. Download from the Reports table below.`
              : `Report job completed. Refresh Reports to download.`
          )
          done = true
          await loadReportDocs()
        }
      }
      if (!done) {
        throw new Error('Report save job timed out while waiting for completion')
      }
    } catch (err) {
      console.error(err)
      alert('Report save failed')
    } finally {
      setDownloading(false)
    }
  }

  const previewNarrative = async () => {
    if (selectedModules.length === 0) {
      alert('Please select at least one module.')
      return
    }
    if (prereqWarnings.length > 0) {
      alert('Some prerequisites are missing. Please review module selection.')
      return
    }
    setLoadingNarrative(true)
    setNarrative(null)
    try {
      const contractUrl = scrapeResult?.success ? (scrapeResult.final_url || scrapeResult.url) : undefined
      const contractExcerpt = scrapeResult?.success ? (scrapeResult.text_excerpt || '') : undefined
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
          project_name: projectName || undefined,
          government_poc: governmentPOC || undefined,
          account_manager: accountManager || undefined,
          service_delivery_mgr: serviceDeliveryMgr || undefined,
          service_delivery_exec: serviceDeliveryExec || undefined,
          site_location: siteLocation || undefined,
          email: email || undefined,
          fy: fy || undefined,
          rap_number: rapNumber || undefined,
          psi_code: psiCode || undefined,
          additional_comments: additionalComments || undefined,
          security_protocols: securityProtocols || undefined,
          compliance_frameworks: complianceFrameworks || undefined,
          additional_assumptions: additionalAssumptions || undefined,
          sites,
          overtime,
          period_of_performance: periodOfPerformance || undefined,
          estimating_method: estimatingMethod,
          historical_estimates: serializeHistoricalEstimates(),
          raci_matrix: raciMatrix,
          roadmap_phases: roadmapPhases,
          odc_items: odcItems,
          fixed_price_items: fixedPriceItems,
          hardware_subtotal: hardwareSubtotal,
          warranty_months: warrantyMonths,
          warranty_cost: warrantyCost,
          roi_capex_event_cost_low: asNumber(roiCapexLow),
          roi_capex_event_cost_high: asNumber(roiCapexHigh),
          roi_capex_event_interval_months: asNumber(roiCapexIntervalMonths),
          roi_downtime_cost_per_hour: asNumber(roiDowntimeCostPerHour),
          roi_current_availability: asNumber(roiCurrentAvailability),
          roi_target_availability: asNumber(roiTargetAvailability),
          roi_legacy_support_savings_annual: asNumber(roiLegacySupportAnnual),
          contract_url: contractUrl,
          contract_excerpt: contractExcerpt,
          style_guide: styleGuide || undefined,
          tone,
          sections: ['executive_summary','assumptions','risks']
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

  const rewriteNarrativeSection = async (sectionKey: string) => {
    if (readOnly) return
    if (selectedModules.length === 0) {
      alert('Please select at least one module.')
      return
    }
    setNarrativeSectionError(null)
    setNarrativeSectionBusy(sectionKey)
    try {
      let estimationResult = estimate
      if (!estimationResult) {
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
            security_protocols: securityProtocols,
            compliance_frameworks: complianceFrameworks,
            additional_assumptions: additionalAssumptions,
            sites,
            overtime,
            period_of_performance: periodOfPerformance,
            estimating_method: estimatingMethod,
            historical_estimates: serializeHistoricalEstimates(),
            raci_matrix: raciMatrix,
            roadmap_phases: roadmapPhases,
            odc_items: odcItems,
            fixed_price_items: fixedPriceItems,
            hardware_subtotal: hardwareSubtotal,
            warranty_months: warrantyMonths,
            warranty_cost: warrantyCost,
            roi_capex_event_cost_low: asNumber(roiCapexLow),
            roi_capex_event_cost_high: asNumber(roiCapexHigh),
            roi_capex_event_interval_months: asNumber(roiCapexIntervalMonths),
            roi_downtime_cost_per_hour: asNumber(roiDowntimeCostPerHour),
            roi_current_availability: asNumber(roiCurrentAvailability),
            roi_target_availability: asNumber(roiTargetAvailability),
            roi_legacy_support_savings_annual: asNumber(roiLegacySupportAnnual),
          })
        })
        if (!estRes.ok) throw new Error('Failed to calculate estimate')
        const estData = await estRes.json()
        estimationResult = estData?.estimation_result || null
        setEstimate(estimationResult)
      }

      const contractUrl = scrapeResult?.success ? (scrapeResult.final_url || scrapeResult.url) : undefined
      const contractExcerpt = scrapeResult?.success ? (scrapeResult.text_excerpt || '') : undefined
      const estimationInput = {
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
        security_protocols: securityProtocols,
        compliance_frameworks: complianceFrameworks,
        additional_assumptions: additionalAssumptions,
        sites,
        overtime,
        period_of_performance: periodOfPerformance,
        estimating_method: estimatingMethod,
        historical_estimates: serializeHistoricalEstimates(),
        raci_matrix: raciMatrix,
        roadmap_phases: roadmapPhases,
        odc_items: odcItems,
        fixed_price_items: fixedPriceItems,
        hardware_subtotal: hardwareSubtotal,
        warranty_months: warrantyMonths,
        warranty_cost: warrantyCost,
        roi_capex_event_cost_low: asNumber(roiCapexLow),
        roi_capex_event_cost_high: asNumber(roiCapexHigh),
        roi_capex_event_interval_months: asNumber(roiCapexIntervalMonths),
        roi_downtime_cost_per_hour: asNumber(roiDowntimeCostPerHour),
        roi_current_availability: asNumber(roiCurrentAvailability),
        roi_target_availability: asNumber(roiTargetAvailability),
        roi_legacy_support_savings_annual: asNumber(roiLegacySupportAnnual),
      }
      const estimationData: any = {
        estimation_result: estimationResult || {},
        estimation_input: estimationInput,
        project_info: {
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
          security_protocols: securityProtocols,
          compliance_frameworks: complianceFrameworks,
          additional_assumptions: additionalAssumptions,
        },
        odc_items: odcItems,
        fixed_price_items: fixedPriceItems,
        hardware_subtotal: hardwareSubtotal,
        warranty_months: warrantyMonths,
        warranty_cost: warrantyCost,
        roi_inputs: {
          capex_event_cost_low: asNumber(roiCapexLow),
          capex_event_cost_high: asNumber(roiCapexHigh),
          capex_event_interval_months: asNumber(roiCapexIntervalMonths),
          downtime_cost_per_hour: asNumber(roiDowntimeCostPerHour),
          current_availability: asNumber(roiCurrentAvailability),
          target_availability: asNumber(roiTargetAvailability),
          legacy_support_savings_annual: asNumber(roiLegacySupportAnnual),
        },
        roi_horizon_years: 5,
        raci_matrix: raciMatrix,
        roadmap_phases: roadmapPhases,
        narrative_sections: editableNarrative,
      }
      if (contractUrl || contractExcerpt) {
        estimationData.contract_source = {
          url: contractUrl,
          excerpt: contractExcerpt,
        }
      }
      if (styleGuide.trim()) {
        estimationData.style_guide = styleGuide.trim()
      }

      const res = await fetch(`${API}/api/v1/narrative/section`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          section: sectionKey,
          prompt: '',
          current_text: editableNarrative?.[sectionKey] || '',
          tone,
          estimation_data: estimationData,
          input_summary: {
            complexity,
            module_count: selectedModules.length,
          },
          style_guide: styleGuide.trim() || undefined,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.detail || 'Failed to generate text for this section.')
      }
      const data = await res.json()
      const text = typeof data?.text === 'string' ? data.text : data?.[sectionKey]
      if (!text) throw new Error('No text returned from AI.')
      setEditableNarrative(prev => ({ ...prev, [sectionKey]: text }))
    } catch (e: any) {
      setNarrativeSectionError(e?.message || 'Unable to update section.')
    } finally {
      setNarrativeSectionBusy(null)
    }
  }

  const previewSubtasks = async () => {
    if (selectedModules.length === 0) {
      alert('Please select at least one module.')
      return
    }
    if (!AUTH_DISABLED && !authToken) {
      alert('Please sign in to generate subtasks.')
      return
    }
    setSubtaskLoading(true)
    setSubtaskError(null)
    setSubtaskPreview(null)
    try {
      const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
      const contractUrl = scrapeResult?.success ? (scrapeResult.final_url || scrapeResult.url) : undefined
      const contractExcerpt = scrapeResult?.success ? (scrapeResult.text_excerpt || '') : undefined
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(!AUTH_DISABLED && authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      }
      const res = await fetch(`${API}/api/v1/subtasks/preview/jobs`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          modules: selectedModules,
          complexity,
          environment: 'production',
          integration_level: 'moderate_integration',
          geography: 'dc_metro',
          clearance_level: 'secret',
          is_prime_contractor: true,
          custom_role_overrides: {},
          project_name: projectName || undefined,
          government_poc: governmentPOC || undefined,
          account_manager: accountManager || undefined,
          service_delivery_mgr: serviceDeliveryMgr || undefined,
          service_delivery_exec: serviceDeliveryExec || undefined,
          site_location: siteLocation || undefined,
          email: email || undefined,
          fy: fy || undefined,
          rap_number: rapNumber || undefined,
          psi_code: psiCode || undefined,
          additional_comments: additionalComments || undefined,
          security_protocols: securityProtocols || undefined,
          compliance_frameworks: complianceFrameworks || undefined,
          additional_assumptions: additionalAssumptions || undefined,
          sites,
          overtime,
          period_of_performance: periodOfPerformance || undefined,
          estimating_method: estimatingMethod,
          historical_estimates: serializeHistoricalEstimates(),
          raci_matrix: raciMatrix,
          roadmap_phases: roadmapPhases,
          odc_items: odcItems,
          fixed_price_items: fixedPriceItems,
          hardware_subtotal: hardwareSubtotal,
          warranty_months: warrantyMonths,
          warranty_cost: warrantyCost,
          roi_capex_event_cost_low: asNumber(roiCapexLow),
          roi_capex_event_cost_high: asNumber(roiCapexHigh),
          roi_capex_event_interval_months: asNumber(roiCapexIntervalMonths),
          roi_downtime_cost_per_hour: asNumber(roiDowntimeCostPerHour),
          roi_current_availability: asNumber(roiCurrentAvailability),
          roi_target_availability: asNumber(roiTargetAvailability),
          roi_legacy_support_savings_annual: asNumber(roiLegacySupportAnnual),
          contract_url: contractUrl,
          contract_excerpt: contractExcerpt,
          use_ai_subtasks: includeAI,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        const detail = err?.detail || 'Failed to queue subtask preview'
        throw new Error(detail)
      }
      const queued = await res.json().catch(() => ({}))
      const jobId = queued?.job_id
      if (!jobId) throw new Error('Subtask preview job id missing')

      const deadline = Date.now() + 5 * 60 * 1000
      let done = false
      while (!done && Date.now() < deadline) {
        await sleep(1500)
        const statusRes = await fetch(`${API}/api/v1/subtasks/preview/jobs/${encodeURIComponent(jobId)}`, { headers })
        if (!statusRes.ok) throw new Error('Failed to get subtask preview status')
        const statusData = await statusRes.json().catch(() => ({}))
        const status = statusData?.status
        if (status === 'queued' || status === 'running') continue
        if (status === 'failed') throw new Error(statusData?.error || 'Subtask preview failed')
        if (status === 'completed') {
          const data = statusData?.result || {}
          console.debug('Subtask preview response', data)
          setSubtaskPreview(data?.module_subtasks || [])
          setSubtaskStatus(data?.status || null)
          setSubtaskRaw(data?.raw_ai_response || null)
          if (data?.error) setSubtaskError(data.error)
          done = true
        }
      }
      if (!done) throw new Error('Subtask preview timed out')
    } catch (e: any) {
      console.error('Subtask preview failed', e)
      setSubtaskError(e?.message || 'Failed to generate subtasks')
    } finally {
      setSubtaskLoading(false)
    }
  }

  const updateRaciRow = (idx: number, patch: Record<string, string>) => {
    setRaciMatrix((prev) => prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)))
  }

  const addRaciRow = () => {
    setRaciMatrix((prev) => [
      ...prev,
      { milestone: '', responsible: '', accountable: '', consulted: '', informed: '' },
    ])
  }

  const removeRaciRow = (idx: number) => {
    setRaciMatrix((prev) => prev.filter((_, i) => i !== idx))
  }

  const updateRoadmapPhase = (idx: number, patch: Record<string, string>) => {
    setRoadmapPhases((prev) => prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)))
  }

  const updateHistoricalEstimate = (idx: number, patch: Record<string, any>) => {
    setHistoricalEstimates((prev) => prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)))
  }

  const addHistoricalEstimate = () => {
    setHistoricalEstimates((prev) => ([
      ...prev,
      { name: '', actual_hours: '', actual_total_cost: '', selected: true },
    ]))
  }

  const removeHistoricalEstimate = (idx: number) => {
    setHistoricalEstimates((prev) => prev.filter((_, i) => i !== idx))
  }

  const countWords = (s: string) => (s || '').trim().split(/\s+/).filter(Boolean).length
  const asNumber = (value: string) => {
    const trimmed = (value || '').trim()
    if (!trimmed) return undefined
    const num = Number(trimmed)
    return Number.isFinite(num) ? num : undefined
  }
  const serializeHistoricalEstimates = (items = historicalEstimates) => (
    items.map((item) => ({
      name: item.name,
      actual_hours: asNumber(item.actual_hours),
      actual_total_cost: asNumber(item.actual_total_cost),
      selected: item.selected,
    }))
  )
  const normalizeHistoricalEstimates = (items: any) => (
    Array.isArray(items)
      ? items.map((item) => ({
          name: item?.name || '',
          actual_hours: item?.actual_hours != null
            ? String(item.actual_hours)
            : (item?.total_hours != null ? String(item.total_hours) : ''),
          actual_total_cost: item?.actual_total_cost != null
            ? String(item.actual_total_cost)
            : (item?.total_cost != null ? String(item.total_cost) : ''),
          selected: item?.selected !== false,
        }))
      : []
  )
  const formatBytes = (bytes?: number) => {
    if (bytes == null || !Number.isFinite(bytes)) return '-'
    if (bytes === 0) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB']
    const idx = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)))
    const value = bytes / Math.pow(1024, idx)
    return `${value.toFixed(value >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`
  }

  // Draft helpers
  const buildDraft = () => ({
    estimation_input: {
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
      security_protocols: securityProtocols,
      compliance_frameworks: complianceFrameworks,
      additional_assumptions: additionalAssumptions,
      sites,
      overtime,
      period_of_performance: periodOfPerformance,
      estimating_method: estimatingMethod,
      historical_estimates: serializeHistoricalEstimates(),
      raci_matrix: raciMatrix,
      roadmap_phases: roadmapPhases,
      odc_items: odcItems,
      fixed_price_items: fixedPriceItems,
      hardware_subtotal: hardwareSubtotal,
      warranty_months: warrantyMonths,
      warranty_cost: warrantyCost,
      roi_capex_event_cost_low: asNumber(roiCapexLow),
      roi_capex_event_cost_high: asNumber(roiCapexHigh),
      roi_capex_event_interval_months: asNumber(roiCapexIntervalMonths),
      roi_downtime_cost_per_hour: asNumber(roiDowntimeCostPerHour),
      roi_current_availability: asNumber(roiCurrentAvailability),
      roi_target_availability: asNumber(roiTargetAvailability),
      roi_legacy_support_savings_annual: asNumber(roiLegacySupportAnnual),
    },
    narrative_sections: editableNarrative,
    estimation_result: estimate,
    tone,
    style_guide: styleGuide,
    ts: new Date().toISOString(),
  })

  const saveDraftLocal = () => {
    const draft = buildDraft()
    localStorage.setItem('estimation_draft', JSON.stringify(draft))
    alert('Draft saved locally.')
  }

  const loadDraftLocal = () => {
    const raw = localStorage.getItem('estimation_draft')
    if (!raw) { alert('No local draft found'); return }
    try {
      const d = JSON.parse(raw)
      const ei = d.estimation_input || {}
      setSelectedModules(ei.modules || [])
      setComplexity(ei.complexity || 'M')
      setProjectName(ei.project_name || '')
      setGovernmentPOC(ei.government_poc || '')
      setAccountManager(ei.account_manager || '')
      setServiceDeliveryMgr(ei.service_delivery_mgr || '')
      setServiceDeliveryExec(ei.service_delivery_exec || '')
      setSiteLocation(ei.site_location || '')
      setEmail(ei.email || '')
      setFy(ei.fy || '')
      setRapNumber(ei.rap_number || '')
      setPsiCode(ei.psi_code || '')
      setAdditionalComments(ei.additional_comments || '')
      setSecurityProtocols(ei.security_protocols || '')
      setComplianceFrameworks(ei.compliance_frameworks || '')
      setAdditionalAssumptions(ei.additional_assumptions || '')
      setSites(ei.sites || 1)
      setOvertime(!!ei.overtime)
      setPeriodOfPerformance(ei.period_of_performance || '')
      setEstimatingMethod((ei.estimating_method as any) || 'engineering')
      setHistoricalEstimates(normalizeHistoricalEstimates(ei.historical_estimates))
      setRaciMatrix(Array.isArray(ei.raci_matrix) && ei.raci_matrix.length
        ? ei.raci_matrix
        : DEFAULT_RACI_ROWS.map((row) => ({ ...row })))
      setRoadmapPhases(Array.isArray(ei.roadmap_phases) && ei.roadmap_phases.length
        ? ei.roadmap_phases
        : DEFAULT_ROADMAP_PHASES.map((row) => ({ ...row })))
      setRoiCapexLow(ei.roi_capex_event_cost_low != null ? String(ei.roi_capex_event_cost_low) : '')
      setRoiCapexHigh(ei.roi_capex_event_cost_high != null ? String(ei.roi_capex_event_cost_high) : '')
      setRoiCapexIntervalMonths(ei.roi_capex_event_interval_months != null ? String(ei.roi_capex_event_interval_months) : '')
      setRoiDowntimeCostPerHour(ei.roi_downtime_cost_per_hour != null ? String(ei.roi_downtime_cost_per_hour) : '')
      setRoiCurrentAvailability(ei.roi_current_availability != null ? String(ei.roi_current_availability) : '')
      setRoiTargetAvailability(ei.roi_target_availability != null ? String(ei.roi_target_availability) : '')
      setRoiLegacySupportAnnual(ei.roi_legacy_support_savings_annual != null ? String(ei.roi_legacy_support_savings_annual) : '')
      setOdcItems(ei.odc_items || [])
      setFixedPriceItems(ei.fixed_price_items || [])
      setHardwareSubtotal(ei.hardware_subtotal || 0)
      setWarrantyMonths(ei.warranty_months || 0)
      setWarrantyCost(ei.warranty_cost || 0)
      setTone(d.tone || 'professional')
      setStyleGuide(d.style_guide || '')
      const narr = d.narrative_sections || {}
      setNarrative(narr)
      setEditableNarrative(narr)
      setEstimate(d.estimation_result || null)
      setShowPreview(!!d.estimation_result)
    } catch (e) {
      alert('Failed to load draft')
    }
  }

  const exportDraft = () => {
    const draft = buildDraft()
    const blob = new Blob([JSON.stringify(draft, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15)
    a.download = `estimation_draft_${ts}.json`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const importDraft = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const d = JSON.parse(String(reader.result))
        const ei = d.estimation_input || {}
        setSelectedModules(ei.modules || [])
        setComplexity(ei.complexity || 'M')
        setProjectName(ei.project_name || '')
        setGovernmentPOC(ei.government_poc || '')
        setAccountManager(ei.account_manager || '')
        setServiceDeliveryMgr(ei.service_delivery_mgr || '')
        setServiceDeliveryExec(ei.service_delivery_exec || '')
        setSiteLocation(ei.site_location || '')
        setEmail(ei.email || '')
        setFy(ei.fy || '')
        setRapNumber(ei.rap_number || '')
        setPsiCode(ei.psi_code || '')
        setAdditionalComments(ei.additional_comments || '')
        setSecurityProtocols(ei.security_protocols || '')
        setComplianceFrameworks(ei.compliance_frameworks || '')
        setAdditionalAssumptions(ei.additional_assumptions || '')
        setSites(ei.sites || 1)
        setOvertime(!!ei.overtime)
        setPeriodOfPerformance(ei.period_of_performance || '')
        setEstimatingMethod((ei.estimating_method as any) || 'engineering')
        setHistoricalEstimates(normalizeHistoricalEstimates(ei.historical_estimates))
        setRaciMatrix(Array.isArray(ei.raci_matrix) && ei.raci_matrix.length
          ? ei.raci_matrix
          : DEFAULT_RACI_ROWS.map((row) => ({ ...row })))
        setRoadmapPhases(Array.isArray(ei.roadmap_phases) && ei.roadmap_phases.length
          ? ei.roadmap_phases
          : DEFAULT_ROADMAP_PHASES.map((row) => ({ ...row })))
        setRoiCapexLow(ei.roi_capex_event_cost_low != null ? String(ei.roi_capex_event_cost_low) : '')
        setRoiCapexHigh(ei.roi_capex_event_cost_high != null ? String(ei.roi_capex_event_cost_high) : '')
        setRoiCapexIntervalMonths(ei.roi_capex_event_interval_months != null ? String(ei.roi_capex_event_interval_months) : '')
        setRoiDowntimeCostPerHour(ei.roi_downtime_cost_per_hour != null ? String(ei.roi_downtime_cost_per_hour) : '')
        setRoiCurrentAvailability(ei.roi_current_availability != null ? String(ei.roi_current_availability) : '')
        setRoiTargetAvailability(ei.roi_target_availability != null ? String(ei.roi_target_availability) : '')
        setRoiLegacySupportAnnual(ei.roi_legacy_support_savings_annual != null ? String(ei.roi_legacy_support_savings_annual) : '')
        setOdcItems(ei.odc_items || [])
        setFixedPriceItems(ei.fixed_price_items || [])
        setHardwareSubtotal(ei.hardware_subtotal || 0)
        setWarrantyMonths(ei.warranty_months || 0)
        setWarrantyCost(ei.warranty_cost || 0)
        setTone(d.tone || 'professional')
        setStyleGuide(d.style_guide || '')
        const narr = d.narrative_sections || {}
        setNarrative(narr)
        setEditableNarrative(narr)
        setEstimate(d.estimation_result || null)
        setShowPreview(!!d.estimation_result)
      } catch (e) {
        alert('Invalid draft file')
      }
    }
    reader.readAsText(file)
  }

  const createShareLink = async () => {
    if (selectedModules.length === 0) { alert('Please select at least one module.'); return }
    if (prereqWarnings.length > 0) { alert('Some prerequisites are missing.'); return }
    try {
      // Ensure we have a current estimate to share
      const estRes = await fetch(`${API}/api/v1/estimate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildDraft().estimation_input)
      })
      if (!estRes.ok) throw new Error('Failed to calculate estimate')
      const estData = await estRes.json()
      const payload = buildDraft()
      payload.estimation_result = estData?.estimation_result
      if (!AUTH_DISABLED && (!authToken || !authEmail)) { alert('Please sign in to create a share link.'); return }
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (!AUTH_DISABLED && authToken) headers.Authorization = `Bearer ${authToken}`
      const res = await fetch(`${API}/api/v1/proposals`, {
        method: 'POST', headers,
        body: JSON.stringify({ title: projectName || 'Proposal', payload })
      })
      if (!res.ok) throw new Error('Failed to save proposal')
      const data = await res.json()
      const pub = data.public_id
      const url = `${window.location.origin}/preview/${encodeURIComponent(pub)}`
      setShareUrl(url)
      setSharePublicId(pub)
      setPreviewIdInput(pub)
      setProposalId(data.id)
      setReadOnly(false)
      alert('Share link created. You can copy it from the banner.')
    } catch (e: any) {
      alert(e?.message || 'Failed to create share link')
    }
  }

  const saveVersion = async () => {
    if (!proposalId) { alert('Create a share link first to initialize the proposal.'); return }
    try {
      if (!AUTH_DISABLED && (!authToken || !authEmail)) { alert('Please sign in first.'); return }
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (!AUTH_DISABLED && authToken) headers.Authorization = `Bearer ${authToken}`
      const res = await fetch(`${API}/api/v1/proposals/${proposalId}/versions`, {
        method: 'POST', headers,
        body: JSON.stringify({ title: projectName || undefined, payload: buildDraft() })
      })
      if (!res.ok) throw new Error('Failed to save version')
      alert('Version saved.')
    } catch (e: any) {
      alert(e?.message || 'Failed to save version')
    }
  }

  // Editor: versions list + restore
  const [versions, setVersions] = useState<{ id: string; version: number; title?: string; created_at?: string }[]>([])
  const [versionsLoaded, setVersionsLoaded] = useState(false)
  const [reportDocs, setReportDocs] = useState<any[]>([])
  const [reportsLoaded, setReportsLoaded] = useState(false)
  const [reportsError, setReportsError] = useState<string | null>(null)
  const [reportScope, setReportScope] = useState<'all' | 'proposal'>('all')
  const [initBusy, setInitBusy] = useState(false)

  const loadVersions = async () => {
    if (!proposalId) { setVersions([]); setVersionsLoaded(true); return }
    try {
      const res = await fetch(`${API}/api/v1/proposals/${proposalId}/versions`, { headers: !AUTH_DISABLED && authToken ? { 'Authorization': `Bearer ${authToken}` } : {} })
      if (!res.ok) throw new Error('Failed to load versions')
      const rows = await res.json()
      setVersions(rows || [])
      setVersionsLoaded(true)
    } catch (e) {
      setVersionsLoaded(true)
    }
  }

  const initializeProposal = async (): Promise<string | null> => {
    if (proposalId) { alert('Proposal already initialized.'); return proposalId }
    if (selectedModules.length === 0) { alert('Please select at least one module.'); return null }
    if (prereqWarnings.length > 0) { alert('Some prerequisites are missing.'); return null }
    try {
      setInitBusy(true)
      let estimationResult = estimate
      if (!estimationResult) {
        const estRes = await fetch(`${API}/api/v1/estimate`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildDraft().estimation_input)
        })
        if (!estRes.ok) throw new Error('Failed to calculate estimate')
        const estData = await estRes.json()
        estimationResult = estData?.estimation_result || null
        setEstimate(estimationResult)
      }
      const payload = buildDraft()
      payload.estimation_result = estimationResult
      if (!AUTH_DISABLED && (!authToken || !authEmail)) { alert('Please sign in to initialize a proposal.'); return null }
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (!AUTH_DISABLED && authToken) headers.Authorization = `Bearer ${authToken}`
      const res = await fetch(`${API}/api/v1/proposals`, {
        method: 'POST', headers,
        body: JSON.stringify({ title: projectName || 'Proposal', payload })
      })
      if (!res.ok) throw new Error('Failed to create proposal')
      const data = await res.json()
      const pub = data.public_id
      setProposalId(data.id)
      setSharePublicId(pub)
      setPreviewIdInput(pub)
      setShareUrl(`${window.location.origin}/preview/${encodeURIComponent(pub)}`)
      await loadVersions()
      await loadReportDocs()
      alert('Proposal initialized. You can now save versions and reports.')
      return data.id
    } catch (e: any) {
      alert(e?.message || 'Failed to initialize proposal')
      return null
    } finally {
      setInitBusy(false)
    }
  }

  const loadReportDocs = async () => {
    try {
      setReportsLoaded(false)
      setReportsError(null)
      const headers: Record<string, string> = !AUTH_DISABLED && authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
      const params = new URLSearchParams({ presign: 'true' })
      if (reportScope === 'proposal' && proposalId) {
        params.set('proposal_id', proposalId)
      }
      const res = await fetch(`${API}/api/v1/reports?${params.toString()}`, { headers })
      if (!res.ok) throw new Error('Failed to load reports')
      const rows = await res.json()
      const reports = Array.isArray(rows) ? rows : []
      setReportDocs(reports)
      setReportsLoaded(true)
    } catch (e: any) {
      setReportsLoaded(true)
      setReportsError(e?.message || 'Failed to load reports')
    }
  }

  const deleteReport = async (doc: any) => {
    if (!confirm('Delete this report? This removes the PDF and its database entry.')) return
    try {
      setReportsError(null)
      const headers: Record<string, string> = !AUTH_DISABLED && authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
      const res = await fetch(`${API}/api/v1/reports/${doc.id}`, {
        method: 'DELETE',
        headers,
      })
      if (!res.ok) throw new Error('Failed to delete report')
      if (overwriteReportId === doc.id) {
        setOverwriteReportId(null)
      }
      await loadReportDocs()
    } catch (e: any) {
      setReportsError(e?.message || 'Failed to delete report')
    }
  }

  useEffect(() => {
    if (proposalId) {
      loadVersions()
    }
  }, [proposalId, authToken])

  useEffect(() => {
    if (AUTH_DISABLED || authToken) {
      if (reportScope === 'proposal' && !proposalId) {
        setReportScope('all')
        return
      }
      loadReportDocs()
    }
  }, [proposalId, authToken, reportScope])

  const applyPayloadToEditor = (payload: any) => {
    const ei = payload?.estimation_input || {}
    setSelectedModules(ei.modules || [])
    setComplexity(ei.complexity || 'M')
    setProjectName(ei.project_name || '')
    setGovernmentPOC(ei.government_poc || '')
    setAccountManager(ei.account_manager || '')
    setServiceDeliveryMgr(ei.service_delivery_mgr || '')
    setServiceDeliveryExec(ei.service_delivery_exec || '')
    setSiteLocation(ei.site_location || '')
    setEmail(ei.email || '')
    setFy(ei.fy || '')
    setRapNumber(ei.rap_number || '')
    setPsiCode(ei.psi_code || '')
    setAdditionalComments(ei.additional_comments || '')
    setSecurityProtocols(ei.security_protocols || '')
    setComplianceFrameworks(ei.compliance_frameworks || '')
    setAdditionalAssumptions(ei.additional_assumptions || '')
    setSites(ei.sites || 1)
    setOvertime(!!ei.overtime)
    setPeriodOfPerformance(ei.period_of_performance || '')
    setEstimatingMethod((ei.estimating_method as any) || 'engineering')
    setHistoricalEstimates(normalizeHistoricalEstimates(ei.historical_estimates))
    setRaciMatrix(Array.isArray(ei.raci_matrix) && ei.raci_matrix.length
      ? ei.raci_matrix
      : DEFAULT_RACI_ROWS.map((row) => ({ ...row })))
    setRoadmapPhases(Array.isArray(ei.roadmap_phases) && ei.roadmap_phases.length
      ? ei.roadmap_phases
      : DEFAULT_ROADMAP_PHASES.map((row) => ({ ...row })))
    setRoiCapexLow(ei.roi_capex_event_cost_low != null ? String(ei.roi_capex_event_cost_low) : '')
    setRoiCapexHigh(ei.roi_capex_event_cost_high != null ? String(ei.roi_capex_event_cost_high) : '')
    setRoiCapexIntervalMonths(ei.roi_capex_event_interval_months != null ? String(ei.roi_capex_event_interval_months) : '')
    setRoiDowntimeCostPerHour(ei.roi_downtime_cost_per_hour != null ? String(ei.roi_downtime_cost_per_hour) : '')
    setRoiCurrentAvailability(ei.roi_current_availability != null ? String(ei.roi_current_availability) : '')
    setRoiTargetAvailability(ei.roi_target_availability != null ? String(ei.roi_target_availability) : '')
    setRoiLegacySupportAnnual(ei.roi_legacy_support_savings_annual != null ? String(ei.roi_legacy_support_savings_annual) : '')
    setOdcItems(ei.odc_items || [])
    setFixedPriceItems(ei.fixed_price_items || [])
    setHardwareSubtotal(ei.hardware_subtotal || 0)
    setWarrantyMonths(ei.warranty_months || 0)
    setWarrantyCost(ei.warranty_cost || 0)
    setStyleGuide(payload?.style_guide || '')
    const narr = payload?.narrative_sections || {}
    setNarrative(narr)
    setEditableNarrative(narr)
    setEstimate(payload?.estimation_result || null)
    setShowPreview(!!payload?.estimation_result)
  }

  const loadSavedReportPayload = async (reportId: string, overwriteId?: string | null) => {
    if (!reportId) return
    if (!AUTH_DISABLED && !authToken) return
    try {
      setReportsError(null)
      const headers: Record<string, string> = !AUTH_DISABLED && authToken ? { Authorization: `Bearer ${authToken}` } : {}
      const res = await fetch(`${API}/api/v1/reports/${encodeURIComponent(reportId)}/payload`, { headers })
      if (!res.ok) throw new Error('Failed to load saved report payload')
      const data = await res.json()
      applyPayloadToEditor(data?.payload || {})
      if (data?.proposal_id) {
        setProposalId(data.proposal_id)
      }
      if (data?.proposal_public_id) {
        setSharePublicId(data.proposal_public_id)
        setPreviewIdInput(data.proposal_public_id)
        setShareUrl(`${window.location.origin}/preview/${encodeURIComponent(data.proposal_public_id)}`)
      }
      const nextOverwriteId = overwriteId || null
      setOverwriteReportId(nextOverwriteId)
      setReportLoadNotice(
        nextOverwriteId
          ? `Loaded report ${reportId}. Next report save will overwrite this entry.`
          : `Loaded report ${reportId} into the editor.`
      )
      await loadReportDocs()
    } catch (e: any) {
      setReportLoadNotice(null)
      setReportsError(e?.message || 'Failed to load saved report payload')
    }
  }

  useEffect(() => {
    if (queryReportApplied) return
    const params = new URLSearchParams(window.location.search)
    const reportId = params.get('load_report_id')
    if (!reportId) {
      setQueryReportApplied(true)
      return
    }
    if (!AUTH_DISABLED && !authToken) {
      return
    }

    const overwriteId = params.get('overwrite_report_id')
    loadSavedReportPayload(reportId, overwriteId)
      .finally(() => {
        params.delete('load_report_id')
        params.delete('overwrite_report_id')
        const qs = params.toString()
        const next = `${window.location.pathname}${qs ? `?${qs}` : ''}${window.location.hash || ''}`
        window.history.replaceState({}, '', next)
        setQueryReportApplied(true)
      })
  }, [authToken, queryReportApplied])

  const restoreVersion = async (ver: number) => {
    if (!proposalId || (!AUTH_DISABLED && !authToken)) { alert('Sign in and create a share link first.'); return }
    try {
      const res = await fetch(`${API}/api/v1/proposals/${proposalId}/versions/${ver}`, { headers: !AUTH_DISABLED && authToken ? { 'Authorization': `Bearer ${authToken}` } : {} })
      if (!res.ok) throw new Error('Failed to load version')
      const data = await res.json()
      applyPayloadToEditor(data?.payload)
      // Auto-create a new version on restore
      await saveVersion()
      alert(`Restored version v${ver} into editor and saved as a new version.`)
    } catch (e: any) {
      alert(e?.message || 'Failed to restore version')
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
          security_protocols: securityProtocols,
          compliance_frameworks: complianceFrameworks,
          additional_assumptions: additionalAssumptions,
          sites,
          overtime,
          period_of_performance: periodOfPerformance,
          estimating_method: estimatingMethod,
          historical_estimates: serializeHistoricalEstimates(),
          raci_matrix: raciMatrix,
          roadmap_phases: roadmapPhases,
          odc_items: odcItems,
          fixed_price_items: fixedPriceItems,
          hardware_subtotal: hardwareSubtotal,
          warranty_months: warrantyMonths,
          warranty_cost: warrantyCost,
          roi_capex_event_cost_low: asNumber(roiCapexLow),
          roi_capex_event_cost_high: asNumber(roiCapexHigh),
          roi_capex_event_interval_months: asNumber(roiCapexIntervalMonths),
          roi_downtime_cost_per_hour: asNumber(roiDowntimeCostPerHour),
          roi_current_availability: asNumber(roiCurrentAvailability),
          roi_target_availability: asNumber(roiTargetAvailability),
          roi_legacy_support_savings_annual: asNumber(roiLegacySupportAnnual),
        })
      })
      if (!estRes.ok) throw new Error('Failed to calculate estimate')
      const estData = await estRes.json()
      setEstimate(estData?.estimation_result || null)

      // 2) Optionally fetch AI narrative
      if (includeAI) {
        const contractUrl = scrapeResult?.success ? (scrapeResult.final_url || scrapeResult.url) : undefined
        const contractExcerpt = scrapeResult?.success ? (scrapeResult.text_excerpt || '') : undefined
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
            security_protocols: securityProtocols,
            compliance_frameworks: complianceFrameworks,
            additional_assumptions: additionalAssumptions,
            sites,
            overtime,
            period_of_performance: periodOfPerformance,
            estimating_method: estimatingMethod,
            historical_estimates: serializeHistoricalEstimates(),
            raci_matrix: raciMatrix,
            roadmap_phases: roadmapPhases,
            odc_items: odcItems,
            fixed_price_items: fixedPriceItems,
            hardware_subtotal: hardwareSubtotal,
            warranty_months: warrantyMonths,
            warranty_cost: warrantyCost,
            roi_capex_event_cost_low: asNumber(roiCapexLow),
            roi_capex_event_cost_high: asNumber(roiCapexHigh),
            roi_capex_event_interval_months: asNumber(roiCapexIntervalMonths),
            roi_downtime_cost_per_hour: asNumber(roiDowntimeCostPerHour),
            roi_current_availability: asNumber(roiCurrentAvailability),
            roi_target_availability: asNumber(roiTargetAvailability),
            roi_legacy_support_savings_annual: asNumber(roiLegacySupportAnnual),
            contract_url: contractUrl,
            contract_excerpt: contractExcerpt,
            style_guide: styleGuide || undefined,
            tone,
            sections: ['executive_summary','assumptions','risks']
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
          risks: ''
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

  const openPreviewPage = () => {
    const id = (previewIdInput || '').trim()
    if (!id) { alert('Enter a public preview ID.'); return }
    const url = `/preview/${encodeURIComponent(id)}`
    window.open(url, '_blank')
  }

  const clearAll = () => {
    setSelectedModules([])
    setComplexity('M')
    setIncludeAI(true)
    setTone('professional')
    setStyleGuide('')
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
    setSecurityProtocols('')
    setComplianceFrameworks('')
    setAdditionalAssumptions('')
    setSites(1)
    setOvertime(false)
    setPeriodOfPerformance('')
    setEstimatingMethod('engineering')
    setHistoricalEstimates([])
    setRaciMatrix(DEFAULT_RACI_ROWS.map((row) => ({ ...row })))
    setRoadmapPhases(DEFAULT_ROADMAP_PHASES.map((row) => ({ ...row })))
    setRoiCapexLow('')
    setRoiCapexHigh('')
    setRoiCapexIntervalMonths('')
    setRoiDowntimeCostPerHour('')
    setRoiCurrentAvailability('')
    setRoiTargetAvailability('')
    setRoiLegacySupportAnnual('')
    setOdcItems([])
    setFixedPriceItems([])
    setHardwareSubtotal(0)
    setWarrantyMonths(0)
    setWarrantyCost(0)
    setNarrativeSectionBusy(null)
    setNarrativeSectionError(null)
    setAssumptionsBusy(false)
    setAssumptionsError(null)
    setCommentsBusy(false)
    setCommentsError(null)
    setSecurityBusy(false)
    setSecurityError(null)
    setComplianceBusy(false)
    setComplianceError(null)
  }

  if (shouldEnforceAuth && !authChecked) {
    return (
      <div className="app app-shell">
        <h1>Estimation Tool</h1>
        <p>Checking authentication...</p>
      </div>
    )
  }

  if (shouldEnforceAuth && !isAuthenticated) {
    return (
      <div className="app auth-screen">
        <div style={{ maxWidth: 480, width: '100%', padding: 24, border: '1px solid #ddd', borderRadius: 8, boxShadow: '0 2px 6px rgba(0,0,0,0.04)' }}>
          <h1>Estimation Tool</h1>
          <p style={{ marginBottom: 16 }}>Sign in or sign up to access the estimation workspace.</p>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <button
              className="btn"
              onClick={() => {
                setAuthMode('signin')
                setLoginError(null)
                setSignupError(null)
                setSignupInfo(null)
              }}
              style={{
                padding: '6px 12px',
                fontWeight: authMode === 'signin' ? 600 : 400,
                borderBottom: authMode === 'signin' ? '2px solid #1976d2' : '2px solid transparent',
              }}
            >
              Sign in
            </button>
            <button
              className="btn"
              onClick={() => {
                setAuthMode('signup')
                setLoginError(null)
                setSignupError(null)
              }}
              style={{
                padding: '6px 12px',
                fontWeight: authMode === 'signup' ? 600 : 400,
                borderBottom: authMode === 'signup' ? '2px solid #1976d2' : '2px solid transparent',
              }}
            >
              Sign up
            </button>
          </div>
          {authMode === 'signin' ? (
            <>
              {loginError && (
                <p style={{ color: 'crimson', marginBottom: 8 }}>{loginError}</p>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <input
                  type="email"
                  placeholder="email@example.com"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  style={{ padding: 8 }}
                />
                <input
                  type="password"
                  placeholder="Password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  style={{ padding: 8 }}
                />
                <button
                  className="btn btn-primary"
                  onClick={handleLogin}
                  disabled={loginBusy}
                  style={{ padding: '8px 16px' }}
                >
                  {loginBusy ? 'Signing in...' : 'Sign in'}
                </button>
              </div>
            </>
          ) : (
            <>
              {signupError && (
                <p style={{ color: 'crimson', marginBottom: 8 }}>{signupError}</p>
              )}
              {signupInfo && (
                <p style={{ color: '#1b5e20', marginBottom: 8 }}>{signupInfo}</p>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <input
                  type="email"
                  placeholder="email@example.com"
                  value={signupEmail}
                  onChange={(e) => setSignupEmail(e.target.value)}
                  style={{ padding: 8 }}
                  disabled={awaitingVerification}
                />
                <input
                  type="password"
                  placeholder="Password"
                  value={signupPassword}
                  onChange={(e) => setSignupPassword(e.target.value)}
                  style={{ padding: 8 }}
                  disabled={awaitingVerification}
                />
                {!awaitingVerification && (
                  <button
                    className="btn btn-primary"
                    onClick={handleSignup}
                    disabled={signupBusy}
                    style={{ padding: '8px 16px' }}
                  >
                    {signupBusy ? 'Signing up...' : 'Sign up'}
                  </button>
                )}
                {awaitingVerification && (
                  <>
                    <input
                      type="text"
                      placeholder="Verification code"
                      value={signupCode}
                      onChange={(e) => setSignupCode(e.target.value)}
                      style={{ padding: 8 }}
                    />
                    <button
                      className="btn btn-primary"
                      onClick={handleConfirmSignup}
                      disabled={signupBusy}
                      style={{ padding: '8px 16px' }}
                    >
                      {signupBusy ? 'Verifying...' : 'Confirm code'}
                    </button>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="app app-shell">
      <TopNav />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1 }}>
          {readOnly && (
            <div style={{ padding: 8, marginBottom: 12, border: '1px solid #ffcc80', background: '#fff8e1', borderRadius: 6 }}>
              Read‑only shared preview. <a href={shareUrl || '#'} target="_blank" rel="noreferrer">Open share link</a>
            </div>
          )}
          <h1>Estimation Tool</h1>
          <p>
            Backend Status:{' '}
            <strong>{backendStatus}</strong>
          </p>
        </div>
        <div style={{ minWidth: 320, padding: 8, border: '1px solid #eee', borderRadius: 8 }}>
          <div>
            <div style={{ marginBottom: 6 }}>
              {AUTH_DISABLED ? (
                <span>Auth temporarily disabled</span>
              ) : authEmail ? (
                <>Signed in as <strong>{authEmail}</strong></>
              ) : (
                <span>Not signed in</span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {!AUTH_DISABLED && authEmail && (
                <button
                  className="btn"
                  onClick={() => {
                    localStorage.removeItem('auth_token')
                    localStorage.removeItem('auth_email')
                    setAuthToken(null)
                    setAuthEmail(null)
                  }}
                >
                  Sign out
                </button>
              )}
              {!AUTH_DISABLED && IS_LOCALHOST && DEV_STUB_EMAIL && !authEmail && (
                <button
                  className="btn"
                  onClick={handleDevStubLogin}
                  disabled={devLoginBusy}
                >
                  {devLoginBusy ? 'Signing in stub...' : 'Dev: sign in stub user'}
                </button>
              )}
            </div>
            {!AUTH_DISABLED && IS_LOCALHOST && DEV_STUB_EMAIL && !authEmail && (
              <div style={{ marginTop: 4, fontSize: 11, color: '#666' }}>
                Uses backend dev auth endpoints with {DEV_STUB_EMAIL}.
              </div>
            )}
          </div>
        </div>
      </div>
      
      <section className="form-section">
        <h2>Available Modules</h2>
        {modules.length > 0 ? (
          <div className="modules-grid">
            {modules.map((module: any) => (
              <label key={module.id} className="module-checkbox">
                <input
                  type="checkbox"
                  checked={selectedModules.includes(module.id)}
                  onChange={() => toggleModule(module.id)}
                  disabled={readOnly}
                />
                <span className="module-name">
                  {module.name} ({module.focus_area}) -{' '}
                  {Object.values(module.base_hours_by_role).map(Number).reduce((a, b) => a + b, 0)} base hours
                </span>
              </label>
            ))}
          </div>
        ) : (
          <p>Loading modules...</p>
        )}
        {prereqWarnings.length > 0 && (
          <div style={{ color: '#b26a00', marginTop: 8 }}>
            <strong>Prerequisites missing:</strong>
            <ul>
              {prereqWarnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="form-section">
        <h2>Scope Options</h2>
        <div style={{ marginTop: 16 }}>
          <label>
            Complexity:
            <select
              value={complexity}
              onChange={(e) => setComplexity(e.target.value as any)}
              style={{ marginLeft: 8 }}
              disabled={readOnly}
            >
              <option value="S">Small (S)</option>
              <option value="M">Medium (M)</option>
              <option value="L">Large (L)</option>
              <option value="XL">Extra Large (XL)</option>
            </select>
          </label>
        </div>
      </section>

      <h2 style={{ marginTop: 24 }}>Project Information</h2>
      <div className="form-grid">
        <label>Project Name
          <input value={projectName} onChange={(e) => setProjectName(e.target.value)} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>Fiscal Year (FY)
          <input value={fy} onChange={(e) => setFy(e.target.value)} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>Government POC
          <input value={governmentPOC} onChange={(e) => setGovernmentPOC(e.target.value)} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>Account Manager
          <input value={accountManager} onChange={(e) => setAccountManager(e.target.value)} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>Service Delivery Mgr
          <input value={serviceDeliveryMgr} onChange={(e) => setServiceDeliveryMgr(e.target.value)} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>Service Delivery Exec
          <input value={serviceDeliveryExec} onChange={(e) => setServiceDeliveryExec(e.target.value)} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>Site Location
          <input value={siteLocation} onChange={(e) => setSiteLocation(e.target.value)} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>RAP #
          <input value={rapNumber} onChange={(e) => setRapNumber(e.target.value)} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>PSI Code
          <input value={psiCode} onChange={(e) => setPsiCode(e.target.value)} style={{ width: '100%' }} disabled={readOnly} />
        </label>
      </div>
      <div style={{ marginTop: 8 }}>
        <label>Additional Comments
          <textarea value={additionalComments} onChange={(e) => setAdditionalComments(e.target.value)} rows={2} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 6 }}>
          <button className="btn" onClick={generateAdditionalComments} disabled={commentsBusy || readOnly}>
            {commentsBusy ? 'Generating...' : 'Generate from Scrape'}
          </button>
          {commentsError && (
            <span style={{ fontSize: 12, color: 'crimson' }}>{commentsError}</span>
          )}
        </div>
      </div>

      <h2 style={{ marginTop: 24 }}>Security & Compliance</h2>
      <div className="form-grid">
        <label>Security Protocols
          <textarea value={securityProtocols} onChange={(e) => setSecurityProtocols(e.target.value)} rows={2} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>Compliance Frameworks
          <textarea value={complianceFrameworks} onChange={(e) => setComplianceFrameworks(e.target.value)} rows={2} style={{ width: '100%' }} disabled={readOnly} />
        </label>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 6 }}>
        <button className="btn" onClick={generateSecurityProtocols} disabled={securityBusy || readOnly}>
          {securityBusy ? 'Generating...' : 'Generate Security from Scrape'}
        </button>
        {securityError && (
          <span style={{ fontSize: 12, color: 'crimson' }}>{securityError}</span>
        )}
        <button className="btn" onClick={generateComplianceFrameworks} disabled={complianceBusy || readOnly}>
          {complianceBusy ? 'Generating...' : 'Generate Compliance from Scrape'}
        </button>
        {complianceError && (
          <span style={{ fontSize: 12, color: 'crimson' }}>{complianceError}</span>
        )}
      </div>

      <h2 style={{ marginTop: 24 }}>Assumptions</h2>
      <div style={{ marginTop: 8 }}>
        <label>Additional Assumptions
          <textarea value={additionalAssumptions} onChange={(e) => setAdditionalAssumptions(e.target.value)} rows={3} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 6 }}>
          <button className="btn" onClick={generateAdditionalAssumptions} disabled={assumptionsBusy || readOnly}>
            {assumptionsBusy ? 'Generating...' : 'Generate from Scrape'}
          </button>
          {assumptionsError && (
            <span style={{ fontSize: 12, color: 'crimson' }}>{assumptionsError}</span>
          )}
        </div>
        <div style={{ fontSize: 12, color: '#666' }}>
          Used to expand the narrative assumptions section.
        </div>
      </div>

      <h2 style={{ marginTop: 24 }}>Value & ROI Inputs</h2>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
        Used to calculate the 5-year net fiscal benefit summary in the report.
      </div>
      <div className="form-grid">
        <label>Emergency CapEx Event Cost (Low)
          <input type="number" value={roiCapexLow} onChange={(e) => setRoiCapexLow(e.target.value)} style={{ width: '100%' }} disabled={readOnly} placeholder="150000" />
        </label>
        <label>Emergency CapEx Event Cost (High)
          <input type="number" value={roiCapexHigh} onChange={(e) => setRoiCapexHigh(e.target.value)} style={{ width: '100%' }} disabled={readOnly} placeholder="250000" />
        </label>
        <label>CapEx Event Interval (Months)
          <input type="number" value={roiCapexIntervalMonths} onChange={(e) => setRoiCapexIntervalMonths(e.target.value)} style={{ width: '100%' }} disabled={readOnly} placeholder="18" />
        </label>
        <label>Downtime Cost per Hour
          <input type="number" value={roiDowntimeCostPerHour} onChange={(e) => setRoiDowntimeCostPerHour(e.target.value)} style={{ width: '100%' }} disabled={readOnly} placeholder="5000" />
        </label>
        <label>Current Availability (%)
          <input type="number" value={roiCurrentAvailability} onChange={(e) => setRoiCurrentAvailability(e.target.value)} style={{ width: '100%' }} disabled={readOnly} placeholder="99.5" />
        </label>
        <label>Target Availability (%)
          <input type="number" value={roiTargetAvailability} onChange={(e) => setRoiTargetAvailability(e.target.value)} style={{ width: '100%' }} disabled={readOnly} placeholder="99.99" />
        </label>
        <label>Legacy Support Savings (Annual)
          <input type="number" value={roiLegacySupportAnnual} onChange={(e) => setRoiLegacySupportAnnual(e.target.value)} style={{ width: '100%' }} disabled={readOnly} placeholder="75000" />
        </label>
      </div>

      <h2 style={{ marginTop: 24 }}>Roles & Responsibilities (RACI)</h2>
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
              {!readOnly && <th style={{ width: 1 }} />}
            </tr>
          </thead>
          <tbody>
            {raciMatrix.map((row, idx) => (
              <tr key={idx}>
                <td style={{ padding: 6 }}>
                  <input
                    value={row.milestone || ''}
                    onChange={(e) => updateRaciRow(idx, { milestone: e.target.value })}
                    disabled={readOnly}
                    style={{ width: '100%' }}
                  />
                </td>
                <td style={{ padding: 6 }}>
                  <input
                    value={row.responsible || ''}
                    onChange={(e) => updateRaciRow(idx, { responsible: e.target.value })}
                    disabled={readOnly}
                    style={{ width: '100%' }}
                  />
                </td>
                <td style={{ padding: 6 }}>
                  <input
                    value={row.accountable || ''}
                    onChange={(e) => updateRaciRow(idx, { accountable: e.target.value })}
                    disabled={readOnly}
                    style={{ width: '100%' }}
                  />
                </td>
                <td style={{ padding: 6 }}>
                  <input
                    value={row.consulted || ''}
                    onChange={(e) => updateRaciRow(idx, { consulted: e.target.value })}
                    disabled={readOnly}
                    style={{ width: '100%' }}
                  />
                </td>
                <td style={{ padding: 6 }}>
                  <input
                    value={row.informed || ''}
                    onChange={(e) => updateRaciRow(idx, { informed: e.target.value })}
                    disabled={readOnly}
                    style={{ width: '100%' }}
                  />
                </td>
                {!readOnly && (
                  <td style={{ padding: 6 }}>
                    <button className="btn" onClick={() => removeRaciRow(idx)}>Remove</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!readOnly && (
        <button className="btn" style={{ marginTop: 8 }} onClick={addRaciRow}>
          Add RACI Row
        </button>
      )}

      <h2 style={{ marginTop: 24 }}>Future-Proofing Roadmap</h2>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
        Define phased implementation aligned to the 5-10 year strategy.
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {roadmapPhases.map((phase, idx) => (
          <div key={idx} style={{ border: '1px solid #eee', borderRadius: 8, padding: 10, background: '#fafafa' }}>
            <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
              <label>Phase
                <input
                  value={phase.phase || ''}
                  onChange={(e) => updateRoadmapPhase(idx, { phase: e.target.value })}
                  disabled={readOnly}
                />
              </label>
              <label>Timeline
                <input
                  value={phase.timeline || ''}
                  onChange={(e) => updateRoadmapPhase(idx, { timeline: e.target.value })}
                  disabled={readOnly}
                />
              </label>
              <label>Title
                <input
                  value={phase.title || ''}
                  onChange={(e) => updateRoadmapPhase(idx, { title: e.target.value })}
                  disabled={readOnly}
                />
              </label>
            </div>
            <label style={{ marginTop: 8, display: 'block' }}>Description
              <textarea
                value={phase.description || ''}
                onChange={(e) => updateRoadmapPhase(idx, { description: e.target.value })}
                disabled={readOnly}
                rows={2}
                style={{ width: '100%' }}
              />
            </label>
          </div>
        ))}
      </div>

      <h2 style={{ marginTop: 24 }}>Scope Options</h2>
      <div className="form-grid">
        <label>Number of Sites
          <input type="number" min={1} value={sites} onChange={(e) => setSites(Math.max(1, parseInt(e.target.value || '1')))} style={{ width: 100, marginLeft: 8 }} disabled={readOnly} />
        </label>
        <label>Period of Performance
          <input value={periodOfPerformance} onChange={(e) => setPeriodOfPerformance(e.target.value)} style={{ width: '100%' }} disabled={readOnly} placeholder="e.g., 12 months from award" />
        </label>
        <label>
          <input type="checkbox" checked={overtime} onChange={(e) => setOvertime(e.target.checked)} style={{ marginRight: 8 }} disabled={readOnly} />
          Overtime Required
        </label>
      </div>

      <h2 style={{ marginTop: 24 }}>Subtask Estimating Method</h2>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <input
            type="radio"
            name="estimating-method"
            checked={estimatingMethod === 'engineering'}
            onChange={() => setEstimatingMethod('engineering')}
            disabled={readOnly}
          />
          Engineering Discrete
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <input
            type="radio"
            name="estimating-method"
            checked={estimatingMethod === 'historical'}
            onChange={() => setEstimatingMethod('historical')}
            disabled={readOnly}
          />
          Historical Actuals
        </label>
      </div>
      {estimatingMethod === 'historical' && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
            Select past wins to scale hours and rates for module subtasks.
          </div>
          {historicalEstimates.length > 0 ? (
            historicalEstimates.map((item, idx) => (
              <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <input
                    type="checkbox"
                    checked={item.selected}
                    onChange={(e) => updateHistoricalEstimate(idx, { selected: e.target.checked })}
                    disabled={readOnly}
                  />
                  Use
                </label>
                <input
                  placeholder="Historical win name"
                  value={item.name}
                  onChange={(e) => updateHistoricalEstimate(idx, { name: e.target.value })}
                  style={{ minWidth: 200, flex: 1 }}
                  disabled={readOnly}
                />
                <input
                  type="number"
                  placeholder="Actual Hours"
                  value={item.actual_hours}
                  onChange={(e) => updateHistoricalEstimate(idx, { actual_hours: e.target.value })}
                  style={{ width: 140 }}
                  disabled={readOnly}
                />
                <input
                  type="number"
                  placeholder="Actual Total Cost"
                  value={item.actual_total_cost}
                  onChange={(e) => updateHistoricalEstimate(idx, { actual_total_cost: e.target.value })}
                  style={{ width: 160 }}
                  disabled={readOnly}
                />
                {!readOnly && (
                  <button className="btn" onClick={() => removeHistoricalEstimate(idx)}>Remove</button>
                )}
              </div>
            ))
          ) : (
            <div style={{ fontSize: 12, color: '#666' }}>No historical wins added yet.</div>
          )}
          {!readOnly && (
            <button className="btn" onClick={addHistoricalEstimate} style={{ marginTop: 6 }}>
              Add Historical Win
            </button>
          )}
        </div>
      )}

      <h2 style={{ marginTop: 24 }}>Other Costs</h2>
      <div className="form-grid">
        <label>Hardware Subtotal ($)
          <input type="number" min={0} value={hardwareSubtotal} onChange={(e) => setHardwareSubtotal(Number(e.target.value || 0))} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <div />
        <label>Warranty Months
          <input type="number" min={0} value={warrantyMonths} onChange={(e) => setWarrantyMonths(Number(e.target.value || 0))} style={{ width: '100%' }} disabled={readOnly} />
        </label>
        <label>Warranty Cost ($)
          <input type="number" min={0} value={warrantyCost} onChange={(e) => setWarrantyCost(Number(e.target.value || 0))} style={{ width: '100%' }} disabled={readOnly} />
        </label>
      </div>

      <div style={{ marginTop: 12 }}>
        <h3>Other Direct Costs</h3>
        {odcItems.map((item, idx) => (
          <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <input placeholder="Description" value={item.description} onChange={(e) => setOdcItems(prev => prev.map((x, i) => i===idx ? { ...x, description: e.target.value } : x))} style={{ flex: 1 }} disabled={readOnly} />
            <input placeholder="Price" type="number" min={0} value={item.price} onChange={(e) => setOdcItems(prev => prev.map((x, i) => i===idx ? { ...x, price: Number(e.target.value || 0) } : x))} style={{ width: 140 }} disabled={readOnly} />
            {!readOnly && (
              <button
                className="btn"
                onClick={() => setOdcItems(prev => prev.filter((_, i) => i!==idx))}
              >
                Remove
              </button>
            )}
          </div>
        ))}
        {!readOnly && (
          <button
            className="btn"
            onClick={() => setOdcItems(prev => [...prev, { description: '', price: 0 }])}
          >
            Add ODC Item
          </button>
        )}
      </div>

      <div style={{ marginTop: 12 }}>
        <h3>Fixed-Price Items</h3>
        {fixedPriceItems.map((item, idx) => (
          <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <input placeholder="Description" value={item.description} onChange={(e) => setFixedPriceItems(prev => prev.map((x, i) => i===idx ? { ...x, description: e.target.value } : x))} style={{ flex: 1 }} disabled={readOnly} />
            <input placeholder="Price" type="number" min={0} value={item.price} onChange={(e) => setFixedPriceItems(prev => prev.map((x, i) => i===idx ? { ...x, price: Number(e.target.value || 0) } : x))} style={{ width: 140 }} disabled={readOnly} />
            {!readOnly && (
              <button
                className="btn"
                onClick={() => setFixedPriceItems(prev => prev.filter((_, i) => i!==idx))}
              >
                Remove
              </button>
            )}
          </div>
        ))}
        {!readOnly && (
          <button
            className="btn"
            onClick={() => setFixedPriceItems(prev => [...prev, { description: '', price: 0 }])}
          >
            Add Fixed-Price Item
          </button>
        )}
      </div>

      <h2>Quick Test Calculation</h2>
      <button
        className="btn btn-primary"
        onClick={() => {
        fetch(`${API}/api/v1/calculate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ base_hours: 100, complexity: 'M' })
        })
        .then(res => res.json())
        .then(data => alert(`Estimated cost: $${data.total_cost}`))
        .catch(() => alert('Calculation failed'))
      }}>
        Test Calculation (100 hours, Medium complexity)
      </button>

      <h2 style={{ marginTop: 24 }}>Contract URL Scraper (beta)</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 680 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            placeholder="https://example.gov/contracts/solicitation-1234"
            value={scrapeUrl}
            onChange={(e) => setScrapeUrl(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={runScrapeTest}
            disabled={scrapeLoading}
          >
            {scrapeLoading ? 'Scraping...' : 'Scrape URL'}
          </button>
        </div>
        {!isAuthenticated && (
          <div style={{ fontSize: 12, color: '#b26a00' }}>
            Sign in to run authenticated scraping calls.
          </div>
        )}
        {scrapeError && (
          <div style={{ fontSize: 12, color: 'crimson' }}>
            {scrapeError}
          </div>
        )}
        {scrapeResult && (
          <div style={{ border: '1px solid #ddd', borderRadius: 6, padding: 8, background: '#fafafa' }}>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              <div><strong>URL:</strong> {scrapeResult.url}</div>
              {scrapeResult.final_url && scrapeResult.final_url !== scrapeResult.url && (
                <div><strong>Final URL:</strong> {scrapeResult.final_url}</div>
              )}
              <div>
                <strong>Status:</strong>{' '}
                {scrapeResult.success ? `OK (${scrapeResult.status_code ?? 'n/a'})` : 'Failed'}
                {scrapeResult.truncated && ' · truncated'}
              </div>
              {scrapeResult.content_type && (
                <div><strong>Content-Type:</strong> {scrapeResult.content_type}</div>
              )}
            </div>
            {scrapeResult.error && (
              <div style={{ fontSize: 12, color: '#b26a00', marginBottom: 4 }}>
                {scrapeResult.error}
              </div>
            )}
            <div style={{ maxHeight: 200, overflow: 'auto', padding: 6, background: '#fff', borderRadius: 4, border: '1px solid #eee' }}>
              <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                {scrapeResult.text_excerpt || '(no text extracted)'}
              </pre>
            </div>
          </div>
        )}
      </div>

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
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
        <label>
          Proposal ID (optional):
          <input
            type="text"
            value={proposalId || ''}
            onChange={(e) => setProposalId(e.target.value || null)}
            placeholder="prop_abc123"
            style={{ marginLeft: 6, padding: '4px 6px', minWidth: 200 }}
          />
        </label>
        {overwriteReportId && (
          <div style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: '#555' }}>Overwrite target: {overwriteReportId}</span>
            <button className="btn" onClick={() => setOverwriteReportId(null)}>
              Clear
            </button>
          </div>
        )}
        <div style={{ fontSize: 12, color: '#555' }}>
          Selected modules + scraped excerpt drive the subtask section in the PDF.
        </div>
      </div>
      {reportLoadNotice && (
        <div style={{ marginBottom: 8, fontSize: 12, color: '#1b5e20' }}>
          {reportLoadNotice}
        </div>
      )}

      <div style={{ border: '1px dashed #ccc', borderRadius: 6, padding: 10, marginBottom: 12, background: '#fafafa' }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>Subtask context preview</div>
        <div style={{ fontSize: 13, marginBottom: 4 }}>
          <strong>Modules:</strong>{' '}
          {selectedModules.length > 0
            ? modules
                .filter((m) => selectedModules.includes(m.id))
                .map((m) => m.name)
                .join(', ')
            : 'Choose modules above to seed subtasks.'}
        </div>
        <div style={{ fontSize: 13 }}>
          <strong>Contract excerpt:</strong>{' '}
          {scrapeResult?.success
            ? (scrapeResult.text_excerpt || '(no text extracted)').slice(0, 400) +
              ((scrapeResult.text_excerpt || '').length > 400 ? '...' : '')
            : 'Scrape the contract URL to embed customer context into the subtask descriptions.'}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <button className="btn btn-primary" onClick={previewReport} disabled={previewLoading || readOnly}>
          {previewLoading ? 'Building Preview...' : 'Preview Report'}
        </button>
        <button className="btn btn-primary" onClick={saveReportToServer} disabled={downloading}>
          {downloading ? 'Saving...' : 'Save Report to Server'}
        </button>
        <button className="btn" onClick={previewNarrative} disabled={loadingNarrative}>
          {loadingNarrative ? 'Regenerating Narrative...' : 'Regenerate Narrative'}
        </button>
        <button className="btn" onClick={previewSubtasks} disabled={subtaskLoading}>
          {subtaskLoading ? 'Building Subtasks...' : 'Preview Subtasks'}
        </button>
        {!readOnly && (
          <button className="btn" onClick={clearAll}>
            Clear Inputs
          </button>
        )}
        {!readOnly && (
          <button className="btn" onClick={saveDraftLocal}>
            Save Draft
          </button>
        )}
        {!readOnly && (
          <button className="btn" onClick={loadDraftLocal}>
            Load Draft
          </button>
        )}
        {!readOnly && (
          <button className="btn" onClick={exportDraft}>
            Export JSON
          </button>
        )}
        {!readOnly && (
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <input type="file" accept="application/json" onChange={(e) => { const f = e.target.files?.[0]; if (f) importDraft(f); e.currentTarget.value = '' }} />
            Import JSON
          </label>
        )}
        {!readOnly && (
          <button className="btn" onClick={createShareLink}>
            Create Share Link
          </button>
        )}
        {!readOnly && (
          <button className="btn" onClick={initializeProposal} disabled={initBusy || !!proposalId}>
            {initBusy ? 'Initializing...' : (proposalId ? 'Proposal Initialized' : 'Initialize Proposal')}
          </button>
        )}
        <div style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
          <label>
            Public preview ID:
            <input
              type="text"
              value={previewIdInput}
              onChange={(e) => setPreviewIdInput(e.target.value)}
              placeholder="public id"
              style={{ marginLeft: 6, padding: '4px 6px', minWidth: 160 }}
            />
          </label>
          <button className="btn" onClick={openPreviewPage}>
            Open Preview
          </button>
        </div>
        {!readOnly && (
          <button className="btn" onClick={saveVersion}>
            Save Version
          </button>
        )}
        {readOnly && sharePublicId && (
          <a href={`/preview/${sharePublicId}`} style={{ alignSelf: 'center' }}>Open Preview Page</a>
        )}
        {readOnly && shareUrl && (
          <button className="btn" onClick={() => { navigator.clipboard.writeText(shareUrl) }}>
            Copy Share Link
          </button>
        )}
        {!readOnly && sharePublicId && (
          <span style={{ marginLeft: 8, fontSize: 12, color: '#555' }}>
            Preview: <a href={`/preview/${sharePublicId}`} target="_blank" rel="noreferrer">/preview/{sharePublicId}</a>
          </span>
        )}
      </div>

      <h2 style={{ marginTop: 24 }}>Narrative</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
        <button
          className="btn btn-primary"
          onClick={previewNarrative}
          disabled={loadingNarrative || readOnly}
        >
          {loadingNarrative ? 'Generating...' : 'Generate Narrative'}
        </button>
        {!readOnly && (
          <button className="btn" onClick={() => setEditableNarrative({})}>
            Clear Narrative
          </button>
        )}
      </div>
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontWeight: 600 }}>Style guide (optional)</label>
        <textarea
          value={styleGuide}
          onChange={(e) => setStyleGuide(e.target.value)}
          rows={3}
          style={{ width: '100%', padding: 8, fontFamily: 'inherit' }}
          disabled={readOnly}
          placeholder="e.g., concise, active voice, avoid jargon; use client-ready tone"
        />
        <div style={{ fontSize: 12, color: '#666' }}>
          Used when AI generates or rewrites narrative sections.
        </div>
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
            <h4>Subtask Preview</h4>
            {subtaskLoading && <div style={{ fontSize: 12 }}>Building subtasks...</div>}
            {subtaskError && <div style={{ fontSize: 12, color: 'crimson' }}>{subtaskError}</div>}
            {subtaskStatus && <div style={{ fontSize: 12, color: '#555' }}>Status: {subtaskStatus}</div>}
            {subtaskPreview && subtaskPreview.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
                {subtaskPreview.map((st: any, idx: number) => (
                  <div key={idx} style={{ border: '1px solid #ddd', borderRadius: 6, padding: 10, background: '#fafafa' }}>
                    <div style={{ fontWeight: 600 }}>{st.sequence || idx + 1}. {st.module_name} ({st.focus_area})</div>
                    <div style={{ fontSize: 12, marginTop: 4 }}><strong>Work Scope:</strong> {st.work_scope}</div>
                    <div style={{ fontSize: 12, marginTop: 2 }}><strong>Estimate Basis:</strong> {st.estimate_basis}</div>
                    <div style={{ fontSize: 12, marginTop: 2 }}><strong>Period of Performance:</strong> {st.period_of_performance}</div>
                    {st.security_protocols && <div style={{ fontSize: 12, marginTop: 2 }}><strong>Security Protocols:</strong> {st.security_protocols}</div>}
                    {st.compliance_frameworks && <div style={{ fontSize: 12, marginTop: 2 }}><strong>Compliance Frameworks:</strong> {st.compliance_frameworks}</div>}
                    {st.customer_context && <div style={{ fontSize: 12, marginTop: 2 }}><strong>Context:</strong> {st.customer_context}</div>}
                    <div style={{ marginTop: 6 }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Task</th>
                            <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Calc</th>
                            <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 4 }}>Hours</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(st.tasks || []).map((t: any, ix: number) => (
                            <tr key={ix}>
                              <td style={{ padding: 4 }}>{t.title}</td>
                              <td style={{ padding: 4 }}>{t.calculation}</td>
                              <td style={{ padding: 4, textAlign: 'right' }}>{Number(t.hours || 0).toFixed(1)}</td>
                            </tr>
                          ))}
                          <tr>
                            <td style={{ padding: 4, fontWeight: 600 }}>Subtask Total</td>
                            <td />
                            <td style={{ padding: 4, textAlign: 'right', fontWeight: 600 }}>{Number(st.total_hours || 0).toFixed(1)}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            ) : !subtaskLoading && <div style={{ fontSize: 12, color: '#666' }}>No subtasks previewed yet.</div>}
            {subtaskRaw && (
              <details style={{ marginTop: 8 }}>
                <summary style={{ cursor: 'pointer', fontSize: 12 }}>Raw AI response</summary>
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: 11, background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                  {subtaskRaw}
                </pre>
              </details>
            )}
          </div>

          <div style={{ marginTop: 16 }}>
            <h4>Editable Narrative</h4>
            {narrativeSectionError && (
              <div style={{ fontSize: 12, color: 'crimson', marginBottom: 6 }}>
                {narrativeSectionError}
              </div>
            )}
            {['executive_summary','assumptions','risks'].map((k) => (
              <div key={k} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <label style={{ display: 'block', fontWeight: 600 }}>{k.replace('_',' ').toUpperCase()}</label>
                  <button
                    className="btn"
                    onClick={() => rewriteNarrativeSection(k)}
                    disabled={readOnly || narrativeSectionBusy === k}
                  >
                    {narrativeSectionBusy === k ? 'Regenerating...' : 'Regenerate'}
                  </button>
                </div>
                <textarea
                  value={editableNarrative?.[k] || ''}
                  onChange={(e) => setEditableNarrative(prev => ({ ...prev, [k]: e.target.value }))}
                  rows={4}
                  style={{ width: '100%', padding: 8, fontFamily: 'inherit' }}
                  disabled={readOnly}
                  placeholder={`Write ${k.replace('_',' ')}...`}
                />
                <div style={{ fontSize: 12, color: '#666', textAlign: 'right' }}>{countWords(editableNarrative?.[k] || '')} words</div>
              </div>
            ))}
          </div>
        </div>
      )}
      {!proposalId && (
        <div style={{ marginTop: 24, fontSize: 12, color: '#666' }}>
          Create a share link or enter a Proposal ID to save new versions and reports.
        </div>
      )}
      {proposalId && (AUTH_DISABLED || authToken) && (
        <div style={{ marginTop: 24 }}>
          <h4>Versions</h4>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
            <button className="btn" onClick={loadVersions}>Refresh</button>
            <span style={{ fontSize: 12, color: '#666' }}>{versions.length} version(s)</span>
          </div>
          {versions.length === 0 ? (
            <div style={{ fontSize: 12, color: '#777' }}>{versionsLoaded ? 'No versions yet.' : 'Loading...'}</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Version</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Title</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Created</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {versions.map(v => (
                  <tr key={v.id}>
                    <td style={{ padding: 6 }}>v{v.version}</td>
                    <td style={{ padding: 6 }}>{v.title || '-'}</td>
                    <td style={{ padding: 6 }}>{v.created_at || '-'}</td>
                    <td style={{ padding: 6 }}>
                      <button className="btn" onClick={() => restoreVersion(v.version)}>Restore</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      {(AUTH_DISABLED || authToken) && (
        <div style={{ marginTop: 24 }}>
          <h4>Reports</h4>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
            <button className="btn" onClick={loadReportDocs}>Refresh</button>
            <span style={{ fontSize: 12, color: '#666' }}>{reportDocs.length} report(s)</span>
            <label style={{ fontSize: 12, color: '#666' }}>
              Scope:
              <select
                value={reportScope}
                onChange={(e) => setReportScope(e.target.value as 'all' | 'proposal')}
                style={{ marginLeft: 6, padding: '4px 6px' }}
              >
                <option value="all">All proposals</option>
                <option value="proposal" disabled={!proposalId}>Current proposal</option>
              </select>
            </label>
            {reportsError && <span style={{ fontSize: 12, color: 'crimson' }}>{reportsError}</span>}
          </div>
          {reportDocs.length === 0 ? (
            <div style={{ fontSize: 12, color: '#777' }}>{reportsLoaded ? 'No reports saved yet.' : 'Loading...'}</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Proposal</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Created</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Created By</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Tool Version</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Proposal Version</th>
                  <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Total Cost</th>
                  <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 6 }}>Total Hours</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>AI</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>PDF</th>
                  <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 6 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {reportDocs.map((doc: any) => (
                  <tr key={doc.id}>
                    <td style={{ padding: 6 }}>
                      <div style={{ fontWeight: 600 }}>{doc.proposal_title || 'Untitled Proposal'}</div>
                      <div style={{ fontSize: 11, color: '#777' }}>
                        {doc.proposal_public_id ? (
                          <a href={`/preview/${doc.proposal_public_id}`} target="_blank" rel="noreferrer">/preview/{doc.proposal_public_id}</a>
                        ) : doc.proposal_id ? (
                          <span>ID: {doc.proposal_id}</span>
                        ) : (
                          <span>-</span>
                        )}
                      </div>
                    </td>
                    <td style={{ padding: 6 }}>{doc.created_at || '-'}</td>
                    <td style={{ padding: 6 }}>{doc.created_by || '-'}</td>
                    <td style={{ padding: 6 }}>{doc.tool_version || '-'}</td>
                    <td style={{ padding: 6 }}>{doc.proposal_version != null ? `v${doc.proposal_version}` : '-'}</td>
                    <td style={{ padding: 6, textAlign: 'right' }}>
                      {doc.total_cost != null ? `$${Number(doc.total_cost).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '-'}
                    </td>
                    <td style={{ padding: 6, textAlign: 'right' }}>
                      {doc.total_hours != null ? Number(doc.total_hours).toLocaleString(undefined, { maximumFractionDigits: 1 }) : '-'}
                    </td>
                    <td style={{ padding: 6 }}>{doc.include_ai ? 'Yes' : 'No'}</td>
                    <td style={{ padding: 6 }}>
                      {doc.url ? (
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          <a href={doc.url} target="_blank" rel="noreferrer">Open PDF</a>
                          <a className="btn" href={doc.url} download>Download</a>
                        </div>
                      ) : (
                        <span style={{ fontSize: 12, color: '#777' }}>No link</span>
                      )}
                      <div style={{ fontSize: 11, color: '#777' }}>
                        {doc.filename || 'report.pdf'} - {formatBytes(doc.size_bytes)}
                      </div>
                    </td>
                    <td style={{ padding: 6 }}>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        <button className="btn" onClick={() => loadSavedReportPayload(doc.id, null)}>Load</button>
                        <button className="btn" onClick={() => loadSavedReportPayload(doc.id, doc.id)}>Load + Overwrite</button>
                        <button className="btn" onClick={() => deleteReport(doc)}>Delete</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

export default App
