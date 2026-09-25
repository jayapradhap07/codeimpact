import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles,
  X,
  Send,
  Trash2,
  ChevronDown,
  ChevronRight,
  Code,
  FileCode,
  Bot,
  User,
  ExternalLink,
  Layers,
  ArrowRight,
} from 'lucide-react'
import { api } from '../../services/api'
import type { Repository, ChatMessage, SearchResult } from '../../types'

interface AIAssistantDrawerProps {
  isOpen: boolean
  onClose: () => void
  initialRepoId?: number
}

const DEFAULT_SUGGESTIONS = [
  'Summarize codebase architecture & modules',
  'What are the main entry points?',
  'Find all database models and relationships',
  'How is authentication & security handled?',
  'List critical external dependencies',
]

// Simple, robust markdown & code block renderer
function FormattedMessage({ content }: { content: string }) {
  // Split by code fences ```
  const parts = content.split(/(```[\s\S]*?```)/g)

  return (
    <div className="assistant-markdown">
      {parts.map((part, idx) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const lines = part.slice(3, -3).trim().split('\n')
          const lang = lines[0]?.match(/^[a-zA-Z0-9_-]+$/) ? lines[0] : ''
          const code = lang ? lines.slice(1).join('\n') : lines.join('\n')

          return (
            <div key={idx} className="assistant-code-block">
              {lang && <div className="code-block-lang">{lang}</div>}
              <pre>
                <code>{code}</code>
              </pre>
            </div>
          )
        }

        // Render headings, bold text, lists, and inline code
        const lines = part.split('\n')
        return (
          <div key={idx} className="assistant-text-block">
            {lines.map((line, lineIdx) => {
              if (!line.trim()) return <div key={lineIdx} style={{ height: '8px' }} />

              // Headings
              if (line.startsWith('### ')) {
                return (
                  <h4 key={lineIdx} className="assistant-h4">
                    {line.slice(4)}
                  </h4>
                )
              }
              if (line.startsWith('## ')) {
                return (
                  <h3 key={lineIdx} className="assistant-h3">
                    {line.slice(3)}
                  </h3>
                )
              }
              if (line.startsWith('# ')) {
                return (
                  <h2 key={lineIdx} className="assistant-h2">
                    {line.slice(2)}
                  </h2>
                )
              }

              // List items
              const isBullet = line.trim().startsWith('- ') || line.trim().startsWith('* ')
              const isNumbered = /^\d+\.\s/.test(line.trim())
              const textContent = isBullet
                ? line.trim().slice(2)
                : isNumbered
                ? line.trim().replace(/^\d+\.\s/, '')
                : line

              // Parse inline code and bold
              const renderedInline = parseInline(textContent)

              if (isBullet) {
                return (
                  <div key={lineIdx} className="assistant-list-item bullet">
                    <span className="bullet-dot">•</span>
                    <span>{renderedInline}</span>
                  </div>
                )
              }
              if (isNumbered) {
                const match = line.trim().match(/^(\d+)\./)
                return (
                  <div key={lineIdx} className="assistant-list-item numbered">
                    <span className="number-badge">{match ? match[1] : '•'}</span>
                    <span>{renderedInline}</span>
                  </div>
                )
              }

              return (
                <p key={lineIdx} className="assistant-paragraph">
                  {renderedInline}
                </p>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}

function parseInline(text: string): React.ReactNode[] {
  // Regex for inline code `...` and bold **...**
  const regex = /(`[^`]+`|\*\*[^*]+\*\*)/g
  const parts = text.split(regex)

  return parts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} className="assistant-inline-code">
          {part.slice(1, -1)}
        </code>
      )
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    return part
  })
}

export function AIAssistantDrawer({ isOpen, onClose, initialRepoId }: AIAssistantDrawerProps) {
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [selectedRepoId, setSelectedRepoId] = useState<number | null>(initialRepoId || null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [expandedChunks, setExpandedChunks] = useState<Record<string, boolean>>({})

  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Load repositories
  useEffect(() => {
    async function loadRepos() {
      try {
        const res = await api.listRepositories()
        setRepositories(res.repositories)
        if (!selectedRepoId && res.repositories.length > 0) {
          const readyRepo = res.repositories.find((r) => r.status === 'ready') || res.repositories[0]
          setSelectedRepoId(readyRepo.id)
        }
      } catch (err) {
        console.error('Failed to load repositories', err)
      }
    }
    if (isOpen) {
      loadRepos()
    }
  }, [isOpen])

  // Update repo if initialRepoId prop changes
  useEffect(() => {
    if (initialRepoId) {
      setSelectedRepoId(initialRepoId)
    }
  }, [initialRepoId])

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 200)
    }
  }, [isOpen])

  // Auto scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const selectedRepo = repositories.find((r) => r.id === selectedRepoId)

  // Welcome message when selecting repo
  useEffect(() => {
    if (selectedRepo && messages.length === 0) {
      setMessages([
        {
          id: 'welcome',
          role: 'assistant',
          content: `👋 Hello! I'm your **CodeImpact AI Assistant** for **${selectedRepo.name}**.\n\nI can help you explore architecture, locate symbols, analyze change impacts, and inspect code dependencies.\n\n*Choose a suggested question below or ask anything about this codebase!*`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          suggested_followups: [
            `What does ${selectedRepo.name} do?`,
            'What are the key modules?',
            'Find all API endpoints',
          ],
        },
      ])
    }
  }, [selectedRepo])

  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend || input).trim()
    if (!query || !selectedRepoId || isLoading) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    // Build history
    const history = messages.map((m) => ({ role: m.role, content: m.content }))

    try {
      const res = await api.askAssistant({
        repo_id: selectedRepoId,
        message: query,
        history,
      })

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: res.response,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        relevant_chunks: res.relevant_chunks,
        suggested_followups: res.suggested_followups,
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (err: any) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `⚠️ **Error generating response:** ${err.message || 'Server connection failed'}. Please verify backend is running on port 8001.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const toggleChunk = (id: string) => {
    setExpandedChunks((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const clearChat = () => {
    if (selectedRepo) {
      setMessages([
        {
          id: 'welcome-cleared',
          role: 'assistant',
          content: `Chat cleared. Ready for your questions about **${selectedRepo.name}**!`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          suggested_followups: DEFAULT_SUGGESTIONS.slice(0, 3),
        },
      ])
    } else {
      setMessages([])
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop for click outside */}
          <motion.div
            className="assistant-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />

          {/* Slide-in Drawer from Right Side */}
          <motion.aside
            className="assistant-drawer"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 26, stiffness: 280 }}
          >
            {/* Header */}
            <div className="assistant-header">
              <div className="assistant-header-left">
                <div className="assistant-avatar">
                  <Sparkles size={18} className="assistant-sparkle-icon" />
                </div>
                <div>
                  <div className="assistant-title">AI Assistant</div>
                  <div className="assistant-subtitle">RAG & Knowledge Graph Powered</div>
                </div>
              </div>

              <div className="assistant-header-actions">
                <button
                  className="assistant-icon-btn"
                  title="Clear conversation"
                  onClick={clearChat}
                >
                  <Trash2 size={16} />
                </button>
                <button
                  className="assistant-icon-btn close-btn"
                  title="Close assistant"
                  onClick={onClose}
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Repository Selector Toolbar */}
            <div className="assistant-repo-bar">
              <span className="repo-bar-label">Repository:</span>
              <select
                className="assistant-repo-select"
                value={selectedRepoId || ''}
                onChange={(e) => {
                  setSelectedRepoId(Number(e.target.value))
                  setMessages([])
                }}
              >
                {repositories.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.file_count} files)
                  </option>
                ))}
              </select>
            </div>

            {/* Messages Container */}
            <div className="assistant-messages-container">
              {messages.map((msg) => (
                <div key={msg.id} className={`assistant-msg-row ${msg.role}`}>
                  <div className="msg-avatar">
                    {msg.role === 'assistant' ? <Bot size={15} /> : <User size={15} />}
                  </div>

                  <div className="msg-bubble-wrapper">
                    <div className="msg-header-meta">
                      <span className="msg-sender">
                        {msg.role === 'assistant' ? 'CodeImpact AI' : 'You'}
                      </span>
                      <span className="msg-time">{msg.timestamp}</span>
                    </div>

                    <div className="msg-bubble">
                      <FormattedMessage content={msg.content} />

                      {/* Cited Code Chunks / Context */}
                      {msg.relevant_chunks && msg.relevant_chunks.length > 0 && (
                        <div className="assistant-citations">
                          <div className="citations-header">
                            <Code size={13} />
                            <span>Referenced Context ({msg.relevant_chunks.length} snippets)</span>
                          </div>
                          <div className="citations-list">
                            {msg.relevant_chunks.map((item, idx) => {
                              const chunk = item.chunk
                              const chunkKey = `${msg.id}-chunk-${idx}`
                              const isExp = expandedChunks[chunkKey]

                              return (
                                <div key={idx} className="citation-item">
                                  <div
                                    className="citation-summary"
                                    onClick={() => toggleChunk(chunkKey)}
                                  >
                                    <div className="citation-file">
                                      <FileCode size={13} className="citation-icon" />
                                      <span className="citation-path">{chunk.file_path}</span>
                                      <span className="citation-lines">
                                        :{chunk.start_line}-{chunk.end_line}
                                      </span>
                                    </div>
                                    <div className="citation-badge">
                                      {chunk.chunk_type}
                                      {isExp ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                                    </div>
                                  </div>

                                  {isExp && (
                                    <motion.div
                                      initial={{ height: 0, opacity: 0 }}
                                      animate={{ height: 'auto', opacity: 1 }}
                                      className="citation-code-preview"
                                    >
                                      <pre>
                                        <code>{chunk.content}</code>
                                      </pre>
                                    </motion.div>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}

                      {/* Suggested Followups */}
                      {msg.suggested_followups && msg.suggested_followups.length > 0 && (
                        <div className="msg-followups">
                          <span className="followup-label">Suggested follow-ups:</span>
                          <div className="followup-chips">
                            {msg.suggested_followups.map((sug, sIdx) => (
                              <button
                                key={sIdx}
                                className="followup-chip"
                                onClick={() => handleSendMessage(sug)}
                              >
                                <span>{sug}</span>
                                <ArrowRight size={12} />
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {/* Loading indicator */}
              {isLoading && (
                <div className="assistant-msg-row assistant loading-row">
                  <div className="msg-avatar">
                    <Bot size={15} />
                  </div>
                  <div className="msg-bubble-wrapper">
                    <div className="msg-bubble loading-bubble">
                      <div className="typing-dots">
                        <span />
                        <span />
                        <span />
                      </div>
                      <span className="typing-text">Analyzing codebase & knowledge graph...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* Quick Suggestions Drawer Footer */}
            {messages.length <= 2 && (
              <div className="assistant-suggestions-bar">
                <div className="suggestions-title">
                  <Sparkles size={13} />
                  <span>Quick Inquiries</span>
                </div>
                <div className="suggestions-scroll">
                  {DEFAULT_SUGGESTIONS.map((sug, idx) => (
                    <button
                      key={idx}
                      className="quick-sug-btn"
                      onClick={() => handleSendMessage(sug)}
                    >
                      {sug}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Input Bar */}
            <div className="assistant-input-bar">
              <div className="input-wrapper">
                <input
                  ref={inputRef}
                  type="text"
                  placeholder={
                    selectedRepo
                      ? `Ask about ${selectedRepo.name}...`
                      : 'Connect a repository to ask questions...'
                  }
                  value={input}
                  disabled={!selectedRepoId || isLoading}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
                <button
                  className="send-btn"
                  disabled={!input.trim() || !selectedRepoId || isLoading}
                  onClick={() => handleSendMessage()}
                  title="Send message (Enter)"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
