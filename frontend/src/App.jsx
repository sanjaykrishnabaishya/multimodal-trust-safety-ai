import { useEffect, useMemo, useState } from "react";
import "./App.css";


const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8010";

const SOURCE_CONTEXTS = [
  { value: "user", label: "User-generated content" },
  { value: "news", label: "News reporting" },
  { value: "education", label: "Educational content" },
  { value: "art", label: "Art or museum" },
  { value: "medical", label: "Medical content" },
  { value: "gaming", label: "Gaming" },
  { value: "satire", label: "Satire" },
  { value: "history", label: "Historical content" },
];

const ACCEPTED_FILES =
  ".txt,.pdf,.docx,.jpg,.jpeg,.png,.webp,.mp4,.mov,.avi,.mkv,.webm";


function formatLabel(value) {
  if (!value) return "Not available";

  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function getCategoryClass(category) {
  if (category === "Normal/Ignore") {
    return "category-safe";
  }

  if (
    category === "Child Abuse" ||
    category === "Violence"
  ) {
    return "category-critical";
  }

  if (
    category === "Scam" ||
    category === "Hate Speech" ||
    category === "Nudity"
  ) {
    return "category-high";
  }

  return "category-medium";
}


function ResultPanel({ result }) {
  if (!result) {
    return (
      <section className="empty-result">
        <div className="empty-symbol">TS</div>
        <h2>No analysis yet</h2>
        <p>
          Submit text or upload a file to see the
          moderation decision and supporting evidence.
        </p>
      </section>
    );
  }

  const confidencePercent = Math.round(
    (result.confidence || 0) * 100
  );

  const evidence =
    result.retrieved_evidence || [];

  const consensus =
    result.rag_consensus || {};

  return (
    <section className="result-panel">
      <div className="result-heading">
        <div>
          <p className="eyebrow">Moderation decision</p>
          <h2>{result.category}</h2>
        </div>

        <span
          className={`category-badge ${getCategoryClass(
            result.category
          )}`}
        >
          {result.action}
        </span>
      </div>

      <div className="decision-grid">
        <article className="metric-card">
          <span>Severity</span>
          <strong>{result.severity}</strong>
        </article>

        <article className="metric-card">
          <span>Confidence</span>
          <strong>{confidencePercent}%</strong>
        </article>

        <article className="metric-card">
          <span>Human review</span>
          <strong>
            {result.human_review_required
              ? "Required"
              : "Not required"}
          </strong>
        </article>

        <article className="metric-card">
          <span>Content type</span>
          <strong>
            {formatLabel(result.content_type)}
          </strong>
        </article>
      </div>

      <div className="confidence-block">
        <div className="confidence-label">
          <span>Decision confidence</span>
          <span>{confidencePercent}%</span>
        </div>

        <div className="confidence-track">
          <div
            className="confidence-fill"
            style={{
              width: `${confidencePercent}%`,
            }}
          />
        </div>
      </div>

      <article
        className={
          result.human_review_required
            ? "review-banner review-required"
            : "review-banner review-clear"
        }
      >
        <strong>
          {result.human_review_required
            ? "Human review required"
            : "Automated decision available"}
        </strong>
        <p>{result.reason}</p>
      </article>

      {!!result.decision_sources?.length && (
        <article className="result-section">
          <h3>Decision sources</h3>

          <div className="chip-list">
            {result.decision_sources.map(
              (source) => (
                <span
                  className="chip"
                  key={source}
                >
                  {formatLabel(source)}
                </span>
              )
            )}
          </div>
        </article>
      )}

      {!!result.matched_signals?.length && (
        <article className="result-section">
          <h3>Matched signals</h3>

          <div className="chip-list">
            {result.matched_signals.map(
              (signal) => (
                <span
                  className="chip signal-chip"
                  key={signal}
                >
                  {signal}
                </span>
              )
            )}
          </div>
        </article>
      )}

      {result.rag_used && (
        <article className="result-section">
          <div className="section-heading">
            <h3>RAG consensus</h3>
            <span className="status-dot">
              Connected
            </span>
          </div>

          <div className="rag-summary">
            <div>
              <span>Suggested category</span>
              <strong>
                {consensus.category ||
                  "No consensus"}
              </strong>
            </div>

            <div>
              <span>Agreement</span>
              <strong>
                {Math.round(
                  (consensus.agreement || 0) *
                    100
                )}
                %
              </strong>
            </div>

            <div>
              <span>Top similarity</span>
              <strong>
                {Math.round(
                  (consensus.top_similarity ||
                    0) * 100
                )}
                %
              </strong>
            </div>
          </div>
        </article>
      )}

      {!!result.analyzed_text_preview && (
        <details className="result-details">
          <summary>Analyzed content</summary>
          <pre>
            {result.analyzed_text_preview}
          </pre>
        </details>
      )}

      {!!evidence.length && (
        <details className="result-details">
          <summary>
            Retrieved evidence ({evidence.length})
          </summary>

          <div className="evidence-list">
            {evidence.map((item) => (
              <article
                className="evidence-card"
                key={item.rag_id}
              >
                <div className="evidence-heading">
                  <strong>
                    #{item.rank} {item.category}
                  </strong>
                  <span>
                    {Math.round(
                      item.similarity * 100
                    )}
                    % similar
                  </span>
                </div>

                <p>{item.reason}</p>

                <dl>
                  <div>
                    <dt>Source</dt>
                    <dd>{item.source_file}</dd>
                  </div>
                  <div>
                    <dt>Context</dt>
                    <dd>
                      {item.source_context ||
                        "Not specified"}
                    </dd>
                  </div>
                  <div>
                    <dt>Action</dt>
                    <dd>
                      {item.action ||
                        "Not specified"}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </details>
      )}

      {!!result.warnings?.length && (
        <details className="result-details warning-details">
          <summary>
            Processing warnings (
            {result.warnings.length})
          </summary>

          <ul>
            {result.warnings.map(
              (warning, index) => (
                <li key={`${warning}-${index}`}>
                  {warning}
                </li>
              )
            )}
          </ul>
        </details>
      )}

      {result.extraction_metadata &&
        Object.keys(
          result.extraction_metadata
        ).length > 0 && (
          <details className="result-details">
            <summary>
              Technical extraction details
            </summary>
            <pre>
              {JSON.stringify(
                result.extraction_metadata,
                null,
                2
              )}
            </pre>
          </details>
        )}
    </section>
  );
}


function App() {
  const [mode, setMode] = useState("text");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [sourceContext, setSourceContext] =
    useState("user");

  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [backendStatus, setBackendStatus] =
    useState("checking");

  const previewUrl = useMemo(() => {
    if (!file) return "";

    if (
      !file.type.startsWith("image/") &&
      !file.type.startsWith("video/")
    ) {
      return "";
    }

    return URL.createObjectURL(file);
  }, [file]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    async function checkBackend() {
      try {
        const response = await fetch(
          `${API_BASE_URL}/health`
        );

        if (!response.ok) {
          throw new Error();
        }

        setBackendStatus("connected");
      } catch {
        setBackendStatus("offline");
      }
    }

    checkBackend();
  }, []);

  function selectMode(nextMode) {
    setMode(nextMode);
    setError("");
    setResult(null);
  }

  function handleFile(event) {
    const selectedFile =
      event.target.files?.[0] || null;

    setFile(selectedFile);
    setError("");
    setResult(null);
  }

  async function readError(response) {
    try {
      const data = await response.json();

      if (typeof data.detail === "string") {
        return data.detail;
      }

      return JSON.stringify(
        data.detail || data
      );
    } catch {
      return `Request failed with status ${response.status}.`;
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setResult(null);

    if (mode === "text" && !text.trim()) {
      setError(
        "Enter some text before starting analysis."
      );
      return;
    }

    if (mode === "file" && !file) {
      setError(
        "Choose a document, image, or video first."
      );
      return;
    }

    setLoading(true);

    try {
      let response;

      if (mode === "text") {
        response = await fetch(
          `${API_BASE_URL}/moderation/text`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              text: text.trim(),
              source_context:
                sourceContext,
            }),
          }
        );
      } else {
        const formData = new FormData();

        formData.append("file", file);
        formData.append(
          "source_context",
          sourceContext
        );

        response = await fetch(
          `${API_BASE_URL}/moderation/file`,
          {
            method: "POST",
            body: formData,
          }
        );
      }

      if (!response.ok) {
        throw new Error(
          await readError(response)
        );
      }

      const data = await response.json();
      setResult(data);
    } catch (requestError) {
      setError(
        requestError.message ||
          "The moderation request failed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brand-mark">TS</span>
          <span>
            <strong>TrustScope</strong>
            <small>
              Multimodal safety review
            </small>
          </span>
        </a>

        <div
          className={`backend-status ${backendStatus}`}
        >
          <span />
          {backendStatus === "connected"
            ? "Backend connected"
            : backendStatus === "offline"
              ? "Backend offline"
              : "Checking backend"}
        </div>
      </header>

      <main>
        <section className="hero">
          <p className="eyebrow">
            Multimodal Trust & Safety
          </p>
          <h1>
            Review content with context,
            evidence, and human oversight.
          </h1>
          <p>
            Analyze text, documents, images,
            and videos using OCR, speech
            transcription, visual descriptions,
            policy retrieval, and decision fusion.
          </p>
        </section>

        <div className="workspace">
          <section className="input-panel">
            <div className="mode-tabs">
              <button
                className={
                  mode === "text"
                    ? "active"
                    : ""
                }
                type="button"
                onClick={() =>
                  selectMode("text")
                }
              >
                Analyze text
              </button>

              <button
                className={
                  mode === "file"
                    ? "active"
                    : ""
                }
                type="button"
                onClick={() =>
                  selectMode("file")
                }
              >
                Upload a file
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <label
                className="field-label"
                htmlFor="source-context"
              >
                Source context
              </label>

              <select
                id="source-context"
                value={sourceContext}
                onChange={(event) =>
                  setSourceContext(
                    event.target.value
                  )
                }
              >
                {SOURCE_CONTEXTS.map(
                  (context) => (
                    <option
                      key={context.value}
                      value={context.value}
                    >
                      {context.label}
                    </option>
                  )
                )}
              </select>

              {mode === "text" ? (
                <>
                  <label
                    className="field-label"
                    htmlFor="content-text"
                  >
                    Content to analyze
                  </label>

                  <textarea
                    id="content-text"
                    value={text}
                    onChange={(event) =>
                      setText(
                        event.target.value
                      )
                    }
                    placeholder="Paste a message, post, comment, article, or other text..."
                    rows={12}
                  />

                  <div className="field-footer">
                    <span>
                      {text.length.toLocaleString()}
                      {" / "}100,000 characters
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <label
                    className="field-label"
                    htmlFor="content-file"
                  >
                    Document, image, or video
                  </label>

                  <label
                    className="upload-zone"
                    htmlFor="content-file"
                  >
                    <input
                      id="content-file"
                      type="file"
                      accept={ACCEPTED_FILES}
                      onChange={handleFile}
                    />

                    <span className="upload-symbol">
                      ↑
                    </span>

                    {file ? (
                      <>
                        <strong>{file.name}</strong>
                        <span>
                          {(
                            file.size /
                            1024 /
                            1024
                          ).toFixed(2)}
                          {" MB"}
                        </span>
                      </>
                    ) : (
                      <>
                        <strong>
                          Choose a file
                        </strong>
                        <span>
                          TXT, PDF, DOCX, JPG,
                          PNG, WEBP, MP4, MOV,
                          AVI, MKV or WEBM
                        </span>
                      </>
                    )}
                  </label>

                  {previewUrl &&
                    file?.type.startsWith(
                      "image/"
                    ) && (
                      <img
                        className="media-preview"
                        src={previewUrl}
                        alt="Selected upload preview"
                      />
                    )}

                  {previewUrl &&
                    file?.type.startsWith(
                      "video/"
                    ) && (
                      <video
                        className="media-preview"
                        src={previewUrl}
                        controls
                      >
                        <track
                          kind="captions"
                          label="No captions available"
                        />
                      </video>
                    )}
                </>
              )}

              {error && (
                <div
                  className="error-message"
                  role="alert"
                >
                  {error}
                </div>
              )}

              <button
                className="analyze-button"
                type="submit"
                disabled={loading}
              >
                {loading
                  ? mode === "file"
                    ? "Processing media..."
                    : "Analyzing..."
                  : "Run safety analysis"}
              </button>

              {loading && (
                <p className="processing-note">
                  Video, vision, and transcription
                  requests can take several minutes.
                  Keep this page open.
                </p>
              )}
            </form>
          </section>

          <ResultPanel result={result} />
        </div>
      </main>

      <footer>
        <p>
          Automated decisions can be incomplete.
          High-risk and uncertain cases require
          qualified human review.
        </p>
      </footer>
    </div>
  );
}


export default App;