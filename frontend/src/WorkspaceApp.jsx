import {
  useEffect,
  useState,
} from "react";

import App from "./App";
import ReviewQueue from "./ReviewQueue";
import {
  API_BASE_URL,
} from "./apiConfig";


function getViewFromHash() {
  return (
    window.location.hash ===
    "#review"
      ? "review"
      : "analyze"
  );
}


function WorkspaceApp() {
  const [view, setView] =
    useState(
      getViewFromHash
    );


  useEffect(() => {
    function handleHashChange() {
      setView(
        getViewFromHash()
      );
    }

    window.addEventListener(
      "hashchange",
      handleHashChange
    );

    return () => {
      window.removeEventListener(
        "hashchange",
        handleHashChange
      );
    };
  }, []);


  function openView(
    nextView
  ) {
    if (nextView === "review") {
      window.location.hash =
        "review";

      setView("review");
    } else {
      window.history.pushState(
        null,
        "",
        window.location.pathname
      );

      setView("analyze");
    }

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }


  return (
    <>
      <nav
        className="workspace-navigation"
        aria-label="Application views"
      >
        <button
          className={
            view === "analyze"
              ? "active"
              : ""
          }
          type="button"
          onClick={() =>
            openView("analyze")
          }
        >
          Analyze
        </button>

        <button
          className={
            view === "review"
              ? "active"
              : ""
          }
          type="button"
          onClick={() =>
            openView("review")
          }
        >
          Review Queue
        </button>
      </nav>

      {view === "analyze" ? (
        <App />
      ) : (
        <div className="app-shell">
          <header className="topbar">
            <button
              className="brand"
              type="button"
              style={{
                background:
                  "transparent",
                border: 0,
                padding: 0,
                textAlign: "left",
              }}
              onClick={() =>
                openView("analyze")
              }
            >
              <span className="brand-mark">
                TS
              </span>

              <span>
                <strong>
                  TrustScope
                </strong>

                <small>
                  Multimodal safety
                  review
                </small>
              </span>
            </button>

            <div
              style={{
                color: "#65746d",
                fontSize: "12px",
                fontWeight: 800,
              }}
            >
              Human review workspace
            </div>
          </header>

          <ReviewQueue
            apiBaseUrl={
              API_BASE_URL
            }
          />

          <footer>
            <p>
              Human-review records are
              stored locally for this
              prototype. Authentication,
              access control, encryption,
              and retention policies are
              required before production
              use.
            </p>
          </footer>
        </div>
      )}
    </>
  );
}


export default WorkspaceApp;
