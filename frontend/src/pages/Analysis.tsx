import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Zap, Loader2, FileCode, AlertTriangle, CheckCircle2,
  XCircle, FlaskConical, Globe, ArrowRight, ShieldCheck
} from 'lucide-react'
import { api } from '../services/api'
import type { Repository, ImpactReport, RiskLevel } from '../types'

export default function AnalysisPage() {
  const location = useLocation()
  const [repos, setRepos] = useState<Repository[]>([])
  const [selectedRepo, setSelectedRepo] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [report, setReport] = useState<ImpactReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    api.listRepositories().then((res) => {
      const readyRepos = res.repositories.filter((r) => r.status === 'ready')
      setRepos(readyRepos)

      const state = location.state as { repoId?: number; query?: string } | null
      if (state?.repoId) {
        setSelectedRepo(state.repoId)
      } else if (readyRepos.length > 0) {
        setSelectedRepo(readyRepos[0].id)
      }

      if (state?.query) {
        setQuery(state.query)
      }
    }).catch(() => {})
  }, [location.state])

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedRepo || !query.trim()) return

    setLoading(true)
    setError(null)
    setReport(null)

    try {
      const result = await api.runImpactAnalysis({
        repo_id: selectedRepo,
        query: query.trim(),
      })
      setReport(result)
    } catch (err: any) {
      setError(err.message || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const riskIcon = (level: RiskLevel) => {
    switch (level) {
      case 'critical': return '🔴'
      case 'high': return '🟠'
      case 'medium': return '🟡'
      case 'low': return '🟢'
    }
  }

  return (
    <>
      <div className="page-header">
        <h2>Impact Analysis</h2>
        <p>Describe a code change and discover its ripple effects across the codebase</p>
      </div>

      {/* Change Request Form */}
      <motion.div className="glass-card" style={{ padding: 28, marginBottom: 28 }} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <form onSubmit={handleAnalyze}>
          <div style={{ display: 'grid', gridTemplateColumns: '250px 1fr auto', gap: 16, alignItems: 'end' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Repository</label>
              <select
                className="form-input"
                value={selectedRepo || ''}
                onChange={(e) => setSelectedRepo(Number(e.target.value))}
                style={{ appearance: 'auto' }}
              >
                <option value="">Select repository...</option>
                {repos.map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Change Description</label>
              <input
                className="form-input"
                type="text"
                placeholder='e.g. "I want to modify the authenticate() function"'
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !selectedRepo || !query.trim()}
              style={{ height: 46 }}
            >
              {loading ? (
                <Loader2 size={18} style={{ animation: 'spin 0.8s linear infinite' }} />
              ) : (
                <Zap size={18} />
              )}
              {loading ? 'Analyzing...' : 'Analyze Impact'}
            </button>
          </div>
        </form>
      </motion.div>

      {/* Error */}
      {error && (
        <motion.div className="glass-card" style={{ padding: 20, marginBottom: 20, borderLeft: '3px solid var(--risk-critical)' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--risk-critical)' }}>
            <XCircle size={18} />
            <span style={{ fontWeight: 600 }}>Analysis Failed</span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: 6 }}>{error}</p>
        </motion.div>
      )}

      {/* Loading animation */}
      <AnimatePresence>
        {loading && (
          <motion.div className="glass-card" style={{ padding: 32, textAlign: 'center' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="spinner" style={{ margin: '0 auto 20px' }} />
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Running 12-Step Impact Analysis...</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Searching → Analyzing Dependencies → RAG Retrieval → AI Reasoning → Verification
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Report */}
      <AnimatePresence>
        {report && !loading && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>

            {/* Risk Overview */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>
                    Change Impact Report
                  </div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>{report.changed_component}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>{report.query}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span className={`risk-badge ${report.risk_level}`} style={{ fontSize: '0.85rem', padding: '6px 16px' }}>
                    {riskIcon(report.risk_level)} {report.risk_level}
                  </span>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 6 }}>
                    Score: {(report.risk_score * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              {/* Quick stats */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
                {[
                  { label: 'Affected Files', value: report.affected_files.length, icon: FileCode, color: 'var(--accent-blue)' },
                  { label: 'Affected Functions', value: report.affected_functions.length, icon: Zap, color: 'var(--accent-violet)' },
                  { label: 'API Impacts', value: report.api_impacts.length, icon: Globe, color: 'var(--accent-amber)' },
                  { label: 'Tests Recommended', value: report.test_recommendations.length, icon: FlaskConical, color: 'var(--accent-emerald)' },
                ].map(({ label, value, icon: Icon, color }) => (
                  <div key={label} style={{ padding: 14, background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
                    <Icon size={18} color={color} style={{ marginBottom: 6 }} />
                    <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{value}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{label}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Tabs */}
            <div className="tabs">
              {['overview', 'files', 'functions', 'tests', 'evidence', 'verification'].map((tab) => (
                <button key={tab} className={`tab ${activeTab === tab ? 'active' : ''}`} onClick={() => setActiveTab(tab)}>
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="glass-card" style={{ padding: 24 }}>

              {/* Overview */}
              {activeTab === 'overview' && (
                <div className="report-section">
                  <h3 className="report-section-title">
                    <Zap size={18} color="var(--accent-blue)" />
                    AI Explanation
                  </h3>
                  <div className="report-explanation">{report.explanation || 'No explanation available.'}</div>
                </div>
              )}

              {/* Affected Files */}
              {activeTab === 'files' && (
                <div className="report-section">
                  <h3 className="report-section-title">
                    <FileCode size={18} color="var(--accent-violet)" />
                    Affected Files ({report.affected_files.length})
                  </h3>
                  {report.affected_files.length > 0 ? (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>File</th>
                          <th>Risk</th>
                          <th>Depth</th>
                          <th>Affected Functions</th>
                          <th>Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.affected_files.map((f, i) => (
                          <tr key={i}>
                            <td className="mono">{f.file_path.split(/[/\\]/).pop()}</td>
                            <td><span className={`risk-badge ${f.risk_level}`}>{riskIcon(f.risk_level)} {f.risk_level}</span></td>
                            <td>{f.dependency_depth}</td>
                            <td className="mono" style={{ fontSize: '0.75rem' }}>
                              {f.affected_functions.slice(0, 3).join(', ')}
                              {f.affected_functions.length > 3 && ` +${f.affected_functions.length - 3}`}
                            </td>
                            <td style={{ maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {f.reason}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="empty-state"><p>No affected files detected.</p></div>
                  )}
                </div>
              )}

              {/* Affected Functions */}
              {activeTab === 'functions' && (
                <div className="report-section">
                  <h3 className="report-section-title">
                    <Zap size={18} color="var(--accent-amber)" />
                    Affected Functions ({report.affected_functions.length})
                  </h3>
                  {report.affected_functions.length > 0 ? (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Function</th>
                          <th>Risk</th>
                          <th>Impact Type</th>
                          <th>File</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.affected_functions.map((f, i) => (
                          <tr key={i}>
                            <td className="mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{f.name}</td>
                            <td><span className={`risk-badge ${f.risk_level}`}>{riskIcon(f.risk_level)} {f.risk_level}</span></td>
                            <td>
                              <span style={{ padding: '2px 8px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-full)', fontSize: '0.75rem' }}>
                                {f.impact_type.replace(/_/g, ' ')}
                              </span>
                            </td>
                            <td className="mono" style={{ fontSize: '0.75rem' }}>{f.file_path.split(/[/\\]/).pop()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="empty-state"><p>No affected functions detected.</p></div>
                  )}
                </div>
              )}

              {/* Tests */}
              {activeTab === 'tests' && (
                <div className="report-section">
                  <h3 className="report-section-title">
                    <FlaskConical size={18} color="var(--accent-emerald)" />
                    Test Recommendations ({report.test_recommendations.length})
                  </h3>
                  <div style={{ marginBottom: 16, padding: '10px 14px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem' }}>
                    Estimated test coverage: <strong>{(report.estimated_test_coverage * 100).toFixed(0)}%</strong>
                  </div>
                  {report.test_recommendations.length > 0 ? (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Test</th>
                          <th>Priority</th>
                          <th>File</th>
                          <th>Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.test_recommendations.map((t, i) => (
                          <tr key={i}>
                            <td className="mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{t.test_name}</td>
                            <td><span className={`risk-badge ${t.priority}`}>{t.priority}</span></td>
                            <td className="mono" style={{ fontSize: '0.75rem' }}>{t.test_file.split(/[/\\]/).pop()}</td>
                            <td style={{ fontSize: '0.8rem' }}>{t.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="empty-state">
                      <FlaskConical />
                      <h3>No tests found</h3>
                      <p>The changed component may lack test coverage.</p>
                    </div>
                  )}
                </div>
              )}

              {/* Evidence */}
              {activeTab === 'evidence' && (
                <div className="report-section">
                  <h3 className="report-section-title">
                    <ShieldCheck size={18} color="var(--accent-cyan)" />
                    Evidence ({report.evidence.length})
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {report.evidence.map((e, i) => (
                      <div key={i} style={{ padding: '12px 16px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid var(--accent-blue)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--accent-blue)', textTransform: 'uppercase' }}>
                            {e.source.replace(/_/g, ' ')}
                          </span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                            Confidence: {(e.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{e.description}</div>
                        {e.file_path && (
                          <div className="mono" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4 }}>
                            {e.file_path} {e.line_range && `(${e.line_range})`}
                          </div>
                        )}
                        {e.code_snippet && (
                          <pre style={{ marginTop: 8, padding: 10, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', overflow: 'auto', color: 'var(--text-muted)' }}>
                            {e.code_snippet}
                          </pre>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Verification */}
              {activeTab === 'verification' && (
                <div className="report-section">
                  <h3 className="report-section-title">
                    <ShieldCheck size={18} color="var(--accent-emerald)" />
                    Verification Results
                  </h3>
                  <div className="verification-list">
                    {report.verification_results.map((v, i) => (
                      <div key={i} className="verification-item">
                        <div className={`check-icon ${v.passed ? 'pass' : 'fail'}`}>
                          {v.passed ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{v.check_name}</div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{v.message}</div>
                        </div>
                        <span className={`risk-badge ${v.severity}`}>{v.severity}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
