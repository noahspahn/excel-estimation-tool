import { NavLink } from 'react-router-dom'
import './App.css'

const NAV_ITEMS = [
  { to: '/', label: 'Estimator', end: true },
  { to: '/reports', label: 'Saved Reports' },
  { to: '/subcontractors', label: 'Subcontractors' },
  { to: '/contracts', label: 'Contract Stats' },
]

export default function TopNav() {
  const appVersion =
    typeof __APP_VERSION__ !== 'undefined' && __APP_VERSION__ ? __APP_VERSION__ : ''
  const rawEnv = String((import.meta as any).env?.VITE_APP_ENV ?? '').trim().toLowerCase()
  const modeEnv = String((import.meta as any).env?.MODE ?? '').trim().toLowerCase()
  const normalizedEnv = (() => {
    if (!rawEnv && modeEnv === 'development') return 'dev'
    if (rawEnv === 'development') return 'dev'
    if (rawEnv === 'staging') return 'stage'
    if (rawEnv === 'production') return 'prod'
    return rawEnv
  })()
  const showBadge = normalizedEnv === 'dev' || normalizedEnv === 'stage'
  const badgeLabel = normalizedEnv === 'stage' ? 'Stage' : 'Dev'

  return (
    <nav className="top-nav">
      <div className="top-nav__links">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `top-nav__link${isActive ? ' active' : ''}`}
          >
            {item.label}
          </NavLink>
        ))}
      </div>
      <div className="top-nav__meta">
        {showBadge && (
          <span className={`env-badge env-badge--${normalizedEnv}`}>
            {badgeLabel}
          </span>
        )}
        {appVersion && (
          <span className="app-version">
            {appVersion}
          </span>
        )}
      </div>
    </nav>
  )
}
