import { Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { ws } from './api/websocket'
import { useStore } from './stores/run-store'
import Shell from './components/Shell'
import HomePage from './pages/HomePage'
import NewRunPage from './pages/NewRunPage'
import DashboardPage from './pages/DashboardPage'
import ResultsPage from './pages/ResultsPage'

export default function App() {
  const dispatch = useStore((s) => s.dispatch)

  useEffect(() => {
    ws.connect(dispatch)
    return () => ws.disconnect()
  }, [dispatch])

  return (
    <Shell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/new" element={<NewRunPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/results" element={<ResultsPage />} />
      </Routes>
    </Shell>
  )
}
