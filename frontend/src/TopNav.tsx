import { NavLink } from 'react-router-dom'
import './App.css'

const NAV_ITEMS = [
  { to: '/', label: 'Estimator', end: true },
  { to: '/subcontractors', label: 'Subcontractors' },
  { to: '/contracts', label: 'Contract Stats' },
]

export default function TopNav() {
  return (
    <nav className="top-nav">
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
    </nav>
  )
}
