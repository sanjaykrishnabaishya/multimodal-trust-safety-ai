import {
  useCallback,
  useEffect,
  useState,
} from "react";


const REVIEW_STATUSES = [
  "pending",
  "approved",
  "overturned",
  "escalated",
  "closed",
];


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


function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return value;
  }

  return date.toLocaleString();
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


function StatusBadge({
  status,
}) {
  return (
    <span
      className={
        `review-status-badge ` +
        `review-status-${status}`
      }
    >
      {formatLabel(status)}
    </span>
  );
}


function CaseListItem({
  reviewCase,
  selected,
  onSelect,
}) {
  return (
    <button
      className={
        selected
          ? "review-case-item selected"
          : "review-case-item"
      }
      type="button"
      onClick={() =>
        onSelect(reviewCase)
      }
    >
      <div className="review-case-item-top">
        <strong>
          {reviewCase.category}
        </strong>

        <StatusBadge
          status={
            reviewCase.review_status
          }
        />
      </div>

      <p>
        {reviewCase.content_preview}
      </p>

      <div className="review-case-item-meta">
        <span>
          {formatLabel(
            reviewCase.content_type
          )}
        </span>

        <span>
          {formatDate(
            reviewCase.created_at
          )}
        </span>
      </div>
    </button>
  );
}


function AuditTimeline({
  events,
  loading,
}) {
  if (loading) {
    return (
      <p className="review-muted">
        Loading audit history...
      </p>
    );
  }

  if (events.length === 0) {
    return (
      <p className="review-muted">
        No audit events are available.
      </p>
    );
  }

  return (
    <div className="audit-timeline">
      {events.map((event) => (
        <article
          className="audit-event"
          key={event.event_id}
        >
          <span className="audit-marker" />

          <div>
            <div className="audit-event-heading">
              <strong>
                {formatLabel(
                  event.event_type
                )}
              </strong>

              <time>
                {formatDate(
                  event.created_at
                )}
              </time>
            </div>

            {event.event_data
              ?.reviewer_name && (
              <p>
                Reviewer:{" "}
                {
                  event.event_data
                    .reviewer_name
                }
              </p>
            )}

            {event.event_data
              ?.new_status && (
              <p>
                Status changed to{" "}
                <strong>
                  {formatLabel(
                    event.event_data
                      .new_status
                  )}
                </strong>
              </p>
            )}

            {event.event_data
              ?.reviewer_notes && (
              <p>
                {
                  event.event_data
                    .reviewer_notes
                }
              </p>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}


function ReviewQueue({
  apiBaseUrl,
}) {
  const [statusFilter, setStatusFilter] =
    useState("pending");

  const [cases, setCases] =
    useState([]);

  const [
    selectedCase,
    setSelectedCase,
  ] = useState(null);

  const [auditEvents, setAuditEvents] =
    useState([]);

  const [loading, setLoading] =
    useState(true);

  const [
    auditLoading,
    setAuditLoading,
  ] = useState(false);

  const [
    submitting,
    setSubmitting,
  ] = useState(false);

  const [error, setError] =
    useState("");

  const [success, setSuccess] =
    useState("");

  const [
    reviewerName,
    setReviewerName,
  ] = useState("");

  const [
    reviewerNotes,
    setReviewerNotes,
  ] = useState("");

  const [
    reviewStatus,
    setReviewStatus,
  ] = useState("approved");

  const [
    finalCategory,
    setFinalCategory,
  ] = useState("");

  const [
    finalAction,
    setFinalAction,
  ] = useState("");


  const loadCases = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const query = new URLSearchParams({
        limit: "100",
        offset: "0",
      });

      if (
        statusFilter !== "all"
      ) {
        query.set(
          "review_status",
          statusFilter
        );
      }

      const response = await fetch(
        `${apiBaseUrl}/review/cases?${query}`
      );

      if (!response.ok) {
        throw new Error(
          await readError(response)
        );
      }

      const data =
        await response.json();

      setCases(data);

      setSelectedCase(
        (currentCase) => {
          if (!data.length) {
            return null;
          }

          const matchingCase =
            data.find(
              (item) =>
                item.case_id ===
                currentCase?.case_id
            );

          return (
            matchingCase ||
            data[0]
          );
        }
      );
    } catch (requestError) {
      setCases([]);
      setSelectedCase(null);

      setError(
        requestError.message ||
          "The review queue could not be loaded."
      );
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, statusFilter]);


  const loadAudit = useCallback(async (
    caseId
  ) => {
    if (!caseId) {
      setAuditEvents([]);
      return;
    }

    setAuditLoading(true);

    try {
      const response = await fetch(
        `${apiBaseUrl}/review/cases/${caseId}/audit`
      );

      if (!response.ok) {
        throw new Error(
          await readError(response)
        );
      }

      const data =
        await response.json();

      setAuditEvents(data);
    } catch (requestError) {
      setAuditEvents([]);

      setError(
        requestError.message ||
          "The audit history could not be loaded."
      );
    } finally {
      setAuditLoading(false);
    }
  }, [apiBaseUrl]);


  useEffect(() => {
    loadCases();
  }, [loadCases]);


  useEffect(() => {
    if (!selectedCase) {
      setAuditEvents([]);
      return;
    }

    setSuccess("");
    setError("");

    setReviewerName(
      selectedCase.reviewer_name ||
        ""
    );

    setReviewerNotes(
      selectedCase.reviewer_notes ||
        ""
    );

    setReviewStatus(
      selectedCase.review_status ===
        "pending"
        ? "approved"
        : selectedCase.review_status
    );

    setFinalCategory(
      selectedCase.final_category ||
        selectedCase.category ||
        ""
    );

    setFinalAction(
      selectedCase.final_action ||
        selectedCase.action ||
        ""
    );

    loadAudit(
      selectedCase.case_id
    );
  }, [loadAudit, selectedCase]);


  async function submitReview(
    event
  ) {
    event.preventDefault();

    if (!selectedCase) {
      return;
    }

    if (!reviewerName.trim()) {
      setError(
        "Enter the reviewer name."
      );
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `${apiBaseUrl}/review/cases/${selectedCase.case_id}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            review_status:
              reviewStatus,
            reviewer_name:
              reviewerName.trim(),
            reviewer_notes:
              reviewerNotes.trim(),
            final_category:
              finalCategory.trim() ||
              null,
            final_action:
              finalAction.trim() ||
              null,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          await readError(response)
        );
      }

      const updatedCase =
        await response.json();

      setSelectedCase(
        updatedCase
      );

      setCases(
        (currentCases) =>
          currentCases.map(
            (item) =>
              item.case_id ===
              updatedCase.case_id
                ? updatedCase
                : item
          )
      );

      setSuccess(
        "The human-review decision was saved."
      );

      await loadAudit(
        updatedCase.case_id
      );
    } catch (requestError) {
      setError(
        requestError.message ||
          "The human-review decision could not be saved."
      );
    } finally {
      setSubmitting(false);
    }
  }


  return (
    <main className="review-page">
      <section className="review-hero">
        <p className="eyebrow">
          Human oversight
        </p>

        <h1>Review Queue</h1>

        <p>
          Inspect automated decisions,
          record a human judgment, and
          preserve a complete audit
          history.
        </p>
      </section>

      <div className="review-filter-row">
        {[
          "pending",
          "approved",
          "overturned",
          "escalated",
          "closed",
          "all",
        ].map((status) => (
          <button
            className={
              statusFilter === status
                ? "review-filter active"
                : "review-filter"
            }
            type="button"
            key={status}
            onClick={() =>
              setStatusFilter(status)
            }
          >
            {formatLabel(status)}
          </button>
        ))}

        <button
          className="review-refresh-button"
          type="button"
          disabled={loading}
          onClick={loadCases}
        >
          {loading
            ? "Refreshing..."
            : "Refresh"}
        </button>
      </div>

      {error && (
        <div
          className="error-message"
          role="alert"
        >
          {error}
        </div>
      )}

      {success && (
        <div
          className="review-success"
          role="status"
        >
          {success}
        </div>
      )}

      <div className="review-workspace">
        <aside className="review-list-panel">
          <div className="review-list-heading">
            <h2>Cases</h2>

            <span>
              {cases.length}
            </span>
          </div>

          {loading ? (
            <p className="review-list-message">
              Loading cases...
            </p>
          ) : cases.length === 0 ? (
            <p className="review-list-message">
              No cases were found for
              this status.
            </p>
          ) : (
            <div className="review-case-list">
              {cases.map(
                (reviewCase) => (
                  <CaseListItem
                    key={
                      reviewCase.case_id
                    }
                    reviewCase={
                      reviewCase
                    }
                    selected={
                      selectedCase
                        ?.case_id ===
                      reviewCase.case_id
                    }
                    onSelect={
                      setSelectedCase
                    }
                  />
                )
              )}
            </div>
          )}
        </aside>

        <section className="review-detail-panel">
          {!selectedCase ? (
            <div className="review-empty-detail">
              <div>HR</div>

              <h2>
                Select a review case
              </h2>

              <p>
                Choose a case from the
                queue to inspect its
                decision and audit
                history.
              </p>
            </div>
          ) : (
            <>
              <div className="review-detail-heading">
                <div>
                  <p className="eyebrow">
                    Case
                  </p>

                  <h2>
                    {
                      selectedCase
                        .category
                    }
                  </h2>

                  <small>
                    {
                      selectedCase
                        .case_id
                    }
                  </small>
                </div>

                <StatusBadge
                  status={
                    selectedCase
                      .review_status
                  }
                />
              </div>

              <div className="review-decision-grid">
                <article>
                  <span>
                    Automated decision
                  </span>

                  <strong>
                    {
                      selectedCase
                        .category
                    }
                  </strong>
                </article>

                <article>
                  <span>Action</span>

                  <strong>
                    {
                      selectedCase
                        .action
                    }
                  </strong>
                </article>

                <article>
                  <span>Confidence</span>

                  <strong>
                    {Math.round(
                      selectedCase
                        .confidence *
                        100
                    )}
                    %
                  </strong>
                </article>

                <article>
                  <span>Content type</span>

                  <strong>
                    {formatLabel(
                      selectedCase
                        .content_type
                    )}
                  </strong>
                </article>
              </div>

              <article className="review-content-preview">
                <h3>
                  Content preview
                </h3>

                <p>
                  {
                    selectedCase
                      .content_preview
                  }
                </p>

                {selectedCase
                  .file_name && (
                  <small>
                    File:{" "}
                    {
                      selectedCase
                        .file_name
                    }
                  </small>
                )}
              </article>

              <article className="review-reason">
                <h3>
                  Automated reasoning
                </h3>

                <p>
                  {
                    selectedCase
                      .reason
                  }
                </p>
              </article>

              <form
                className="review-form"
                onSubmit={submitReview}
              >
                <h3>
                  Human-review decision
                </h3>

                <div className="review-form-grid">
                  <label>
                    Reviewer name

                    <input
                      type="text"
                      value={
                        reviewerName
                      }
                      maxLength={100}
                      disabled={
                        submitting
                      }
                      onChange={(
                        event
                      ) =>
                        setReviewerName(
                          event.target
                            .value
                        )
                      }
                    />
                  </label>

                  <label>
                    Review status

                    <select
                      value={
                        reviewStatus
                      }
                      disabled={
                        submitting
                      }
                      onChange={(
                        event
                      ) =>
                        setReviewStatus(
                          event.target
                            .value
                        )
                      }
                    >
                      {REVIEW_STATUSES.map(
                        (status) => (
                          <option
                            value={
                              status
                            }
                            key={
                              status
                            }
                          >
                            {formatLabel(
                              status
                            )}
                          </option>
                        )
                      )}
                    </select>
                  </label>

                  <label>
                    Final category

                    <input
                      type="text"
                      value={
                        finalCategory
                      }
                      maxLength={100}
                      disabled={
                        submitting
                      }
                      onChange={(
                        event
                      ) =>
                        setFinalCategory(
                          event.target
                            .value
                        )
                      }
                    />
                  </label>

                  <label>
                    Final action

                    <input
                      type="text"
                      value={
                        finalAction
                      }
                      maxLength={200}
                      disabled={
                        submitting
                      }
                      onChange={(
                        event
                      ) =>
                        setFinalAction(
                          event.target
                            .value
                        )
                      }
                    />
                  </label>
                </div>

                <label>
                  Reviewer notes

                  <textarea
                    className="review-notes"
                    value={
                      reviewerNotes
                    }
                    maxLength={2000}
                    rows={5}
                    disabled={
                      submitting
                    }
                    onChange={(
                      event
                    ) =>
                      setReviewerNotes(
                        event.target
                          .value
                      )
                    }
                  />
                </label>

                <button
                  className="review-submit-button"
                  type="submit"
                  disabled={
                    submitting
                  }
                >
                  {submitting
                    ? "Saving review..."
                    : "Save human-review decision"}
                </button>
              </form>

              <section className="audit-section">
                <h3>Audit history</h3>

                <AuditTimeline
                  events={
                    auditEvents
                  }
                  loading={
                    auditLoading
                  }
                />
              </section>
            </>
          )}
        </section>
      </div>
    </main>
  );
}


export default ReviewQueue;
