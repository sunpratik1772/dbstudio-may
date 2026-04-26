/**
 * Vite entry point. Mounts <App /> into #root and pulls in the
 * Tailwind/global-CSS bundle. Kept boring on purpose — all routing
 * and state lives one level down (App.tsx + workflowStore).
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './styles/globals.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
