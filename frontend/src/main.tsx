import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App'
import Preview from './preview'
import Subcontractors from './Subcontractors'
import Contracts from './Contracts'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/subcontractors" element={<Subcontractors />} />
        <Route path="/contracts" element={<Contracts />} />
        <Route path="/preview/:id" element={<Preview />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
