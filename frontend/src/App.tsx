import React, { useState, useEffect } from 'react'

function App() {
  const [backendStatus, setBackendStatus] = useState('Checking...')
  const [modules, setModules] = useState([])

  useEffect(() => {
    // Test backend connection
    fetch('http://localhost:8000/health')
      .then(res => res.json())
      .then(data => setBackendStatus(data.status || 'Connected'))
      .catch(() => setBackendStatus('Backend not connected'))

    // Fetch modules
    fetch('http://localhost:8000/api/v1/modules')
      .then(res => res.json())
      .then(data => setModules(data.modules || []))
      .catch(err => console.error('Failed to fetch modules:', err))
  }, [])

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>Estimation Tool</h1>
      <p>Backend Status: <strong>{backendStatus}</strong></p>
      
      <h2>Available Modules</h2>
      {modules.length > 0 ? (
        <ul>
          {modules.map((module: any) => (
            <li key={module.id}>
              {module.name} ({module.focus_area}) - {module.base_hours} hours
            </li>
          ))}
        </ul>
      ) : (
        <p>Loading modules...</p>
      )}

      <h2>Quick Test Calculation</h2>
      <button onClick={() => {
        fetch('http://localhost:8000/api/v1/calculate', {
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
    </div>
  )
}

export default App