import {
  useEffect,
  useMemo,
  useState,
} from "react";

import "./App.css";


const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8010";

const ACCEPTED_FILES =
  ".txt,.pdf,.docx,.jpg,.jpeg,.png,.webp,.mp4,.mov,.avi,.mkv,.webm";


function formatLabel(value) {
  if (!value) {
    return "Not available";
  }

  return value
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      (letter) =>
        letter.toUpperCase()
    );
}


function formatFileSize(bytes) {
  if (
    bytes === null ||
    bytes === undefined
  ) {
    return "Not available";
  }

  if (bytes < 1024) {
    return `${bytes} bytes`;
  }

  if (bytes < 1024 * 1024) {
    return `${(
      bytes / 1024
    ).toFixed(2)} KB`;
  }

  return `${(
    bytes /
    1024 /
    1024
  ).toFixed(2)} MB`;
}


function formatDuration(seconds) {
  if (
    seconds === null ||
    seconds === undefined
  ) {
    return "Not applicable";
  }

  const totalSeconds = Math.round(
    seconds
  );

  const minutes = Math.floor(
    totalSeconds / 60
  );

  const remainingSeconds =
    totalSeconds % 60;

  if (minutes === 0) {
    return `${remainingSeconds} seconds`;
  }

  return (
    `${minutes} min ` +
    `${remainingSeconds} sec`
  );
}


function getDecisionClass(category) {
  if (category === "Normal/Ignore") {
    return "decision-safe";
  }

  if (
    category === "Child Abuse" ||
    category === "Violence"
  ) {
    return "decision-critical";
  }

  if (
    category === "Scam" ||
    category === "Hate Speech" ||
    category === "Nudity"
  ) {
    return "decision-high";
  }

  return "decision-medium";
}


function DeepAnalysisReport({
  deepResult,
}) {
  if (!deepResult) {
    return null;
  }

  const scenes =
    deepResult
      .scene_by_scene_summary || [];

  const factChecks =
    deepResult
      .fact_check_suggestions || [];

  const size =
    deepResult.content_size || {};

  return (
    <section className="deep-report">
      <div className="deep-report-heading">
        <div>
          <p className="eyebrow">
            Extended review
          </p>

          <h3>
            Deep analysis report
          </h3>
        </div>

        <span className="confidence-badge">
          {Math.round(
            (
              deepResult
                .confidence_score ||
              0
            ) * 100
          )}
          % confidence
        </span>
      </div>

      <article className="deep-section">
        <h4>Summary</h4>

        <p>
          {deepResult.summary ||
            "No summary was generated."}
        </p>
      </article>

      {deepResult.content_type ===
        "video" && (
        <article className="deep-section">
          <h4>
            Scene-by-scene summary
          </h4>

          {scenes.length > 0 ? (
            <div className="scene-list">
              {scenes.map(
                (scene, index) => (
                  <div
                    className="scene-item"
                    key={
                      `${scene.timestamp_seconds}-${index}`
                    }
                  >
                    <span>
                      {formatDuration(
                        scene
                          .timestamp_seconds
                      )}
                    </span>

                    <p>
                      {scene.summary}
                    </p>
                  </div>
                )
              )}
            </div>
          ) : (
            <p className="empty-detail">
              No reliable sampled-scene
              summaries were generated.
            </p>
          )}
        </article>
      )}

      {(deepResult.content_type ===
        "image" ||
        deepResult.content_type ===
          "video") && (
        <article className="deep-section">
          <h4>Exact OCR text</h4>

          {deepResult
            .exact_ocr_text ? (
            <pre className="ocr-output">
              {
                deepResult
                  .exact_ocr_text
              }
            </pre>
          ) : (
            <p className="empty-detail">
              No readable text was
              detected.
            </p>
          )}
        </article>
      )}

      <div className="deep-metric-grid">
        <article className="deep-metric-card">
          <span>File/text size</span>

          <strong>
            {formatFileSize(
              size.size_bytes
            )}
          </strong>

          <small>
            {(
              size.character_count ||
              0
            ).toLocaleString()}
            {" characters · "}
            {(
              size.word_count || 0
            ).toLocaleString()}
            {" words"}
          </small>
        </article>

        <article className="deep-metric-card">
          <span>
            Media duration
          </span>

          <strong>
            {formatDuration(
              deepResult
                .media_duration_seconds
            )}
          </strong>

          <small>
            Available for video
            content
          </small>
        </article>

        <article className="deep-metric-card">
          <span>
            Confidence score
          </span>

          <strong>
            {Math.round(
              (
                deepResult
                  .confidence_score ||
                0
              ) * 100
            )}
            %
          </strong>

          <small>
            Based on available
            extracted evidence
          </small>
        </article>
      </div>

      <article className="deep-section">
        <h4>
          Fact-check suggestions
        </h4>

        {factChecks.length > 0 ? (
          <div className="fact-check-list">
            {factChecks.map(
              (item, index) => (
                <div
                  className="fact-check-item"
                  key={index}
                >
                  <span
                    className={
                      `priority-badge ` +
                      `priority-${(
                        item.priority ||
                        "medium"
                      ).toLowerCase()}`
                    }
                  >
                    {item.priority ||
                      "Medium"}
                  </span>

                  <strong>
                    {item.claim}
                  </strong>

                  <p>
                    {item.suggestion}
                  </p>
                </div>
              )
            )}
          </div>
        ) : (
          <p className="empty-detail">
            No specific factual claims
            were flagged for
            verification.
          </p>
        )}
      </article>

      <article className="next-step-card">
        <span>Suggested next step</span>

        <p>
          {
            deepResult
              .suggested_next_step
          }
        </p>
      </article>
    </section>
  );
}


function ResultPanel({
  result,
  deepResult,
  deepLoading,
  deepError,
  onRunDeepAnalysis,
  onStartNewAnalysis,
}) {
  if (!result) {
    return (
      <section className="empty-result">
        <div className="empty-symbol">
          TS
        </div>

        <h2>No analysis yet</h2>

        <p>
          Submit text or upload a file
          to receive a moderation
          decision.
        </p>
      </section>
    );
  }

  return (
    <section className="result-panel">
      <div className="result-heading">
        <div>
          <p className="eyebrow">
            Analysis complete
          </p>

          <h2>Moderation result</h2>
        </div>
      </div>

      <div className="primary-decision-grid">
        <article
          className={
            `primary-decision-card ` +
            getDecisionClass(
              result.category
            )
          }
        >
          <span>
            Moderation Decision
          </span>

          <strong>
            {result.category}
          </strong>
        </article>

        <article className="primary-decision-card">
          <span>
            Action needs to be taken
          </span>

          <strong>
            {result.action}
          </strong>
        </article>

        <article
          className={
            result
              .human_review_required
              ? "primary-decision-card review-needed-card"
              : "primary-decision-card review-clear-card"
          }
        >
          <span>Human review</span>

          <strong>
            {result
              .human_review_required
              ? "Needed"
              : "Not needed"}
          </strong>
        </article>

        <article className="primary-decision-card">
          <span>Content type</span>

          <strong>
            {formatLabel(
              result.content_type
            )}
          </strong>
        </article>
      </div>

      {deepError && (
        <div
          className="error-message"
          role="alert"
        >
          {deepError}
        </div>
      )}

      <div className="result-action-row">
        <button
          className="deep-analysis-button"
          type="button"
          disabled={deepLoading}
          onClick={
            onRunDeepAnalysis
          }
        >
          {deepLoading
            ? "Running deep analysis..."
            : deepResult
              ? "Run deep analysis again"
              : "Run deep analysis"}
        </button>

        <button
          className="new-analysis-button"
          type="button"
          disabled={deepLoading}
          onClick={
            onStartNewAnalysis
          }
        >
          Start New Analysis
        </button>
      </div>

      {deepLoading && (
        <p className="processing-note">
          Deep analysis may take
          several minutes for images,
          documents, and videos. Keep
          this page open.
        </p>
      )}

      <DeepAnalysisReport
        deepResult={deepResult}
      />
    </section>
  );
}


function FilePreview({
  file,
  previewUrl,
  onChooseAnother,
}) {
  if (!file) {
    return null;
  }

  const extension =
    file.name
      .split(".")
      .pop()
      ?.toUpperCase() || "FILE";

  return (
    <div className="selected-file">
      {file.type.startsWith(
        "image/"
      ) && previewUrl ? (
        <img
          className="selected-media-preview"
          src={previewUrl}
          alt="Selected file preview"
        />
      ) : file.type.startsWith(
          "video/"
        ) && previewUrl ? (
        <video
          className="selected-media-preview"
          src={previewUrl}
          controls
        />
      ) : (
        <div className="document-preview">
          <span>{extension}</span>

          <small>
            Document selected
          </small>
        </div>
      )}

      <p className="selected-file-name">
        {file.name}
      </p>

      <p className="selected-file-size">
        {formatFileSize(file.size)}
      </p>

      <button
        className="change-file-button"
        type="button"
        onClick={onChooseAnother}
      >
        Choose another file
      </button>
    </div>
  );
}


function App() {
  const [mode, setMode] =
    useState("text");

  const [text, setText] =
    useState("");

  const [file, setFile] =
    useState(null);

  const [
    fileInputVersion,
    setFileInputVersion,
  ] = useState(0);

  const [result, setResult] =
    useState(null);

  const [
    deepResult,
    setDeepResult,
  ] = useState(null);

  const [error, setError] =
    useState("");

  const [
    deepError,
    setDeepError,
  ] = useState("");

  const [loading, setLoading] =
    useState(false);

  const [
    deepLoading,
    setDeepLoading,
  ] = useState(false);

  const [
    backendStatus,
    setBackendStatus,
  ] = useState("checking");

  const previewUrl = useMemo(() => {
    if (!file) {
      return "";
    }

    if (
      !file.type.startsWith(
        "image/"
      ) &&
      !file.type.startsWith(
        "video/"
      )
    ) {
      return "";
    }

    return URL.createObjectURL(
      file
    );
  }, [file]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(
          previewUrl
        );
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

        setBackendStatus(
          "connected"
        );
      } catch {
        setBackendStatus(
          "offline"
        );
      }
    }

    checkBackend();
  }, []);

  function clearResults() {
    setResult(null);
    setDeepResult(null);
    setError("");
    setDeepError("");
  }

  function clearCase() {
    setText("");
    setFile(null);
    clearResults();
    setLoading(false);
    setDeepLoading(false);

    setFileInputVersion(
      (current) => current + 1
    );
  }

  function selectMode(nextMode) {
    clearCase();
    setMode(nextMode);
  }

  function handleTextChange(event) {
    setText(event.target.value);
    clearResults();
  }

  function handleFile(event) {
    const selectedFile =
      event.target.files?.[0] ||
      null;

    setFile(selectedFile);
    clearResults();
  }

  function chooseAnotherFile() {
    setFile(null);
    clearResults();

    setFileInputVersion(
      (current) => current + 1
    );

    window.setTimeout(() => {
      document
        .getElementById(
          "content-file"
        )
        ?.click();
    }, 0);
  }

  async function readError(response) {
    try {
      const data =
        await response.json();

      if (
        typeof data.detail ===
        "string"
      ) {
        return data.detail;
      }

      return JSON.stringify(
        data.detail || data
      );
    } catch {
      return (
        "Request failed with status " +
        `${response.status}.`
      );
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");
    setDeepError("");
    setResult(null);
    setDeepResult(null);

    if (
      mode === "text" &&
      !text.trim()
    ) {
      setError(
        "Enter some text before starting analysis."
      );
      return;
    }

    if (
      mode === "file" &&
      !file
    ) {
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
                "unknown",
            }),
          }
        );
      } else {
        const formData =
          new FormData();

        formData.append(
          "file",
          file
        );

        formData.append(
          "source_context",
          "unknown"
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

      const data =
        await response.json();

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

  async function runDeepAnalysis() {
    if (!result) {
      return;
    }

    setDeepError("");
    setDeepResult(null);
    setDeepLoading(true);

    try {
      let response;

      if (mode === "text") {
        response = await fetch(
          `${API_BASE_URL}/deep-analysis/text`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              text: text.trim(),
            }),
          }
        );
      } else {
        const formData =
          new FormData();

        formData.append(
          "file",
          file
        );

        response = await fetch(
          `${API_BASE_URL}/deep-analysis/file`,
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

      const data =
        await response.json();

      setDeepResult(data);
    } catch (requestError) {
      setDeepError(
        requestError.message ||
          "The deep-analysis request failed."
      );
    } finally {
      setDeepLoading(false);
    }
  }

  const hasCaseData =
    Boolean(text) ||
    Boolean(file) ||
    Boolean(result) ||
    Boolean(error);

  const processing =
    loading || deepLoading;

  return (
    <div className="app-shell">
      <header className="topbar">
        <a
          className="brand"
          href="/"
        >
          <span className="brand-mark">
            TS
          </span>

          <span>
            <strong>
              TrustScope
            </strong>

            <small>
              Multimodal safety review
            </small>
          </span>
        </a>

        <div
          className={
            `backend-status ` +
            backendStatus
          }
        >
          <span />

          {backendStatus ===
          "connected"
            ? "Backend connected"
            : backendStatus ===
                "offline"
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
            Review content with clarity
            and human oversight.
          </h1>

          <p>
            Analyze text, documents,
            images, and videos without
            requiring users to identify
            the source.
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
                disabled={processing}
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
                disabled={processing}
                onClick={() =>
                  selectMode("file")
                }
              >
                Upload a file
              </button>
            </div>

            <form onSubmit={handleSubmit}>
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
                    disabled={processing}
                    onChange={
                      handleTextChange
                    }
                    placeholder="Paste a message, post, comment, article, or other text..."
                    rows={12}
                  />

                  <div className="field-footer">
                    <span>
                      {text.length.toLocaleString()}
                      {" / "}
                      100,000 characters
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <label
                    className="field-label"
                    htmlFor="content-file"
                  >
                    Document, image,
                    or video
                  </label>

                  <input
                    key={
                      fileInputVersion
                    }
                    className="hidden-file-input"
                    id="content-file"
                    type="file"
                    accept={
                      ACCEPTED_FILES
                    }
                    disabled={processing}
                    onChange={
                      handleFile
                    }
                  />

                  {!file ? (
                    <label
                      className="upload-zone"
                      htmlFor="content-file"
                    >
                      <span className="upload-symbol">
                        ↑
                      </span>

                      <strong>
                        Choose a file
                      </strong>

                      <span>
                        TXT, PDF, DOCX,
                        JPG, PNG, WEBP,
                        MP4, MOV, AVI,
                        MKV or WEBM
                      </span>
                    </label>
                  ) : (
                    <FilePreview
                      file={file}
                      previewUrl={
                        previewUrl
                      }
                      onChooseAnother={
                        chooseAnotherFile
                      }
                    />
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

              <div className="button-row">
                <button
                  className="analyze-button"
                  type="submit"
                  disabled={processing}
                >
                  {loading
                    ? mode === "file"
                      ? "Processing media..."
                      : "Analyzing..."
                    : "Run safety analysis"}
                </button>

                <button
                  className="reset-button"
                  type="button"
                  disabled={
                    processing ||
                    !hasCaseData
                  }
                  onClick={clearCase}
                >
                  Clear
                </button>
              </div>

              {loading && (
                <p className="processing-note">
                  Video, vision, and
                  transcription requests
                  can take several minutes.
                  Keep this page open.
                </p>
              )}
            </form>
          </section>

          <ResultPanel
            result={result}
            deepResult={deepResult}
            deepLoading={deepLoading}
            deepError={deepError}
            onRunDeepAnalysis={
              runDeepAnalysis
            }
            onStartNewAnalysis={
              clearCase
            }
          />
        </div>
      </main>

      <footer>
        <p>
          Automated decisions can be
          incomplete. High-risk and
          uncertain cases require
          qualified human review.
        </p>
      </footer>
    </div>
  );
}


export default App;