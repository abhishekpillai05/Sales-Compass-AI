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
  CheckCircle2,
  Handshake,
  Sparkles,
  RefreshCw,
  Layers,
  ArrowUpRight,
  HelpCircle,
  PackageCheck,
  CheckSquare,
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
  SalesStateResponse,
  CandidateProduct,
  RecommendationItem,
} from '@/types/api';

const SUGGESTIONS = [
  'I need a ladder for electrical maintenance work.',
  'What walk-behind floor scrubbers do you offer?',
  'What is the Kärcher BD 43/40?',
  'Show products suitable for industrial warehouse cleaning.',
  'Show networking switches with PoE+ support.',
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

  // Sales Conversation State
  const [salesState, setSalesState] = useState<SalesStateResponse | null>(null);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const [dealQuantity, setDealQuantity] = useState<number>(1);
  const [isFinalizingDeal, setIsFinalizingDeal] = useState(false);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating, isLoadingHistory, salesState]);

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

  // Select a conversation and load its messages + persistent sales state
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
        setSalesState(detail.sales_state ?? null);
        if (detail.sales_state?.agreed_quantity) {
          setDealQuantity(detail.sales_state.agreed_quantity);
        }
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
    setSalesState(null);
    setSuggestedQuestions([]);
    setDealQuantity(1);
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
        setSalesState(res.sales_state ?? null);
        setSuggestedQuestions(res.suggested_questions ?? []);

        if (res.sales_state?.agreed_quantity) {
          setDealQuantity(res.sales_state.agreed_quantity);
        }

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

  // Handle selecting candidate product
  const handleSelectProduct = async (product: CandidateProduct) => {
    if (!activeConversationId) return;
    try {
      const updated = await conversationsApi.selectProduct(activeConversationId, {
        product,
        quantity: dealQuantity,
      });
      setSalesState(updated);
    } catch (err) {
      setErrorBanner(getErrorMessage(err));
    }
  };

  // Handle explicit deal confirmation
  const handleConfirmDeal = async () => {
    if (!activeConversationId) return;
    setIsFinalizingDeal(true);
    setErrorBanner(null);
    try {
      const updated = await conversationsApi.confirmDeal(activeConversationId, {
        confirmation_text: 'I explicitly confirm and agree to this deal order.',
        quantity: dealQuantity,
      });
      setSalesState(updated);

      // Add a system assistant message in chat confirming finalisation
      const confirmMsg: ChatMessage = {
        id: newId(),
        role: 'assistant',
        content: `Deal explicitly finalised! Verified order for ${updated.agreed_quantity ?? dealQuantity}x ${updated.selected_product?.name ?? 'product'} (${updated.agreed_price ?? 'Standard'}). Add-on accessories and future upgrade recommendations are now eligible.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, confirmMsg]);
    } catch (err) {
      setErrorBanner(getErrorMessage(err));
    } finally {
      setIsFinalizingDeal(false);
    }
  };

  // Handle loading recommendations
  const handleLoadRecommendations = async () => {
    if (!activeConversationId) return;
    setIsLoadingRecommendations(true);
    setErrorBanner(null);
    try {
      const recs = await conversationsApi.getRecommendations(activeConversationId);
      setSalesState((prev) => (prev ? { ...prev, recommendations: recs, stage: 'POST_SALE' } : prev));
    } catch (err) {
      setErrorBanner(getErrorMessage(err));
    } finally {
      setIsLoadingRecommendations(false);
    }
  };

  // Handle reopening deal for modifications
  const handleReopenDeal = async () => {
    if (!activeConversationId) return;
    if (!window.confirm('Reopen this finalised deal to modify quantities or products?')) return;
    try {
      const updated = await conversationsApi.reopenDeal(activeConversationId, {
        reason: 'Customer requested order change',
      });
      setSalesState(updated);
      const reopenMsg: ChatMessage = {
        id: newId(),
        role: 'assistant',
        content: 'Deal has been reopened for discussion and adjustments. Add-on recommendations are paused until terms are re-finalised.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, reopenMsg]);
    } catch (err) {
      setErrorBanner(getErrorMessage(err));
    }
  };

  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const hasMessages = messages.length > 0;
  const stage = salesState?.stage || 'DISCOVERY';
  const isDealFinalized = salesState?.deal_status === 'FINALIZED';
  const requirements = salesState?.extracted_requirements || {};
  const hasRequirements = Object.keys(requirements).length > 0;

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
                Powered by Groq · Qwen 3 · Intelligent Sales State Tracking
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="chat-secure-badge" role="status">
              <ShieldCheck size={14} />
              Conversations & deals saved in PostgreSQL
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

        {/* ── Sales State & Requirements Summary Bar ─────────────────────── */}
        {activeConversationId !== null && salesState && (
          <div className="sales-state-bar" id="sales-state-bar">
            <div className="sales-state-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className={`sales-stage-badge ${stage.toLowerCase()}`} id="sales-stage-badge">
                  {stage === 'DISCOVERY' && <HelpCircle size={13} />}
                  {stage === 'PRODUCT_MATCHING' && <Layers size={13} />}
                  {stage === 'DEAL_DISCUSSION' && <Handshake size={13} />}
                  {stage === 'DEAL_FINALIZED' && <CheckCircle2 size={13} />}
                  {stage === 'POST_SALE' && <Sparkles size={13} />}
                  Stage: {stage.replace('_', ' ')}
                </span>
                {salesState.product_category && (
                  <span style={{ fontSize: '0.8rem', color: 'var(--color-neutral-600)', fontWeight: 500 }}>
                    Category: <strong>{salesState.product_category.replace('_', ' ').toUpperCase()}</strong>
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: '0.75rem', color: isDealFinalized ? '#15803d' : '#b45309', fontWeight: 600 }}>
                  Deal: {salesState.deal_status}
                </span>
              </div>
            </div>

            {hasRequirements && (
              <div className="sales-requirements-list" id="sales-requirements-list">
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                  Extracted Requirements:
                </span>
                {Object.entries(requirements).map(([k, v]) => (
                  <span key={k} className="sales-req-pill">
                    <strong>{k.replace(/_/g, ' ')}:</strong> {String(v)}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

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
                Loading conversation & deal history...
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
                  Intelligent Sales & Product Advisory
                </h2>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', maxWidth: 540, margin: '0 auto' }}>
                  Ask for any equipment or product need. SalesCompass will identify key requirements,
                  ask targeted follow-up questions, match catalogue products, and safely guide you through
                  deal finalisation before offering cross-sell add-ons.
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

              {/* ── Candidate Matching Products Card Grid ────────────────── */}
              {salesState?.candidate_products && salesState.candidate_products.length > 0 && !isDealFinalized && (
                <div className="sales-candidates-container" id="matching-products-section">
                  <div className="sales-candidates-title">
                    <PackageCheck size={16} color="var(--color-brand-600)" />
                    Matching Products from Catalogue ({salesState.candidate_products.length})
                  </div>
                  <div className="sales-candidates-grid">
                    {salesState.candidate_products.map((prod) => {
                      const isSelected = salesState.selected_product?.sku === prod.sku;
                      return (
                        <div
                          key={prod.sku}
                          className={`sales-candidate-card ${isSelected ? 'selected' : ''}`}
                        >
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                              <h4 style={{ fontSize: '0.875rem', fontWeight: 700, margin: '0 0 2px 0' }}>
                                {prod.name}
                              </h4>
                              <span style={{ fontSize: '0.7rem', padding: '1px 5px', background: '#e0e7ff', color: '#4338ca', borderRadius: 4, fontWeight: 600 }}>
                                {prod.sku}
                              </span>
                            </div>
                            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', margin: '0 0 6px 0' }}>
                              {prod.manufacturer ?? 'Catalog'} · {prod.category ?? 'Equipment'}
                            </p>
                            {prod.snippet && (
                              <p style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', lineHeight: 1.4 }}>
                                {prod.snippet}
                              </p>
                            )}
                          </div>
                          <button
                            className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-outline'}`}
                            onClick={() => handleSelectProduct(prod)}
                            style={{ width: '100%', marginTop: 8, fontSize: '0.75rem', padding: '4px 8px' }}
                          >
                            {isSelected ? '✓ Selected for Deal' : 'Select for Deal'}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* ── Deal Discussion Card ─────────────────────────────────── */}
              {salesState?.selected_product && !isDealFinalized && (
                <div className="deal-card" id="deal-discussion-card">
                  <div className="deal-card-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Handshake size={18} color="#b45309" />
                      <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, color: '#92400e' }}>
                        Deal Discussion & Agreement Terms
                      </h4>
                    </div>
                    <span style={{ fontSize: '0.72rem', color: '#b45309', background: '#fef3c7', padding: '2px 8px', borderRadius: 4, fontWeight: 600 }}>
                      Cross-selling disabled until finalised
                    </span>
                  </div>

                  <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', margin: '4px 0 8px 0' }}>
                    Agreed Item: <strong>{salesState.selected_product.name}</strong> ({salesState.selected_product.sku})
                  </p>

                  <div className="deal-terms-row">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                        Quantity:
                      </label>
                      <div className="deal-qty-stepper">
                        <button
                          onClick={() => setDealQuantity((q) => Math.max(1, q - 1))}
                          type="button"
                          aria-label="Decrease quantity"
                        >
                          -
                        </button>
                        <input
                          type="number"
                          min={1}
                          value={dealQuantity}
                          onChange={(e) => setDealQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                          aria-label="Deal quantity"
                        />
                        <button
                          onClick={() => setDealQuantity((q) => q + 1)}
                          type="button"
                          aria-label="Increase quantity"
                        >
                          +
                        </button>
                      </div>
                    </div>

                    <div style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
                      Unit Price: {salesState.selected_product.price && salesState.selected_product.price.startsWith('$') ? (
                        <strong style={{ color: '#16a34a' }}>{salesState.selected_product.price} (Catalogue verified)</strong>
                      ) : (
                        <span style={{ fontStyle: 'italic', color: 'var(--color-text-muted)' }}>
                          {salesState.selected_product.price ?? 'Catalog quote / standard pricing'} (Quote on request)
                        </span>
                      )}
                    </div>

                    <button
                      className="btn btn-primary btn-sm"
                      onClick={handleConfirmDeal}
                      disabled={isFinalizingDeal}
                      id="confirm-deal-btn"
                      style={{ marginLeft: 'auto', gap: 6, background: '#16a34a', borderColor: '#16a34a' }}
                    >
                      {isFinalizingDeal ? <Spinner size={14} /> : <CheckSquare size={15} />}
                      Explicitly Confirm & Finalise Deal
                    </button>
                  </div>
                </div>
              )}

              {/* ── Finalised Deal Visible Confirmation Banner ───────────── */}
              {isDealFinalized && (
                <div className="deal-finalised-banner" id="deal-finalised-banner">
                  <div className="deal-finalised-info">
                    <CheckCircle2 size={24} color="#16a34a" />
                    <div>
                      <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, color: '#14532d' }}>
                        Deal Finalised — Order Terms Locked
                      </h4>
                      <p style={{ margin: 0, fontSize: '0.78rem', color: '#166534' }}>
                        {salesState?.agreed_quantity ?? 1}x {salesState?.selected_product?.name ?? 'Selected Product'} ({salesState?.selected_product?.sku})
                        {salesState?.agreed_price && (
                          salesState.agreed_price.startsWith('$') ? (
                            <> · <strong>{salesState.agreed_price}</strong></>
                          ) : (
                            <> · <span style={{ fontStyle: 'italic' }}>{salesState.agreed_price} (Quote)</span></>
                          )
                        )}
                        {salesState?.deal_finalized_at && (
                          <> · Confirmed on {format(new Date(salesState.deal_finalized_at), 'MMM d, yyyy HH:mm')}</>
                        )}
                      </p>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {!salesState?.recommendations && (
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={handleLoadRecommendations}
                        disabled={isLoadingRecommendations}
                        id="load-recommendations-btn"
                        style={{ gap: 6 }}
                      >
                        {isLoadingRecommendations ? <Spinner size={14} /> : <Sparkles size={14} />}
                        View Eligible Add-ons & Upgrades
                      </button>
                    )}
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={handleReopenDeal}
                      title="Reopen deal to change quantity or item"
                      id="reopen-deal-btn"
                      style={{ gap: 6, fontSize: '0.75rem' }}
                    >
                      <RefreshCw size={13} />
                      Reopen Deal
                    </button>
                  </div>
                </div>
              )}

              {/* ── Post-Deal Recommendations Section ────────────────────── */}
              {isDealFinalized && salesState?.recommendations && (
                <div className="recommendations-container" id="post-deal-recommendations-section">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Sparkles size={18} color="#7e22ce" />
                      <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, color: '#581c87' }}>
                        Post-Deal Recommendations (Cross-Selling & Upselling)
                      </h4>
                    </div>
                    <span style={{ fontSize: '0.72rem', color: '#7e22ce', background: '#f3e8ff', padding: '2px 8px', borderRadius: 4, fontWeight: 600 }}>
                      Backend Verified Catalogue Recommendations
                    </span>
                  </div>

                  {/* Cross-Sell Accessories */}
                  {salesState.recommendations.cross_sells?.length > 0 && (
                    <div style={{ marginBottom: 14 }}>
                      <h5 style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <PackageCheck size={14} color="var(--color-brand-600)" />
                        Complementary Accessories & Supplies (Cross-Sell)
                      </h5>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
                        {salesState.recommendations.cross_sells.map((rec: RecommendationItem) => (
                          <div key={rec.sku} className="recommendation-card cross-sell">
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span className="rec-type-badge cross-sell">Cross-sell / Accessory</span>
                              <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                                {rec.sku}
                              </span>
                            </div>
                            <h5 style={{ fontSize: '0.825rem', fontWeight: 700, margin: '2px 0' }}>
                              {rec.name}
                            </h5>
                            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                              {rec.relevance_explanation}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Upsell Alternatives */}
                  {salesState.recommendations.upsells?.length > 0 && (
                    <div>
                      <h5 style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <ArrowUpRight size={14} color="#9333ea" />
                        Higher-Capacity Upgrades for Future Scale (Upsell)
                      </h5>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
                        {salesState.recommendations.upsells.map((rec: RecommendationItem) => (
                          <div key={rec.sku} className="recommendation-card upsell">
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span className="rec-type-badge upsell">Upsell / Upgrade Option</span>
                              <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                                {rec.sku}
                              </span>
                            </div>
                            <h5 style={{ fontSize: '0.825rem', fontWeight: 700, margin: '2px 0' }}>
                              {rec.name}
                            </h5>
                            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                              {rec.relevance_explanation}
                            </p>
                            {rec.trade_off_note && (
                              <p style={{ fontSize: '0.72rem', color: '#6b21a8', background: '#f5f3ff', padding: '4px 6px', borderRadius: 4, margin: '4px 0 0 0' }}>
                                💡 Note: {rec.trade_off_note}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

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

        {/* ── Suggested Follow-Up Questions Quick-Reply Chips ───────────── */}
        {suggestedQuestions.length > 0 && !isGenerating && (
          <div className="quick-questions-panel" id="quick-questions-panel">
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
              Suggested Answers / Questions:
            </span>
            {suggestedQuestions.map((q, idx) => (
              <button
                key={idx}
                className="quick-q-chip"
                onClick={() => sendMessage(q)}
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input Area */}
        <div className="chat-input-area">
          <div className="chat-input-inner">
            <textarea
              ref={textareaRef}
              className="chat-input-field"
              placeholder={
                isGenerating ? 'Generating response…' : 'Ask about any product or answer follow-up questions…'
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
