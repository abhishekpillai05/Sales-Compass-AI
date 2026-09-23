import React, { useState, useCallback } from 'react';
import { Search, Filter, ChevronDown, ChevronUp, Package } from 'lucide-react';
import { searchApi } from '@/api/search';
import { getErrorMessage } from '@/contexts/AuthContext';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { Spinner } from '@/components/common/Spinner';
import type { RetrievedChunk, SearchRequest } from '@/types/api';

// ── Score badge ──────────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const cls =
    score >= 0.7 ? 'score-high' : score >= 0.5 ? 'score-medium' : 'score-low';
  return <span className={`score-badge ${cls}`}>⬟ {pct}%</span>;
}

// ── Product image placeholder ─────────────────────────────────────────────────

function ImagePlaceholder() {
  return (
    <div
      className="product-image-placeholder"
      style={{ width: 80, height: 80, flexShrink: 0 }}
      title="No product image available — the backend does not currently provide image URLs"
    >
      <Package size={24} style={{ opacity: 0.4 }} />
      <span style={{ fontSize: '0.65rem', opacity: 0.5 }}>No image</span>
    </div>
  );
}

// ── Result card ───────────────────────────────────────────────────────────────

function ResultCard({ chunk, index }: { chunk: RetrievedChunk; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const m = chunk.metadata;

  const metaItems = [
    { label: 'SKU', value: m.sku },
    { label: 'Category', value: m.category },
    { label: 'Manufacturer', value: m.manufacturer },
    { label: 'File', value: m.filename },
    { label: 'Page', value: m.page_number != null ? String(m.page_number) : null },
    { label: 'Sheet', value: m.sheet_name },
    { label: 'Row', value: m.row_number != null ? String(m.row_number) : null },
    { label: 'Doc ID', value: chunk.document_id != null ? String(chunk.document_id) : null },
  ].filter(item => item.value != null && item.value !== '');

  return (
    <article className="result-card" aria-label={`Result ${index + 1}`}>
      <div className="result-card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ImagePlaceholder />
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <ScoreBadge score={chunk.score} />
              {m.sku && (
                <span className="badge badge-brand">
                  SKU: {m.sku}
                </span>
              )}
              {m.category && (
                <span className="badge badge-neutral">{m.category}</span>
              )}
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              {m.filename && <span>{m.filename}</span>}
              {m.manufacturer && <span> · {m.manufacturer}</span>}
            </div>
          </div>
        </div>
        <span
          style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', flexShrink: 0 }}
        >
          #{index + 1}
        </span>
      </div>

      <div className="result-card-body">
        <p className={`result-text${expanded ? ' expanded' : ''}`}>
          {chunk.text || <em style={{ color: 'var(--color-text-muted)' }}>No text content</em>}
        </p>

        {chunk.text && chunk.text.length > 200 && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setExpanded(!expanded)}
            style={{ marginTop: 6, padding: '4px 0', gap: 4 }}
          >
            {expanded ? <><ChevronUp size={13} /> Show less</> : <><ChevronDown size={13} /> Show more</>}
          </button>
        )}

        {metaItems.length > 0 && (
          <div className="result-meta-grid" style={{ marginTop: 14 }}>
            {metaItems.map(({ label, value }) => (
              <div key={label} className="result-meta-item">
                <span className="result-meta-label">{label}</span>
                <span className="result-meta-value">{value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

// ── Search Filters sidebar ────────────────────────────────────────────────────

interface FiltersProps {
  params: SearchRequest;
  onChange: (p: Partial<SearchRequest>) => void;
  onSearch: () => void;
  isLoading: boolean;
}

function SearchFilters({ params, onChange, onSearch, isLoading }: FiltersProps) {
  return (
    <aside className="search-filters">
      <div className="card">
        <div className="card-header">
          <h2 style={{ fontSize: '0.9375rem', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: 7 }}>
            <Filter size={15} /> Filters
          </h2>
        </div>
        <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Query */}
          <div className="input-wrapper">
            <label className="input-label" htmlFor="search-query">Search query *</label>
            <input
              id="search-query"
              className="input"
              placeholder="e.g. industrial floor cleaner"
              value={params.query}
              onChange={e => onChange({ query: e.target.value })}
              onKeyDown={e => { if (e.key === 'Enter') onSearch(); }}
            />
          </div>

          {/* Top K */}
          <div className="slider-wrapper">
            <div className="slider-header">
              <label className="input-label" htmlFor="search-top-k">Results (top_k)</label>
              <span className="slider-value">{params.top_k}</span>
            </div>
            <input
              id="search-top-k"
              type="range"
              min={1}
              max={20}
              value={params.top_k}
              onChange={e => onChange({ top_k: Number(e.target.value) })}
            />
          </div>

          {/* Score threshold */}
          <div className="slider-wrapper">
            <div className="slider-header">
              <label className="input-label" htmlFor="search-threshold">Score threshold</label>
              <span className="slider-value">{(params.score_threshold ?? 0).toFixed(2)}</span>
            </div>
            <input
              id="search-threshold"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={params.score_threshold ?? 0}
              onChange={e => onChange({ score_threshold: Number(e.target.value) })}
            />
          </div>

          {/* Optional filters */}
          <div style={{ height: 1, background: 'var(--color-border)' }} />
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', margin: 0 }}>
            Optional Filters
          </p>

          {[
            { id: 'filter-sku', label: 'SKU', key: 'sku', placeholder: 'e.g. BD-43-40' },
            { id: 'filter-category', label: 'Category', key: 'category', placeholder: 'e.g. Sweepers' },
            { id: 'filter-manufacturer', label: 'Manufacturer', key: 'manufacturer', placeholder: 'e.g. Kärcher' },
          ].map(({ id, label, key, placeholder }) => (
            <div key={key} className="input-wrapper">
              <label className="input-label" htmlFor={id}>{label}</label>
              <input
                id={id}
                className="input"
                placeholder={placeholder}
                value={(params as unknown as Record<string, unknown>)[key] as string ?? ''}
                onChange={e =>
                  onChange({ [key]: e.target.value || null } as Partial<SearchRequest>)
                }
              />
            </div>
          ))}

          {/* Document ID */}
          <div className="input-wrapper">
            <label className="input-label" htmlFor="filter-doc-id">Document ID</label>
            <input
              id="filter-doc-id"
              className="input"
              type="number"
              placeholder="e.g. 3"
              value={params.document_id ?? ''}
              onChange={e =>
                onChange({ document_id: e.target.value ? Number(e.target.value) : null })
              }
            />
          </div>

          <button
            id="search-submit-btn"
            className="btn btn-primary"
            onClick={onSearch}
            disabled={!params.query.trim() || isLoading}
            style={{ width: '100%' }}
          >
            {isLoading ? <><Spinner size={15} /> Searching…</> : <><Search size={15} /> Search</>}
          </button>
        </div>
      </div>
    </aside>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function SearchPage() {
  const [params, setParams] = useState<SearchRequest>({
    query: '',
    top_k: 5,
    score_threshold: 0.0,
    sku: null,
    category: null,
    manufacturer: null,
    document_id: null,
  });

  const [results, setResults] = useState<RetrievedChunk[] | null>(null);
  const [totalResults, setTotalResults] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [searched, setSearched] = useState(false);

  const handleSearch = useCallback(async () => {
    if (!params.query.trim()) return;
    setIsLoading(true);
    setError(null);
    setSearched(true);
    try {
      const res = await searchApi.search(params);
      setResults(res.results);
      setTotalResults(res.total_results);
    } catch (err) {
      setError(err);
      setResults(null);
    } finally {
      setIsLoading(false);
    }
  }, [params]);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-neutral-50)' }}>
      {/* Header */}
      <div className="page-header">
        <div className="page-header-inner">
          <div>
            <h1 className="page-title">Product Explorer</h1>
            <p className="page-subtitle">
              Vector search across the product knowledge base
            </p>
          </div>
          {results !== null && (
            <span className="badge badge-brand" style={{ alignSelf: 'center' }}>
              {totalResults} result{totalResults !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      <div className="search-layout">
        <SearchFilters
          params={params}
          onChange={p => setParams(prev => ({ ...prev, ...p }))}
          onSearch={handleSearch}
          isLoading={isLoading}
        />

        <div>
          {isLoading ? (
            <div className="empty-state">
              <Spinner size={32} />
              <span style={{ color: 'var(--color-text-muted)' }}>Searching knowledge base…</span>
            </div>
          ) : error ? (
            <ErrorState error={error} onRetry={handleSearch} />
          ) : results !== null && results.length === 0 ? (
            <EmptyState
              icon={<Search size={24} />}
              title="No results found"
              description="Try adjusting your query, lowering the score threshold, or removing optional filters."
            />
          ) : !searched ? (
            <EmptyState
              icon={<Search size={24} />}
              title="Enter a search query"
              description="Use the filters on the left to search through indexed product documents."
            />
          ) : results && results.length > 0 ? (
            <div className="search-results-list">
              {results.map((chunk, i) => (
                <ResultCard key={chunk.chunk_id ?? i} chunk={chunk} index={i} />
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
