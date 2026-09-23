import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Upload,
  File,
  CheckCircle,
  XCircle,
  FileText,
  Table,
  FileType,
} from 'lucide-react';
import { uploadApi } from '@/api/upload';
import { getErrorMessage } from '@/contexts/AuthContext';
import { Spinner } from '@/components/common/Spinner';
import type { UploadResponse } from '@/types/api';

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'text/csv': ['.csv'],
};

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return <FileType size={20} style={{ color: '#ef4444' }} />;
  if (ext === 'csv') return <Table size={20} style={{ color: '#10b981' }} />;
  return <FileText size={20} style={{ color: '#6366f1' }} />;
}

interface UploadResult {
  file: string;
  response?: UploadResponse;
  error?: string;
}

export function UploadPage() {
  const [pending, setPending] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [results, setResults] = useState<UploadResult[]>([]);

  const onDrop = useCallback((accepted: File[]) => {
    setPending(prev => {
      const names = new Set(prev.map(f => f.name));
      return [...prev, ...accepted.filter(f => !names.has(f.name))];
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 50 * 1024 * 1024, // 50 MB
    multiple: true,
  });

  function removeFile(name: string) {
    setPending(prev => prev.filter(f => f.name !== name));
  }

  async function handleUpload() {
    if (pending.length === 0 || isUploading) return;
    setIsUploading(true);
    setResults([]);

    const uploadResults: UploadResult[] = [];
    for (const file of pending) {
      try {
        const res = await uploadApi.upload(file);
        uploadResults.push({ file: file.name, response: res });
      } catch (err) {
        uploadResults.push({ file: file.name, error: getErrorMessage(err) });
      }
    }
    setResults(uploadResults);
    setPending([]);
    setIsUploading(false);
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-neutral-50)' }}>
      {/* Header */}
      <div className="page-header">
        <div className="page-header-inner">
          <div>
            <h1 className="page-title">Upload Documents</h1>
            <p className="page-subtitle">
              Add product catalogues and data sheets to the knowledge base
            </p>
          </div>
        </div>
      </div>

      <div className="upload-layout">
        {/* Info */}
        <div className="alert alert-info" style={{ marginBottom: 20 }}>
          <Upload size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <strong>Accepted formats:</strong> PDF, Excel (.xlsx, .xls), CSV · Max 50 MB per file.
            Each file is ingested, chunked, embedded, and indexed into Qdrant automatically.
          </div>
        </div>

        {/* Dropzone */}
        <div
          {...getRootProps()}
          className={`dropzone${isDragActive ? ' drag-over' : ''}`}
          role="button"
          aria-label="File upload area — click or drag files here"
          tabIndex={0}
          id="upload-dropzone"
        >
          <input {...getInputProps()} id="upload-file-input" />
          <div className="dropzone-icon">
            <Upload size={28} color="var(--color-brand-600)" />
          </div>
          <div style={{ fontWeight: 600, fontSize: '1rem', marginBottom: 6 }}>
            {isDragActive ? 'Drop files here…' : 'Drag & drop files here'}
          </div>
          <div style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginBottom: 16 }}>
            or click to browse
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
            {['PDF', 'XLSX', 'XLS', 'CSV'].map(t => (
              <span key={t} className="badge badge-neutral">{t}</span>
            ))}
          </div>
        </div>

        {/* File list */}
        {pending.length > 0 && (
          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>
                {pending.length} file{pending.length !== 1 ? 's' : ''} ready to upload
              </span>
              <button className="btn btn-ghost btn-sm" onClick={() => setPending([])}>
                Clear all
              </button>
            </div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {pending.map(file => (
                <div
                  key={file.name}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 12px', background: 'var(--color-neutral-50)',
                    border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)',
                  }}
                >
                  {fileIcon(file.name)}
                  <span style={{ flex: 1, fontSize: '0.875rem', fontWeight: 500 }}>{file.name}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                    {(file.size / 1024).toFixed(0)} KB
                  </span>
                  <button
                    className="btn btn-ghost btn-icon btn-sm"
                    onClick={() => removeFile(file.name)}
                    aria-label={`Remove ${file.name}`}
                  >
                    <XCircle size={15} />
                  </button>
                </div>
              ))}
            </div>

            <div style={{ padding: '0 20px 20px' }}>
              {isUploading && (
                <div className="progress-bar-wrapper" style={{ marginBottom: 14 }}>
                  <div className="progress-bar-indeterminate" />
                </div>
              )}
              <button
                id="upload-submit-btn"
                className="btn btn-primary"
                style={{ width: '100%' }}
                onClick={handleUpload}
                disabled={isUploading}
              >
                {isUploading ? (
                  <><Spinner size={16} /> Uploading & indexing…</>
                ) : (
                  <><Upload size={16} /> Upload {pending.length} file{pending.length !== 1 ? 's' : ''}</>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Results */}
        {results.length > 0 && (
          <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600 }}>Upload Results</h2>
            {results.map(r => (
              <div
                key={r.file}
                className={`alert ${r.error ? 'alert-error' : 'alert-success'}`}
              >
                {r.error ? (
                  <XCircle size={16} style={{ flexShrink: 0 }} />
                ) : (
                  <CheckCircle size={16} style={{ flexShrink: 0 }} />
                )}
                <div>
                  <strong>{r.file}</strong>
                  {r.error ? (
                    <div style={{ marginTop: 3 }}>{r.error}</div>
                  ) : r.response ? (
                    <div style={{ marginTop: 3, fontSize: '0.8125rem' }}>
                      Document ID: {r.response.document_id} · {r.response.chunks_created} chunks created ·{' '}
                      {r.response.chunks_indexed} indexed
                      {r.response.chunks_index_failed > 0 && (
                        <span style={{ color: '#92400e' }}>
                          {' '}· {r.response.chunks_index_failed} failed
                        </span>
                      )}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
