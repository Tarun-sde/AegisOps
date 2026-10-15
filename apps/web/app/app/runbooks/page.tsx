"use client";

import { useEffect, useState, useTransition } from "react";
import {
  deleteRunbook,
  getRunbooks,
  reindexRunbook,
  searchRunbooks,
  uploadRunbook,
  type RetrievedChunk,
  type Runbook,
} from "../../lib/api";

export default function RunbooksPage() {
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Upload Form state
  const [filename, setFilename] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [isUploading, startUpload] = useTransition();

  // Playground Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"hybrid" | "vector" | "keyword">(
    "hybrid",
  );
  const [searchLimit, setSearchLimit] = useState(5);
  const [searchResults, setSearchResults] = useState<RetrievedChunk[]>([]);
  const [isSearching, startSearch] = useTransition();
  const [searchError, setSearchError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  // Action status message
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    setFetchError(null);
    const { data, error } = await getRunbooks();
    if (error) {
      setFetchError(error);
    } else if (data) {
      setRunbooks(data.items);
    }
    setLoading(false);
  }

  useEffect(() => {
    loadData();
  }, []);

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setFilename(file.name);
    if (!title) {
      setTitle(file.name.replace(/\.[^/.]+$/, ""));
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result;
      if (typeof text === "string") {
        setContent(text);
      }
    };
    reader.readAsText(file);
  }

  function handleUploadSubmit(e: React.FormEvent) {
    e.preventDefault();
    setUploadError(null);
    setUploadSuccess(null);

    if (!filename.trim()) {
      setUploadError("Filename is required.");
      return;
    }
    if (!content.trim()) {
      setUploadError("File content cannot be empty.");
      return;
    }

    startUpload(async () => {
      const { data, error } = await uploadRunbook({
        filename: filename.trim(),
        title: title.trim() || undefined,
        content: content.trim(),
      });

      if (error) {
        setUploadError(error);
      } else if (data) {
        setUploadSuccess(
          `Runbook '${data.filename}' (v${data.version}) submitted for ingestion.`,
        );
        setFilename("");
        setTitle("");
        setContent("");
        await loadData();
      }
    });
  }

  function handleDelete(id: string, name: string) {
    if (
      !window.confirm(
        `Are you sure you want to delete '${name}'? This will remove all vector and full-text index chunks.`,
      )
    ) {
      return;
    }

    startUpload(async () => {
      const { success, error } = await deleteRunbook(id);
      if (!success) {
        setActionMessage(`Failed to delete: ${error}`);
      } else {
        setActionMessage(`Runbook '${name}' successfully deleted.`);
        await loadData();
      }
    });
  }

  function handleReindex(id: string, name: string) {
    startUpload(async () => {
      const { data, error } = await reindexRunbook(id);
      if (error) {
        setActionMessage(`Reindex error: ${error}`);
      } else if (data) {
        setActionMessage(
          `Runbook '${name}' reindexing dispatched (status: ${data.status}).`,
        );
        await loadData();
      }
    });
  }

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearchError(null);
    setHasSearched(true);

    startSearch(async () => {
      const { data, error } = await searchRunbooks(
        searchQuery.trim(),
        searchMode,
        searchLimit,
      );
      if (error) {
        setSearchError(error);
        setSearchResults([]);
      } else if (data) {
        setSearchResults(data.results);
      }
    });
  }

  function renderStatusBadge(status: string) {
    const s = status.toUpperCase();
    if (s === "READY") {
      return (
        <span
          className="badge"
          style={{
            background: "var(--bg-surface)",
            borderColor: "var(--border-default)",
            color: "var(--status-success-text)",
          }}
        >
          READY · INDEXED
        </span>
      );
    }
    if (s === "FAILED") {
      return (
        <span
          className="badge"
          style={{
            background: "var(--bg-surface)",
            borderColor: "var(--status-error-border)",
            color: "var(--status-error-text)",
          }}
        >
          FAILED
        </span>
      );
    }
    return (
      <span
        className="badge"
        style={{
          background: "var(--status-warning-bg)",
          borderColor: "var(--status-warning-border)",
          color: "var(--status-warning-text)",
        }}
      >
        {s}
      </span>
    );
  }

  return (
    <main id="main" className="ws-content">
      <p className="eyebrow">Workspace / Knowledge Subsystem</p>
      <div className="heading">
        <h1>Operational Runbooks</h1>
        <span className="badge">Scoped runbook knowledge</span>
      </div>
      <p className="intro">
        Tenant-scoped knowledge base providing verified troubleshooting runbooks
        and procedures grounded via pgvector and PostgreSQL full-text search.
      </p>

      {actionMessage && (
        <div
          className="panel"
          style={{
            borderColor: "var(--border-default)",
            background: "var(--bg-surface)",
            color: "var(--status-success-text)",
            padding: "16px",
            marginBottom: "20px",
          }}
        >
          {actionMessage}
        </div>
      )}

      {/* TOP SECTION: UPLOAD & SEARCH PLAYGROUND */}
      <div className="grid">
        {/* Upload Panel */}
        <section aria-labelledby="upload-title" className="panel">
          <p className="eyebrow">Ingestion Pipeline</p>
          <h2 id="upload-title">Upload Runbook</h2>
          <p>
            Upload trusted operational documentation (.md or .txt). Secrets are
            automatically redacted prior to semantic chunking and embedding.
          </p>

          <form onSubmit={handleUploadSubmit} style={{ marginTop: "16px" }}>
            <div style={{ marginBottom: "12px" }}>
              <label
                htmlFor="file-input"
                style={{
                  display: "block",
                  marginBottom: "4px",
                  fontSize: "14px",
                  color: "var(--text-secondary)",
                }}
              >
                Select File (.md, .txt)
              </label>
              <input
                id="file-input"
                type="file"
                accept=".md,.markdown,.txt"
                onChange={handleFileUpload}
                style={{
                  width: "100%",
                  padding: "8px",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "6px",
                  color: "var(--text-primary)",
                }}
              />
            </div>

            <div style={{ marginBottom: "12px" }}>
              <label
                htmlFor="title-input"
                style={{
                  display: "block",
                  marginBottom: "4px",
                  fontSize: "14px",
                  color: "var(--text-secondary)",
                }}
              >
                Document Title (Optional)
              </label>
              <input
                id="title-input"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., PostgreSQL Connection Pool Recovery"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "6px",
                  color: "var(--text-primary)",
                }}
              />
            </div>

            <div style={{ marginBottom: "16px" }}>
              <label
                htmlFor="content-input"
                style={{
                  display: "block",
                  marginBottom: "4px",
                  fontSize: "14px",
                  color: "var(--text-secondary)",
                }}
              >
                Markdown Content
              </label>
              <textarea
                id="content-input"
                rows={6}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="# Runbook Title&#10;&#10;## Diagnostic Procedures&#10;Steps to troubleshoot..."
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "6px",
                  color: "var(--text-primary)",
                  fontFamily: "monospace",
                  fontSize: "0.875rem",
                }}
              />
            </div>

            {uploadError && (
              <p
                style={{
                  color: "var(--status-error-text)",
                  fontSize: "14px",
                  marginBottom: "12px",
                }}
              >
                {uploadError}
              </p>
            )}
            {uploadSuccess && (
              <p
                style={{
                  color: "var(--status-success-text)",
                  fontSize: "14px",
                  marginBottom: "12px",
                }}
              >
                {uploadSuccess}
              </p>
            )}

            <button
              type="submit"
              disabled={isUploading}
              style={{
                background: "var(--status-success-text)",
                color: "var(--bg-surface)",
                border: "none",
                padding: "10px 18px",
                borderRadius: "6px",
                fontWeight: 600,
                cursor: isUploading ? "not-allowed" : "pointer",
                opacity: isUploading ? 0.6 : 1,
              }}
            >
              {isUploading ? "Processing Ingestion..." : "Submit Runbook"}
            </button>
          </form>
        </section>

        {/* Retrieval Playground */}
        <section aria-labelledby="search-title" className="panel">
          <p className="eyebrow">Retrieval Verification</p>
          <h2 id="search-title">Retrieval Playground</h2>
          <p>
            Test hybrid search (Reciprocal Rank Fusion k=60) against
            tenant-scoped runbook chunks.
          </p>

          <form onSubmit={handleSearchSubmit} style={{ marginTop: "16px" }}>
            <div style={{ marginBottom: "12px" }}>
              <label
                htmlFor="query-input"
                style={{
                  display: "block",
                  marginBottom: "4px",
                  fontSize: "14px",
                  color: "var(--text-secondary)",
                }}
              >
                Operational Query
              </label>
              <input
                id="query-input"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="e.g., How do we resolve connection pool exhaustion?"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "6px",
                  color: "var(--text-primary)",
                }}
              />
            </div>

            <div style={{ display: "flex", gap: "16px", marginBottom: "16px" }}>
              <div style={{ flex: 1 }}>
                <label
                  htmlFor="mode-select"
                  style={{
                    display: "block",
                    marginBottom: "4px",
                    fontSize: "14px",
                    color: "var(--text-secondary)",
                  }}
                >
                  Retrieval Mode
                </label>
                <select
                  id="mode-select"
                  value={searchMode}
                  onChange={(e) =>
                    setSearchMode(
                      e.target.value as "hybrid" | "vector" | "keyword",
                    )
                  }
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border-default)",
                    borderRadius: "6px",
                    color: "var(--text-primary)",
                  }}
                >
                  <option value="hybrid">Hybrid (RRF k=60)</option>
                  <option value="vector">Vector Only (pgvector cosine)</option>
                  <option value="keyword">Keyword Only (PostgreSQL FTS)</option>
                </select>
              </div>

              <div style={{ width: "90px" }}>
                <label
                  htmlFor="limit-select"
                  style={{
                    display: "block",
                    marginBottom: "4px",
                    fontSize: "14px",
                    color: "var(--text-secondary)",
                  }}
                >
                  Limit
                </label>
                <select
                  id="limit-select"
                  value={searchLimit}
                  onChange={(e) => setSearchLimit(Number(e.target.value))}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border-default)",
                    borderRadius: "6px",
                    color: "var(--text-primary)",
                  }}
                >
                  <option value={3}>Top 3</option>
                  <option value={5}>Top 5</option>
                  <option value={10}>Top 10</option>
                </select>
              </div>
            </div>

            {searchError && (
              <p
                style={{
                  color: "var(--status-error-text)",
                  fontSize: "14px",
                  marginBottom: "12px",
                }}
              >
                {searchError}
              </p>
            )}

            <button
              type="submit"
              disabled={isSearching}
              style={{
                background: "var(--status-success-bg)",
                color: "var(--status-success-text)",
                border: "1px solid var(--border-default)",
                padding: "10px 18px",
                borderRadius: "6px",
                fontWeight: 600,
                cursor: isSearching ? "not-allowed" : "pointer",
              }}
            >
              {isSearching ? "Retrieving..." : "Search Knowledge"}
            </button>
          </form>
        </section>
      </div>

      {/* SEARCH RESULTS DISPLAY */}
      {hasSearched && (
        <section
          aria-labelledby="results-title"
          className="panel"
          style={{ marginTop: "24px" }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <p className="eyebrow">Search Results</p>
              <h2 id="results-title">
                {searchResults.length} Match(es) for &ldquo;{searchQuery}&rdquo;
              </h2>
            </div>
            <span className="badge">Mode: {searchMode.toUpperCase()}</span>
          </div>

          {searchResults.length === 0 ? (
            <p style={{ marginTop: "16px", color: "var(--text-secondary)" }}>
              No relevant runbook sections matched this query within the
              authorized scope.
            </p>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "16px",
                marginTop: "16px",
              }}
            >
              {searchResults.map((chunk, idx) => (
                <div
                  key={chunk.chunk_id}
                  style={{
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border-default)",
                    borderRadius: "8px",
                    padding: "16px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      marginBottom: "8px",
                    }}
                  >
                    <div>
                      <span
                        style={{
                          fontSize: "0.875rem",
                          fontFamily: "monospace",
                          color: "var(--status-success-text)",
                          marginRight: "8px",
                        }}
                      >
                        #{idx + 1}
                      </span>
                      <strong
                        style={{
                          fontSize: "15px",
                          color: "var(--text-primary)",
                        }}
                      >
                        {chunk.title}
                      </strong>
                      <span
                        style={{
                          fontSize: "0.875rem",
                          color: "var(--text-secondary)",
                          marginLeft: "8px",
                        }}
                      >
                        v{chunk.document_version} · {chunk.section_path}
                      </span>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        gap: "8px",
                        alignItems: "center",
                      }}
                    >
                      <span
                        className="badge"
                        style={{
                          fontSize: "0.875rem",
                          padding: "4px 8px",
                          background: "var(--bg-surface)",
                        }}
                      >
                        Score: {chunk.relevance_score.toFixed(4)}
                      </span>
                      <code
                        style={{
                          fontSize: "0.875rem",
                          background: "var(--bg-surface)",
                          padding: "3px 6px",
                          borderRadius: "4px",
                          color: "var(--status-success-text)",
                        }}
                      >
                        {chunk.evidence_id}
                      </code>
                    </div>
                  </div>

                  <pre
                    style={{
                      margin: "8px 0 0 0",
                      padding: "12px",
                      background: "var(--bg-surface)",
                      borderRadius: "6px",
                      fontSize: "0.875rem",
                      color: "var(--text-primary)",
                      whiteSpace: "pre-wrap",
                      fontFamily: "monospace",
                      lineHeight: "1.5",
                    }}
                  >
                    {chunk.content}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* DOCUMENT INVENTORY TABLE */}
      <section
        aria-labelledby="runbook-list-title"
        className="panel"
        style={{ marginTop: "24px" }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <p className="eyebrow">Document Inventory</p>
            <h2 id="runbook-list-title">
              Indexed Runbooks ({runbooks.length})
            </h2>
          </div>
          <button
            type="button"
            onClick={loadData}
            style={{
              background: "transparent",
              color: "var(--status-success-text)",
              border: "1px solid var(--border-default)",
              padding: "6px 14px",
              borderRadius: "5px",
              fontSize: "0.875rem",
              cursor: "pointer",
            }}
          >
            Refresh
          </button>
        </div>

        {fetchError ? (
          <div style={{ marginTop: "16px", color: "var(--status-error-text)" }}>
            Failed to load runbooks: {fetchError}
          </div>
        ) : loading ? (
          <p style={{ marginTop: "16px" }}>Loading runbooks...</p>
        ) : runbooks.length === 0 ? (
          <div style={{ marginTop: "16px" }}>
            <p>
              No runbooks found. Upload a markdown file above (e.g. Postgres
              Connection Pool Runbook) to index operational guidance for
              investigations.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: "auto", marginTop: "16px" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                textAlign: "left",
                fontSize: "14px",
              }}
            >
              <thead>
                <tr
                  style={{
                    borderBottom: "1px solid var(--border-default)",
                    color: "var(--text-secondary)",
                  }}
                >
                  <th style={{ padding: "10px 12px" }}>Title / Filename</th>
                  <th style={{ padding: "10px 12px" }}>Version</th>
                  <th style={{ padding: "10px 12px" }}>Status</th>
                  <th style={{ padding: "10px 12px" }}>Chunks</th>
                  <th style={{ padding: "10px 12px" }}>Indexed At</th>
                  <th style={{ padding: "10px 12px", textAlign: "right" }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {runbooks.map((doc) => (
                  <tr
                    key={doc.id}
                    style={{ borderBottom: "1px solid var(--border-default)" }}
                  >
                    <td style={{ padding: "12px" }}>
                      <strong>{doc.title}</strong>
                      <div
                        style={{
                          fontSize: "0.875rem",
                          color: "var(--text-secondary)",
                          marginTop: "2px",
                        }}
                      >
                        {doc.filename}
                      </div>
                      {doc.error_message && (
                        <div
                          style={{
                            fontSize: "0.875rem",
                            color: "var(--status-error-text)",
                            marginTop: "4px",
                          }}
                        >
                          Error: {doc.error_message}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: "12px" }}>
                      <span
                        style={{
                          background: "var(--bg-surface)",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          fontFamily: "monospace",
                          fontSize: "0.875rem",
                        }}
                      >
                        v{doc.version}
                      </span>
                    </td>
                    <td style={{ padding: "12px" }}>
                      {renderStatusBadge(doc.status)}
                    </td>
                    <td style={{ padding: "12px" }}>{doc.chunk_count}</td>
                    <td
                      style={{
                        padding: "12px",
                        color: "var(--text-secondary)",
                        fontSize: "0.875rem",
                      }}
                    >
                      {doc.indexed_at
                        ? new Date(doc.indexed_at).toLocaleString()
                        : "Pending"}
                    </td>
                    <td style={{ padding: "12px", textAlign: "right" }}>
                      <div
                        style={{
                          display: "flex",
                          gap: "8px",
                          justifyContent: "flex-end",
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => handleReindex(doc.id, doc.title)}
                          style={{
                            background: "transparent",
                            border: "1px solid var(--border-default)",
                            color: "var(--status-success-text)",
                            borderRadius: "4px",
                            padding: "4px 8px",
                            fontSize: "0.875rem",
                            cursor: "pointer",
                          }}
                        >
                          Reindex
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(doc.id, doc.title)}
                          style={{
                            background: "transparent",
                            border: "1px solid var(--status-error-border)",
                            color: "var(--status-error-text)",
                            borderRadius: "4px",
                            padding: "4px 8px",
                            fontSize: "0.875rem",
                            cursor: "pointer",
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
