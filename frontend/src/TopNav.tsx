import { NavLink } from 'react-router-dom'
import './App.css'

const NAV_ITEMS = [
  { to: '/', label: 'Estimator', end: true },
  { to: '/subcontractors', label: 'Subcontractors' },
  { to: '/contracts', label: 'Contract Stats' },
]

export default function TopNav() {
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
      {showBadge && (
        <span className={`env-badge env-badge--${normalizedEnv}`}>
          {badgeLabel}
        </span>
      )}
    </nav>
  )
}
