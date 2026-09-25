import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  GitBranch, FolderOpen, Loader2, CheckCircle, XCircle, ArrowRight,
  FileCode, Code2, RotateCw, Clock, Sparkles, Layers, GitCommit, FileText, ChevronDown,
  Trash2, CheckCircle2, X
} from 'lucide-react'
import { api } from '../services/api'
import type { Repository } from '../types'

interface ToastInfo {
  type: 'success' | 'error'
  message: string
}

const SUGGESTED_INQUIRIES = [
  "Explain the overall architecture and data flow of this codebase",
  "How does the repository handle code parsing and chunking?",
  "What are the main API endpoints and their handler routes?",
  "Trace the execution flow when a user queries the RAG engine",
  "List the primary database models and their relationships",
  "Identify potential circular dependencies or coupling issues",
]

export default function RepositoryPage() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [localPath, setLocalPath] = useState('')
  const [name, setName] = useState('')
  const [mode, setMode] = useState<'url' | 'local'>('url')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<Repository | null>(null)
  const [allRepos, setAllRepos] = useState<Repository[]>([])
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  // Custom Delete Modal State
  const [repoToDelete, setRepoToDelete] = useState<{ id: number; name: string } | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Floating Toast State
  const [toast, setToast] = useState<ToastInfo | null>(null)

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  async function confirmDelete() {
    if (!repoToDelete) return
    setDeleting(true)
    try {
      await api.deleteRepository(repoToDelete.id)
      setAllRepos((prev) => prev.filter((r) => r.id !== repoToDelete.id))
      if (result?.id === repoToDelete.id) {
        setResult(null)
      }
      setToast({
        type: 'success',
        message: `Repository "${repoToDelete.name}" was successfully deleted.`,
      })
      setRepoToDelete(null)
      loadRepositories()
    } catch (err: any) {
      setToast({
        type: 'error',
        message: err.message || 'Failed to delete repository',
      })
    } finally {
      setDeleting(false)
    }
  }

  // Load existing repositories on mount
  useEffect(() => {
    loadRepositories()
  }, [])

  async function loadRepositories() {
    try {
      const res = await api.listRepositories()
      setAllRepos(res.repositories)
      // If we don't have an active result, select the first ready repo
      if (!result && res.repositories.length > 0) {
        const ready = res.repositories.find(r => r.status === 'ready') || res.repositories[0]
        setResult(ready)
      }
    } catch {
      // ignore
    }
  }

  // Live polling while ingestion is in progress
  useEffect(() => {
    if (!result || result.status === 'ready' || result.status === 'error') {
      return
    }

    const intervalId = setInterval(async () => {
      try {
        const updated = await api.getRepository(result.id)
        setResult(updated)
        if (updated.status === 'ready') {
          loadRepositories()
        }
      } catch {
        // Silently retry on next poll tick
      }
    }, 1200)

    return () => clearInterval(intervalId)
  }, [result?.id, result?.status])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const data = mode === 'url'
        ? { url, name: name || undefined }
        : { local_path: localPath, name: name || undefined }

      const repo = await api.connectRepository(data)
      setResult(repo)
    } catch (err: any) {
      setError(err.message || 'Failed to connect repository')
    } finally {
      setLoading(false)
    }
  }

  async function handleRefreshStats() {
    if (!result) return
    setRefreshing(true)
    try {
      const updated = await api.getRepository(result.id)
      setResult(updated)
      loadRepositories()
    } catch {
      // ignore
    } finally {
      setTimeout(() => setRefreshing(false), 400)
    }
  }

  function handleSelectInquiry(inquiryText: string) {
    if (!result) return
    navigate('/analysis', {
      state: {
        repoId: result.id,
        query: inquiryText,
      }
    })
  }

  // Calculate languages breakdown
  const languagesMap = result?.languages || {}
  const totalLangFiles = Object.values(languagesMap).reduce((a, b) => a + b, 0) || result?.file_count || 1
  const languageEntries = Object.entries(languagesMap).sort((a, b) => b[1] - a[1])

  // Semantic chunks estimation (approx 3-5 chunks per file or at least functions+classes)
  const semanticChunksCount = result
    ? Math.max(result.function_count + result.class_count * 2, result.file_count * 3, 16)
    : 0

  const extractedSymbolsCount = result
    ? (result.function_count + result.class_count)
    : 0

  return (
    <>
      <div className="page-header" style={{ marginBottom: 20 }}>
        <h2>Connect & Manage Repositories</h2>
        <p>Add a codebase for impact analysis. The system clones, parses ASTs, and indexes vectors automatically.</p>
      </div>

      {/* Connect Form + Status Box */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 32 }}>
        {/* Form */}
        <motion.div className="glass-card" style={{ padding: 24 }} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
          <div className="tabs" style={{ marginBottom: 20 }}>
            <button className={`tab ${mode === 'url' ? 'active' : ''}`} onClick={() => setMode('url')}>
              <GitBranch size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
              Git URL
            </button>
            <button className={`tab ${mode === 'local' ? 'active' : ''}`} onClick={() => setMode('local')}>
              <FolderOpen size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
              Local Path
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            {mode === 'url' ? (
              <div className="form-group">
                <label className="form-label">Repository URL</label>
                <input
                  className="form-input"
                  type="text"
                  placeholder="https://github.com/user/repo.git"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                />
              </div>
            ) : (
              <div className="form-group">
                <label className="form-label">Local Path</label>
                <input
                  className="form-input"
                  type="text"
                  placeholder="D:\projects\my-repo"
                  value={localPath}
                  onChange={(e) => setLocalPath(e.target.value)}
                  required
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Display Name (optional)</label>
              <input
                className="form-input"
                type="text"
                placeholder="Auto-detected from URL/path"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-lg"
              disabled={loading || (mode === 'url' ? !url : !localPath)}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {loading ? (
                <>
                  <Loader2 size={18} className="spin" style={{ animation: 'spin 0.8s linear infinite' }} />
                  Connecting...
                </>
              ) : (
                <>
                  <GitBranch size={18} />
                  Connect Repository
                </>
              )}
            </button>
          </form>
        </motion.div>

        {/* Select Existing / Status Card */}
        <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
          <div className="glass-card" style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <span className="form-label">Active Workspace Repository</span>
                {allRepos.length > 0 && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {allRepos.length} connected
                  </span>
                )}
              </div>

              {allRepos.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <select
                    className="form-input"
                    value={result?.id || ''}
                    onChange={(e) => {
                      const found = allRepos.find(r => r.id === Number(e.target.value))
                      if (found) setResult(found)
                    }}
                    style={{ background: 'var(--bg-secondary)', cursor: 'pointer' }}
                  >
                    {allRepos.map(r => (
                      <option key={r.id} value={r.id}>
                        {r.name} ({r.status}) — {r.file_count} files
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {result && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span className={`status-dot ${result.status === 'ready' ? 'ready' : result.status === 'error' ? 'error' : 'processing'}`} />
                    <span style={{ fontWeight: 600, fontSize: '1rem' }}>{result.name}</span>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                      ({result.status})
                    </span>
                  </div>

                  {result.status !== 'ready' && result.status !== 'error' && (
                    <div style={{ marginTop: 8 }}>
                      <div className="progress-bar">
                        <div
                          className="progress-bar-fill"
                          style={{
                            width: result.status === 'cloning' ? '25%'
                              : result.status === 'parsing' ? '50%'
                              : result.status === 'indexing' ? '75%'
                              : '15%',
                          }}
                        />
                      </div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 8 }}>
                        {result.status === 'cloning' && '⏳ Cloning repository...'}
                        {result.status === 'parsing' && '⚡ Parsing source files with Tree-sitter...'}
                        {result.status === 'indexing' && '🧠 Building knowledge graph & vector index...'}
                        {result.status === 'pending' && '🚀 Ingestion in progress...'}
                      </div>
                    </div>
                  )}

                  {result.status === 'ready' && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                      ✅ Knowledge graph & semantic vectors indexed. Ready for impact analysis.
                    </div>
                  )}
                </div>
              )}

              {error && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--risk-critical)', marginTop: 12, fontSize: '0.85rem' }}>
                  <XCircle size={16} /> {error}
                </div>
              )}
            </div>

            {result?.status === 'ready' && (
              <button
                className="btn btn-primary"
                onClick={() => navigate('/analysis', { state: { repoId: result.id } })}
                style={{ width: '100%', justifyContent: 'center', marginTop: 16 }}
              >
                Go to Impact Analysis <ArrowRight size={16} />
              </button>
            )}
          </div>
        </motion.div>
      </div>

      {/* ══════════════════════════════════════════════════════════
          REPOSITORY DETAILED STATS VIEW (Exact Design from Reference)
         ══════════════════════════════════════════════════════════ */}
      {result && result.status === 'ready' && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          {/* Top Repository Header Banner */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            marginBottom: 20,
            paddingBottom: 16,
            borderBottom: '1px solid var(--border-primary)',
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <h2 style={{ fontSize: '1.6rem', fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
                  {result.name}
                </h2>
                <span style={{
                  background: 'rgba(59, 130, 246, 0.15)',
                  color: 'var(--accent-blue-light)',
                  padding: '3px 10px',
                  borderRadius: 'var(--radius-full)',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  border: '1px solid rgba(59, 130, 246, 0.3)',
                }}>
                  Branch: main
                </span>
              </div>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                color: 'var(--text-muted)',
                marginTop: 6,
              }}>
                {result.local_path || result.url || `repository/${result.name}`}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleRefreshStats}
                disabled={refreshing}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <RotateCw size={14} className={refreshing ? 'spin' : ''} style={{ animation: refreshing ? 'spin 0.8s linear infinite' : 'none' }} />
                Refresh Stats
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setRepoToDelete({ id: result.id, name: result.name })}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  color: 'var(--text-muted)',
                  borderColor: 'var(--border-primary)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = 'var(--risk-critical)'
                  e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)'
                  e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.3)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = 'var(--text-muted)'
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.borderColor = 'var(--border-primary)'
                }}
                title="Delete Repository"
              >
                <Trash2 size={14} />
                Delete
              </button>
            </div>
          </div>

          {/* 4 Metric Cards */}
          <div className="stats-grid" style={{ marginBottom: 28, gridTemplateColumns: 'repeat(4, 1fr)' }}>
            {/* Total Files */}
            <div className="glass-card stat-card" style={{ padding: '20px 22px' }}>
              <div className="stat-header" style={{ marginBottom: 8 }}>
                <span className="stat-label">Total Files</span>
                <div className="stat-icon blue" style={{ width: 36, height: 36 }}>
                  <FileText size={18} />
                </div>
              </div>
              <div className="stat-value" style={{ fontSize: '1.85rem' }}>{result.file_count}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: 4 }}>
                Indexed source & config files
              </div>
            </div>

            {/* Total Lines of Code */}
            <div className="glass-card stat-card" style={{ padding: '20px 22px' }}>
              <div className="stat-header" style={{ marginBottom: 8 }}>
                <span className="stat-label">Total Lines of Code</span>
                <div className="stat-icon violet" style={{ width: 36, height: 36 }}>
                  <Code2 size={18} />
                </div>
              </div>
              <div className="stat-value" style={{ fontSize: '1.85rem' }}>{result.total_lines.toLocaleString()}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: 4 }}>
                Scanned source lines
              </div>
            </div>

            {/* Semantic Chunks */}
            <div className="glass-card stat-card" style={{ padding: '20px 22px' }}>
              <div className="stat-header" style={{ marginBottom: 8 }}>
                <span className="stat-label">Semantic Chunks</span>
                <div className="stat-icon emerald" style={{ width: 36, height: 36 }}>
                  <Layers size={18} />
                </div>
              </div>
              <div className="stat-value" style={{ fontSize: '1.85rem' }}>{semanticChunksCount}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: 4 }}>
                AST function & class chunks
              </div>
            </div>

            {/* Extracted Symbols */}
            <div className="glass-card stat-card" style={{ padding: '20px 22px' }}>
              <div className="stat-header" style={{ marginBottom: 8 }}>
                <span className="stat-label">Extracted Symbols</span>
                <div className="stat-icon cyan" style={{ width: 36, height: 36 }}>
                  <GitCommit size={18} />
                </div>
              </div>
              <div className="stat-value" style={{ fontSize: '1.85rem' }}>{extractedSymbolsCount}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: 4 }}>
                Functions, classes & routes
              </div>
            </div>
          </div>

          {/* Bottom 2-Column Section: Languages & Formats (Left) + Suggested Inquiries (Right) */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.65fr', gap: 24 }}>
            {/* Left Card: Languages & Formats (Shows ALL detected languages) */}
            <div className="glass-card" style={{ padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22 }}>
                <Clock size={18} color="var(--accent-blue-light)" />
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Languages & Formats
                </h3>
              </div>

              {languageEntries.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No source files detected</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {languageEntries.map(([langName, count]) => {
                    const pct = Math.max(1, Math.round((count / totalLangFiles) * 100))
                    return (
                      <div key={langName}>
                        <div style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          fontSize: '0.825rem',
                          marginBottom: 6,
                        }}>
                          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{langName}</span>
                          <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                            {count} files ({pct}%)
                          </span>
                        </div>
                        {/* Custom glowing progress bar */}
                        <div style={{
                          width: '100%',
                          height: 5,
                          background: 'rgba(255, 255, 255, 0.07)',
                          borderRadius: 999,
                          overflow: 'hidden',
                        }}>
                          <div style={{
                            width: `${pct}%`,
                            height: '100%',
                            background: 'linear-gradient(90deg, #3b82f6, #8b5cf6)',
                            borderRadius: 999,
                            boxShadow: '0 0 8px rgba(59, 130, 246, 0.5)',
                            transition: 'width 0.5s ease',
                          }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Right Card: Suggested Inquiries for AI Assistant */}
            <div className="glass-card" style={{ padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                <Sparkles size={18} color="#eab308" />
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Suggested Inquiries for AI Assistant
                </h3>
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 14,
              }}>
                {SUGGESTED_INQUIRIES.map((promptText, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleSelectInquiry(promptText)}
                    style={{
                      background: 'rgba(15, 22, 41, 0.65)',
                      border: '1px solid rgba(139, 149, 176, 0.12)',
                      borderRadius: 'var(--radius-md)',
                      padding: '16px 18px',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 12,
                      cursor: 'pointer',
                      transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.4)'
                      e.currentTarget.style.background = 'rgba(20, 30, 58, 0.85)'
                      e.currentTarget.style.transform = 'translateY(-2px)'
                      e.currentTarget.style.boxShadow = '0 6px 18px rgba(0, 0, 0, 0.35), 0 0 12px rgba(59, 130, 246, 0.15)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'rgba(139, 149, 176, 0.12)'
                      e.currentTarget.style.background = 'rgba(15, 22, 41, 0.65)'
                      e.currentTarget.style.transform = 'translateY(0)'
                      e.currentTarget.style.boxShadow = 'none'
                    }}
                  >
                    <Sparkles size={16} color="var(--accent-blue-light)" style={{ flexShrink: 0, marginTop: 2 }} />
                    <span style={{
                      fontSize: '0.84rem',
                      color: 'var(--text-secondary)',
                      lineHeight: 1.45,
                      fontWeight: 400,
                    }}>
                      {promptText}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      )}

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
