import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { initMonitoring } from './lib/monitoring'
import { ErrorBoundary } from './components/ErrorBoundary'
import { CrashScreen } from './components/CrashScreen'
import './index.css'

initMonitoring()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary fallback={<CrashScreen />}>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
