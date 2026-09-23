import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
  type KeyboardEvent,
} from 'react';
import { Send, Trash2, Compass, Info } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { askApi } from '@/api/ask';
import { getErrorMessage } from '@/contexts/AuthContext';
import { LoadingDots } from '@/components/common/Spinner';
import { format } from 'date-fns';
import type { ChatMessage, SourceResponse } from '@/types/api';

const SUGGESTIONS = [
  'What is the Kärcher BD 43/40?',
  'What are the main features of this product?',
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
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating]);

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

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

      setMessages(prev => [...prev, userMsg]);
      setInput('');
      setIsGenerating(true);

      try {
        const res = await askApi.ask({ query: trimmed, top_k: 5 });
        const assistantMsg: ChatMessage = {
          id: newId(),
          role: 'assistant',
          content: res.answer,
          sources: res.sources,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, assistantMsg]);
      } catch (err) {
        const errMsg: ChatMessage = {
          id: newId(),
          role: 'assistant',
          content: getErrorMessage(err),
          timestamp: new Date(),
          isError: true,
        };
        setMessages(prev => [...prev, errMsg]);
      } finally {
        setIsGenerating(false);
      }
    },
    [isGenerating],
  );

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="chat-layout">
      {/* Temporary history notice */}
      <div className="notice-banner" role="status">
        <Info size={14} style={{ flexShrink: 0 }} />
        <span>
          <strong>Session-only history</strong> — conversation history is stored in
          your browser tab only and is not persisted by the server.
        </span>
      </div>

      {/* Page header */}
      <div
        style={{
          padding: '14px 24px',
          background: 'white',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <h1 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>
            AI Sales Assistant
          </h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', margin: 0 }}>
            Powered by Groq · Qwen 3.6-27B
          </p>
        </div>
        {hasMessages && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setMessages([])}
            aria-label="Clear conversation"
          >
            <Trash2 size={14} />
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {!hasMessages ? (
          // Empty state
          <div className="chat-empty">
            <div className="chat-welcome-icon">
              <Compass size={36} color="var(--color-brand-600)" />
            </div>
            <div style={{ textAlign: 'center' }}>
              <h2 style={{ fontSize: '1.25rem', marginBottom: 8 }}>
                How can I help you today?
              </h2>
              <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                Ask me anything about products in the catalogue. I'll search the knowledge
                base and generate an answer based on the retrieved content.
              </p>
            </div>
            <div className="chat-suggestions">
              {SUGGESTIONS.map(s => (
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
            {messages.map(msg => (
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

      {/* Input */}
      <div className="chat-input-area">
        <div className="chat-input-inner">
          <textarea
            ref={textareaRef}
            className="chat-input-field"
            placeholder={
              isGenerating ? 'Generating response…' : 'Ask about any product…'
            }
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isGenerating}
            rows={1}
            aria-label="Chat input"
          />
          <button
            className="chat-send-btn"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isGenerating}
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
    </div>
  );
}
