import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  GitBranch, FileCode, Code2, AlertTriangle, Zap, Trash2,
  CheckCircle2, XCircle, Loader2, X
} from 'lucide-react'
import { api } from '../services/api'
import type { Repository, AnalysisSummary } from '../types'

interface ToastInfo {
  type: 'success' | 'error'
  message: string
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [repos, setRepos] = useState<Repository[]>([])
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([])
  const [loading, setLoading] = useState(true)

  // Custom Delete Modal State
  const [repoToDelete, setRepoToDelete] = useState<{ id: number; name: string } | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Floating Toast State
  const [toast, setToast] = useState<ToastInfo | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  async function loadData() {
    try {
      const [repoRes, analysisRes] = await Promise.allSettled([
        api.listRepositories(),
        api.listAnalyses(),
      ])
      if (repoRes.status === 'fulfilled') setRepos(repoRes.value.repositories)
      if (analysisRes.status === 'fulfilled') setAnalyses(analysisRes.value.analyses)
    } catch { /* ignore */
    } finally {
      setLoading(false)
    }
  }

  function openDeleteModal(id: number, name: string, e: React.MouseEvent) {
    e.stopPropagation()
    setRepoToDelete({ id, name })
  }

  async function confirmDelete() {
    if (!repoToDelete) return
    setDeleting(true)
    try {
      await api.deleteRepository(repoToDelete.id)
      setRepos((prev) => prev.filter((r) => r.id !== repoToDelete.id))
      setToast({
        type: 'success',
        message: `Repository "${repoToDelete.name}" was successfully deleted.`,
      })
      setRepoToDelete(null)
    } catch (err: any) {
      setToast({
        type: 'error',
        message: err.message || 'Failed to delete repository',
      })
    } finally {
      setDeleting(false)
    }
  }

  const totalFiles = repos.reduce((s, r) => s + r.file_count, 0)
  const totalFunctions = repos.reduce((s, r) => s + r.function_count, 0)
  const totalClasses = repos.reduce((s, r) => s + r.class_count, 0)
  const totalLines = repos.reduce((s, r) => s + r.total_lines, 0)

  const riskColor = (level: string | null) => {
    if (!level) return ''
    return level
  }

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Overview of your code analysis workspace</p>
      </div>

      {/* Stat Cards */}
      <div className="stats-grid">
        <motion.div className="glass-card stat-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
          <div className="stat-header">
            <span className="stat-label">Repositories</span>
            <div className="stat-icon blue">
              <GitBranch size={20} />
            </div>
          </div>
          <div className="stat-value">{repos.length}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
            {repos.filter(r => r.status === 'ready').length} active
          </div>
        </motion.div>

        <motion.div className="glass-card stat-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <div className="stat-header">
            <span className="stat-label">Source Files</span>
            <div className="stat-icon violet">
              <FileCode size={20} />
            </div>
          </div>
          <div className="stat-value">{totalFiles.toLocaleString()}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
            {totalLines.toLocaleString()} lines of code
          </div>
        </motion.div>

        <motion.div className="glass-card stat-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <div className="stat-header">
            <span className="stat-label">Functions & Classes</span>
            <div className="stat-icon cyan">
              <Code2 size={20} />
            </div>
          </div>
          <div className="stat-value">{(totalFunctions + totalClasses).toLocaleString()}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
            {totalFunctions} funcs · {totalClasses} classes
          </div>
        </motion.div>

        <motion.div className="glass-card stat-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <div className="stat-header">
            <span className="stat-label">Analyses Run</span>
            <div className="stat-icon amber">
              <Zap size={20} />
            </div>
          </div>
          <div className="stat-value">{analyses.length}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
            Impact assessments
          </div>
        </motion.div>
      </div>

      {/* Connected Repositories */}
      <motion.div className="glass-card" style={{ marginBottom: 28 }} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
        <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--border-primary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>Repositories</span>
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/repository')}>
            Connect Repo
          </button>
        </div>
        {repos.length === 0 ? (
          <div className="empty-state">
            <GitBranch />
            <h3>No repositories connected</h3>
            <p>Connect a GitHub repository or local codebase to get started.</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Files</th>
                <th>Functions</th>
                <th>Languages</th>
                <th style={{ width: 80, textAlign: 'center' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {repos.map((repo) => (
                <tr key={repo.id} style={{ cursor: 'pointer' }} onClick={() => navigate('/analysis')}>
                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {repo.name}
                  </td>
                  <td>
                    <span
                      style={{ marginRight: 8 }}
                      data-status={repo.status}
                      className={`status-dot ${repo.status === 'ready' ? 'ready' : repo.status === 'error' ? 'error' : 'processing'}`}
                    />
                    {repo.status}
                  </td>
                  <td>{repo.file_count.toLocaleString()}</td>
                  <td>{repo.function_count.toLocaleString()}</td>
                  <td>
                    {repo.languages
                      ? Object.keys(repo.languages).slice(0, 3).join(', ')
                      : '—'}
                  </td>
                  <td style={{ textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{
                        padding: '6px 8px',
                        color: 'var(--text-muted)',
                        borderRadius: 'var(--radius-sm)',
                        transition: 'all 0.2s',
                        cursor: 'pointer',
                      }}
                      title="Delete Repository"
                      onClick={(e) => openDeleteModal(repo.id, repo.name, e)}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = 'var(--risk-critical)'
                        e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = 'var(--text-muted)'
                        e.currentTarget.style.background = 'transparent'
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </motion.div>

      {/* Recent Analyses */}
      <motion.div className="glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
        <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--border-primary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>Recent Analyses</span>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/analysis')}>
            New Analysis
          </button>
        </div>
        {analyses.length === 0 ? (
          <div className="empty-state">
            <Zap />
            <h3>No analyses yet</h3>
            <p>Run an impact analysis to see how code changes ripple through your codebase.</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Query</th>
                <th>Repository</th>
                <th>Risk</th>
                <th>Affected Files</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {analyses.map((a) => (
                <tr key={a.id} style={{ cursor: 'pointer' }} onClick={() => navigate('/analysis')}>
                  <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                    {a.query.length > 50 ? a.query.slice(0, 50) + '...' : a.query}
                  </td>
                  <td>{a.repo_name || `Repo #${a.repo_id}`}</td>
                  <td>
                    {a.risk_level ? (
                      <span className={`risk-badge ${riskColor(a.risk_level)}`}>
                        {a.risk_level}
                      </span>
                    ) : '—'}
                  </td>
                  <td>{a.affected_files_count} files</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </motion.div>

      {/* ── Custom Glassmorphic Delete Confirmation Popup Modal ── */}
      <AnimatePresence>
        {repoToDelete && (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 9999,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(5, 8, 15, 0.75)',
              backdropFilter: 'blur(8px)',
            }}
            onClick={() => !deleting && setRepoToDelete(null)}
          >
            <motion.div
              className="glass-card"
              style={{
                width: '100%',
                maxWidth: 440,
                padding: 26,
                borderRadius: 'var(--radius-lg)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                boxShadow: '0 20px 50px rgba(0, 0, 0, 0.6), 0 0 30px rgba(239, 68, 68, 0.15)',
                background: 'rgba(15, 23, 42, 0.95)',
              }}
              initial={{ opacity: 0, scale: 0.92, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.92, y: 10 }}
              transition={{ duration: 0.2 }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header with Danger Icon */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: '50%',
                    background: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#f87171',
                    flexShrink: 0,
                  }}
                >
                  <Trash2 size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                    Delete Repository
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    This action cannot be undone
                  </p>
                </div>
              </div>

              {/* Body */}
              <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: '14px 0 22px 0' }}>
                Are you sure you want to permanently delete{' '}
                <strong style={{ color: '#f1f5f9' }}>"{repoToDelete.name}"</strong>? All associated AST graphs, vector embeddings, and change impact reports will be deleted.
              </p>

              {/* Action Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  className="btn btn-ghost"
                  onClick={() => setRepoToDelete(null)}
                  disabled={deleting}
                  style={{ fontSize: '0.82rem', padding: '7px 14px' }}
                >
                  Cancel
                </button>
                <button
                  className="btn"
                  onClick={confirmDelete}
                  disabled={deleting}
                  style={{
                    fontSize: '0.82rem',
                    padding: '7px 18px',
                    background: '#dc2626',
                    color: '#ffffff',
                    border: '1px solid #ef4444',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    fontWeight: 600,
                  }}
                >
                  {deleting ? (
                    <>
                      <Loader2 size={15} className="spin" style={{ animation: 'spin 0.8s linear infinite' }} />
                      Deleting...
                    </>
                  ) : (
                    <>
                      <Trash2 size={15} />
                      Delete Repository
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── Custom Floating Toast Notification ── */}
      <AnimatePresence>
        {toast && (
          <motion.div
            style={{
              position: 'fixed',
              bottom: 24,
              right: 24,
              zIndex: 10000,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '12px 18px',
              borderRadius: 'var(--radius-md)',
              background: toast.type === 'success' ? 'rgba(15, 23, 42, 0.95)' : 'rgba(30, 10, 15, 0.95)',
              border: `1px solid ${toast.type === 'success' ? 'rgba(52, 211, 153, 0.4)' : 'rgba(248, 113, 113, 0.4)'}`,
              boxShadow: `0 10px 30px rgba(0, 0, 0, 0.5), 0 0 20px ${toast.type === 'success' ? 'rgba(52, 211, 153, 0.2)' : 'rgba(248, 113, 113, 0.2)'}`,
              backdropFilter: 'blur(10px)',
              color: '#f8fafc',
              fontSize: '0.85rem',
              maxWidth: 380,
            }}
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
          >
            {toast.type === 'success' ? (
              <CheckCircle2 size={18} style={{ color: '#34d399', flexShrink: 0 }} />
            ) : (
              <XCircle size={18} style={{ color: '#f87171', flexShrink: 0 }} />
            )}
            <span style={{ flex: 1, lineHeight: 1.4 }}>{toast.message}</span>
            <button
              onClick={() => setToast(null)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: 2,
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <X size={14} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
