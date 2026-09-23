import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
  type KeyboardEvent,
} from 'react';
import {
  Send,
  Trash2,
  Compass,
  Plus,
  MessageSquare,
  ShieldCheck,
  PanelLeftClose,
  PanelLeftOpen,
  Edit2,
  Check,
  X,
  AlertCircle,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { askApi } from '@/api/ask';
import { conversationsApi } from '@/api/conversations';
import { getErrorMessage } from '@/contexts/AuthContext';
import { LoadingDots, Spinner } from '@/components/common/Spinner';
import { format } from 'date-fns';
import type {
  ChatMessage,
  SourceResponse,
  Conversation,
} from '@/types/api';

const SUGGESTIONS = [
  'What is the Kärcher BD 43/40?',
  'What are its main features?',
  'Show products suitable for industrial cleaning.',
  'Compare two available products.',
  'Which products belong to a particular category?',
];

function SourceChip({ source }: { source: SourceResponse }) {
  const label =
    source.sku ??
    (source.filename ? `Doc ${source.document_id}` : `Source ${source.chunk_id ?? '?'}`);
  return (
    <span className="source-chip" title={source.filename ?? undefined}>
      📄 {label}
    </span>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`chat-bubble-wrapper ${msg.role}`}>
      <div className={`chat-bubble ${msg.role}${msg.isError ? ' error' : ''}`}>
        {msg.content}
        {msg.sources && msg.sources.length > 0 && (
          <div className="chat-sources">
            {msg.sources.map((s, i) => (
              <SourceChip key={i} source={s} />
            ))}
          </div>
        )}
      </div>
      <div className="chat-meta">
        {format(msg.timestamp, 'HH:mm')}
        {!isUser && msg.sources && msg.sources.length > 0 && (
          <> · {msg.sources.length} source{msg.sources.length !== 1 ? 's' : ''}</>
        )}
      </div>
    </div>
  );
}

let msgCounter = 0;
function newId() {
  return `msg-${++msgCounter}`;
}

export function ChatPage() {
  const { user } = useAuth();

  // Conversations state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Rename state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');

  // Messages state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating, isLoadingHistory]);

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

  // Load conversations list on mount
  const loadConversations = useCallback(async () => {
    try {
      setIsLoadingConversations(true);
      const data = await conversationsApi.list();
      setConversations(data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setIsLoadingConversations(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // Select a conversation and load its messages
  const selectConversation = useCallback(
    async (id: number) => {
      if (activeConversationId === id && messages.length > 0) return;
      setActiveConversationId(id);
      setIsLoadingHistory(true);
      setErrorBanner(null);

      try {
        const detail = await conversationsApi.get(id);
        const mappedMessages: ChatMessage[] = detail.messages.map((m) => ({
          id: `db-${m.id}`,
          role: m.role,
          content: m.content,
          sources: m.sources ?? undefined,
          timestamp: new Date(m.created_at),
        }));
        setMessages(mappedMessages);
      } catch (err) {
        setErrorBanner(getErrorMessage(err));
      } finally {
        setIsLoadingHistory(false);
      }
    },
    [activeConversationId, messages.length]
  );

  // Start a new conversation
  const handleNewChat = useCallback(() => {
    setActiveConversationId(null);
    setMessages([]);
    setInput('');
    setErrorBanner(null);
  }, []);

  // Delete a conversation
  const handleDeleteConversation = useCallback(
    async (e: React.MouseEvent, id: number) => {
      e.stopPropagation();
      if (!window.confirm('Delete this conversation permanently?')) return;

      try {
        await conversationsApi.delete(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (activeConversationId === id) {
          handleNewChat();
        }
      } catch (err) {
        setErrorBanner(getErrorMessage(err));
      }
    },
    [activeConversationId, handleNewChat]
  );

  // Save renamed title
  const handleSaveRename = useCallback(
    async (id: number) => {
      if (!editTitle.trim()) {
        setEditingId(null);
        return;
      }
      try {
        const updated = await conversationsApi.rename(id, editTitle.trim());
        setConversations((prev) =>
          prev.map((c) => (c.id === id ? { ...c, title: updated.title } : c))
        );
      } catch (err) {
        setErrorBanner(getErrorMessage(err));
      } finally {
        setEditingId(null);
      }
    },
    [editTitle]
  );

  // Send message
  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isGenerating) return;

      const userMsg: ChatMessage = {
        id: newId(),
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput('');
      setIsGenerating(true);
      setErrorBanner(null);

      try {
        const res = await askApi.ask({
          query: trimmed,
          top_k: 5,
          conversation_id: activeConversationId ?? undefined,
        });

        const assistantMsg: ChatMessage = {
          id: newId(),
          role: 'assistant',
          content: res.answer,
          sources: res.sources,
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, assistantMsg]);

        // If this was a new conversation, set active ID and refresh conversation list
        if (activeConversationId === null && res.conversation_id) {
          setActiveConversationId(res.conversation_id);
          loadConversations();
        }
      } catch (err) {
        const errMsg: ChatMessage = {
          id: newId(),
          role: 'assistant',
          content: getErrorMessage(err),
          timestamp: new Date(),
          isError: true,
        };
        setMessages((prev) => [...prev, errMsg]);
      } finally {
        setIsGenerating(false);
      }
    },
    [activeConversationId, isGenerating, loadConversations]
  );

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const hasMessages = messages.length > 0;

  return (
    <div className="chat-container">
      {/* ── Conversation Sidebar ────────────────────────────────────────── */}
      <aside className={`chat-sidebar ${sidebarOpen ? '' : 'closed'}`}>
        <div className="chat-sidebar-header">
          <button
            className="btn btn-primary"
            onClick={handleNewChat}
            style={{ width: '100%', justifyContent: 'center', gap: 8 }}
            id="new-chat-btn"
          >
            <Plus size={16} />
            New Chat
          </button>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.75rem',
              color: 'var(--color-text-muted)',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            <span>Saved Chats</span>
            <span>{conversations.length}</span>
          </div>
        </div>

        <div className="chat-sidebar-list">
          {isLoadingConversations ? (
            <div style={{ padding: 24, textAlign: 'center' }}>
              <Spinner size={18} />
            </div>
          ) : conversations.length === 0 ? (
            <div
              style={{
                padding: '24px 16px',
                textAlign: 'center',
                color: 'var(--color-text-muted)',
                fontSize: '0.8rem',
              }}
            >
              No saved conversations yet. Start asking questions to save chat history!
            </div>
          ) : (
            conversations.map((c) => {
              const isActive = c.id === activeConversationId;
              const isEditing = editingId === c.id;

              return (
                <div
                  key={c.id}
                  className={`chat-conv-item ${isActive ? 'active' : ''}`}
                  onClick={() => selectConversation(c.id)}
                  title={c.title}
                >
                  <MessageSquare
                    size={15}
                    style={{
                      flexShrink: 0,
                      color: isActive ? 'var(--color-brand-600)' : 'var(--color-text-muted)',
                    }}
                  />

                  {isEditing ? (
                    <div
                      style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveRename(c.id);
                          if (e.key === 'Escape') setEditingId(null);
                        }}
                        autoFocus
                        style={{
                          flex: 1,
                          fontSize: '0.8rem',
                          padding: '2px 6px',
                          border: '1px solid var(--color-brand-500)',
                          borderRadius: 4,
                        }}
                      />
                      <button
                        className="btn-icon"
                        onClick={() => handleSaveRename(c.id)}
                        aria-label="Save"
                      >
                        <Check size={14} color="#059669" />
                      </button>
                      <button
                        className="btn-icon"
                        onClick={() => setEditingId(null)}
                        aria-label="Cancel"
                      >
                        <X size={14} color="#dc2626" />
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="chat-conv-title">{c.title}</div>
                      <div className="chat-conv-actions">
                        <button
                          className="btn-icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingId(c.id);
                            setEditTitle(c.title);
                          }}
                          title="Rename conversation"
                          aria-label="Rename"
                        >
                          <Edit2 size={13} color="var(--color-text-muted)" />
                        </button>
                        <button
                          className="btn-icon"
                          onClick={(e) => handleDeleteConversation(e, c.id)}
                          title="Delete conversation"
                          aria-label="Delete"
                        >
                          <Trash2 size={13} color="#ef4444" />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* ── Main Chat Area ──────────────────────────────────────────────── */}
      <main className="chat-main">
        {/* Top Header */}
        <header className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setSidebarOpen((prev) => !prev)}
              aria-label={sidebarOpen ? 'Collapse sidebar' : 'Open sidebar'}
              style={{ padding: 6 }}
            >
              {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
            </button>
            <div>
              <h1 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0 }}>
                {activeConv ? activeConv.title : 'AI Sales Assistant'}
              </h1>
              <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', margin: 0 }}>
                Powered by Groq · Qwen 3 · Qdrant Vector Retrieval
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* Accuracy & Security Badge (Replaces old session-only warning) */}
            <span className="chat-secure-badge" role="status">
              <ShieldCheck size={14} />
              Your conversations are saved securely to your account.
            </span>

            {activeConversationId !== null && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={handleNewChat}
                aria-label="Start new chat"
              >
                <Plus size={14} />
                New Chat
              </button>
            )}
          </div>
        </header>

        {/* Error notification if any */}
        {errorBanner && (
          <div
            style={{
              padding: '10px 24px',
              background: 'var(--color-error-bg)',
              color: '#991b1b',
              fontSize: '0.8125rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid #fecaca',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <AlertCircle size={16} />
              <span>{errorBanner}</span>
            </div>
            <button
              onClick={() => setErrorBanner(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer' }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Messages scroll area */}
        <div className="chat-messages">
          {isLoadingHistory ? (
            <div
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              <Spinner size={24} />
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                Loading conversation history...
              </p>
            </div>
          ) : !hasMessages ? (
            /* Empty State */
            <div className="chat-empty">
              <div className="chat-welcome-icon">
                <Compass size={36} color="var(--color-brand-600)" />
              </div>
              <div style={{ textAlign: 'center' }}>
                <h2 style={{ fontSize: '1.25rem', marginBottom: 8, fontWeight: 700 }}>
                  How can I help you today?
                </h2>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                  Ask me anything about products in the catalogue. I search the knowledge base
                  and remember prior context for follow-up questions.
                </p>
              </div>
              <div className="chat-suggestions">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    className="suggestion-card"
                    onClick={() => sendMessage(s)}
                    disabled={isGenerating}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <MessageBubble key={msg.id} msg={msg} />
              ))}
              {isGenerating && (
                <div className="chat-bubble-wrapper assistant">
                  <div className="chat-bubble assistant" style={{ minWidth: 64 }}>
                    <LoadingDots />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input Area */}
        <div className="chat-input-area">
          <div className="chat-input-inner">
            <textarea
              ref={textareaRef}
              className="chat-input-field"
              placeholder={
                isGenerating ? 'Generating response…' : 'Ask about any product or follow up…'
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isGenerating || isLoadingHistory}
              rows={1}
              aria-label="Chat input"
              id="chat-input-field"
            />
            <button
              className="chat-send-btn"
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isGenerating || isLoadingHistory}
              aria-label="Send message"
              id="chat-send-btn"
            >
              <Send size={18} />
            </button>
          </div>
          <p
            style={{
              textAlign: 'center',
              fontSize: '0.72rem',
              color: 'var(--color-text-muted)',
              marginTop: 8,
            }}
          >
            Press <kbd style={{ fontFamily: 'monospace', background: 'var(--color-neutral-100)', padding: '1px 5px', borderRadius: 4, fontSize: '0.8em' }}>Enter</kbd> to send · <kbd style={{ fontFamily: 'monospace', background: 'var(--color-neutral-100)', padding: '1px 5px', borderRadius: 4, fontSize: '0.8em' }}>Shift+Enter</kbd> for new line
          </p>
        </div>
      </main>
    </div>
  );
}
