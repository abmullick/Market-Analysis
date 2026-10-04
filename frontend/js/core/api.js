const API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || "/api";

async function request(path, options = {}) {
    const url = `${API_BASE_URL}${path}`;
    const response = await fetch(url, {
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
        ...options,
    });

    if (!response.ok) {
        const text = await response.text();
        throw new Error(`API error ${response.status}: ${text}`);
    }

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

/*
 * Portfolio Builder busy overlay.
 * Scoped strictly to the portfolio-builder page so the shared API module
 * cannot change behaviour anywhere else in the application.
 * The existing portfolio analysis flow remains untouched; this only adds
 * the visual/input-blocking layer while #pb-analysis-loading is active.
 */
function installPortfolioBuilderBusyOverlay() {
    if (document.body?.dataset?.page !== "portfolio-builder") return;

    const style = document.createElement("style");
    style.id = "pb-analysis-busy-overlay-style";
    style.textContent = `
        #pb-analysis-busy-overlay {
            position: fixed;
            inset: 0;
            z-index: 1000000;
            display: none;
            align-items: center;
            justify-content: center;
            background: rgba(8, 22, 38, 0.48);
            backdrop-filter: blur(4px);
            -webkit-backdrop-filter: blur(4px);
            cursor: wait;
        }
        #pb-analysis-busy-overlay.is-visible { display: flex; }
        #pb-analysis-busy-overlay .pb-analysis-busy-card {
            min-width: 340px;
            max-width: calc(100vw - 40px);
            padding: 34px 42px;
            border: 1px solid rgba(255,255,255,.3);
            border-radius: 22px;
            background: linear-gradient(145deg, rgba(255,255,255,.98), rgba(241,248,255,.97));
            box-shadow: 0 24px 70px rgba(2,12,24,.30);
            text-align: center;
            color: #10263d;
        }
        #pb-analysis-busy-overlay .pb-analysis-busy-spinner {
            width: 68px;
            height: 68px;
            margin: 0 auto 20px;
            border: 7px solid #dbeafe;
            border-top-color: #2563eb;
            border-right-color: #0ea5e9;
            border-radius: 50%;
            animation: pbAnalysisBusySpin .8s linear infinite;
        }
        #pb-analysis-busy-overlay .pb-analysis-busy-title {
            font-size: 20px;
            font-weight: 800;
            letter-spacing: -.015em;
        }
        #pb-analysis-busy-overlay .pb-analysis-busy-message {
            margin-top: 8px;
            color: #64748b;
            font-size: 13px;
            line-height: 1.5;
        }
        @keyframes pbAnalysisBusySpin { to { transform: rotate(360deg); } }
        @media (max-width: 600px) {
            #pb-analysis-busy-overlay .pb-analysis-busy-card {
                min-width: 0;
                width: calc(100vw - 36px);
                padding: 28px 22px;
            }
            #pb-analysis-busy-overlay .pb-analysis-busy-spinner {
                width: 58px;
                height: 58px;
            }
        }
    `;
    document.head.appendChild(style);

    const overlay = document.createElement("div");
    overlay.id = "pb-analysis-busy-overlay";
    overlay.setAttribute("aria-live", "polite");
    overlay.setAttribute("aria-busy", "true");
    overlay.innerHTML = `
        <div class="pb-analysis-busy-card" role="status">
            <div class="pb-analysis-busy-spinner" aria-hidden="true"></div>
            <div class="pb-analysis-busy-title">Analyzing Portfolio</div>
            <div class="pb-analysis-busy-message">Fetching data and calculating your portfolio analysis. Please wait.</div>
        </div>
    `;
    document.body.appendChild(overlay);

    const continueBtn = document.getElementById("pb-continue-btn");
    const loading = document.getElementById("pb-analysis-loading");
    if (!continueBtn || !loading) return;

    const setBusy = (busy) => {
        overlay.classList.toggle("is-visible", !!busy);
        document.body.style.overflow = busy ? "hidden" : "";
        document.body.setAttribute("aria-busy", busy ? "true" : "false");
    };

    continueBtn.addEventListener("click", () => {
        // The normal button validation remains authoritative. Only show the
        // overlay when the actual analysis request is about to start.
        if (!continueBtn.disabled) setBusy(true);
    }, true);

    // The existing runPortfolioAnalysis() toggles this element between its
    // loading/results/error states. Observe that existing state rather than
    // changing the analysis implementation itself.
    const observer = new MutationObserver(() => {
        setBusy(!loading.classList.contains("hidden"));
    });
    observer.observe(loading, { attributes: true, attributeFilter: ["class"] });

    // Safety: if the page is unloaded/navigated away, release the lock.
    window.addEventListener("beforeunload", () => setBusy(false), { once: true });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installPortfolioBuilderBusyOverlay, { once: true });
} else {
    installPortfolioBuilderBusyOverlay();
}

export const api = {
    get: (path) => request(path, { method: "GET" }),
    post: (path, data) => request(path, { method: "POST", body: JSON.stringify(data) }),
};