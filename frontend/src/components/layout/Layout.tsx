import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, GitBranch, Search, Network, Zap, Sparkles, MessageSquare } from 'lucide-react'
import type { ReactNode } from 'react'
import { AIAssistantDrawer } from '../assistant/AIAssistantDrawer'

const navItems = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard },
  { label: 'Repositories', path: '/repository', icon: GitBranch },
  { label: 'Impact Analysis', path: '/analysis', icon: Zap },
  { label: 'Graph Explorer', path: '/graph', icon: Network },
]

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [isAssistantOpen, setIsAssistantOpen] = useState(false)

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">⚡</div>
          <h1>CodeImpact</h1>
        </div>

        <nav className="sidebar-nav">
          <span className="sidebar-section-title">Navigation</span>
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path
            return (
              <button
                key={item.path}
                className={`sidebar-link ${isActive ? 'active' : ''}`}
                onClick={() => navigate(item.path)}
              >
                <Icon />
                {item.label}
              </button>
            )
          })}
        </nav>

        <div style={{ padding: '16px 12px', borderTop: '1px solid var(--border-primary)' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textAlign: 'center' }}>
            CodeImpact v1.0
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="app-main">
        <header className="header">
          <div>
            <div className="header-title">
              {navItems.find((n) => n.path === location.pathname)?.label || 'CodeImpact'}
            </div>
            <div className="header-subtitle">AI-powered change impact analysis</div>
          </div>
          <div className="header-actions" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              className="header-assistant-toggle"
              onClick={() => setIsAssistantOpen((prev) => !prev)}
              title="Toggle AI Codebase Assistant"
            >
              <Sparkles size={15} />
              <span>{isAssistantOpen ? 'Close Assistant' : 'AI Assistant'}</span>
            </button>
            <div className="status-dot ready" title="Backend connected" />
          </div>
        </header>

        <div className="page-content">{children}</div>

        {/* Floating Quick Action Button on Bottom Right */}
        {!isAssistantOpen && (
          <button
            className="floating-assistant-btn"
            onClick={() => setIsAssistantOpen(true)}
            title="Ask AI Assistant about codebase"
          >
            <Sparkles size={17} />
            <span>AI Assistant</span>
          </button>
        )}

        {/* Right-Side AI Assistant Slide-Over Drawer */}
        <AIAssistantDrawer
          isOpen={isAssistantOpen}
          onClose={() => setIsAssistantOpen(false)}
        />
      </main>
    </div>
  )
}

