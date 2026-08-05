import {
  useEffect,
  useState,
} from "react";

import App from "./App";
import ReviewQueue from "./ReviewQueue";


const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8010";


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


  const navigationStyle = {
    alignItems: "center",
    background: "#f3f7f4",
    border: "1px solid #dce4df",
    borderRadius: "12px",
    display: "flex",
    gap: "4px",
    left: "50%",
    padding: "4px",
    position: "fixed",
    top: "14px",
    transform: "translateX(-50%)",
    zIndex: 100,
  };


  function navigationButtonStyle(
    buttonView
  ) {
    const active =
      view === buttonView;

    return {
      background: active
        ? "#ffffff"
        : "transparent",
      border: "0",
      borderRadius: "8px",
      boxShadow: active
        ? "0 3px 12px rgba(25, 47, 38, 0.1)"
        : "none",
      color: active
        ? "#0e684b"
        : "#65746d",
      cursor: "pointer",
      fontSize: "12px",
      fontWeight: 800,
      minHeight: "38px",
      padding: "8px 15px",
      whiteSpace: "nowrap",
    };
  }


  return (
    <>
      <nav
        style={navigationStyle}
        aria-label="Application views"
      >
        <button
          style={
            navigationButtonStyle(
              "analyze"
            )
          }
          type="button"
          onClick={() =>
            openView("analyze")
          }
        >
          Analyze
        </button>

        <button
          style={
            navigationButtonStyle(
              "review"
            )
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