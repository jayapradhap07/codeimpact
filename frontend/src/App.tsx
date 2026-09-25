import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import RepositoryPage from './pages/Repository'
import AnalysisPage from './pages/Analysis'
import GraphExplorer from './pages/GraphExplorer'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/repository" element={<RepositoryPage />} />
        <Route path="/analysis" element={<AnalysisPage />} />
        <Route path="/graph" element={<GraphExplorer />} />
      </Routes>
    </Layout>
  )
}

export default App
