/* User-facing DV01 explanation for Bond Analysis Help. */

const DV01_TITLE = "DV01 — What It Means and How to Use It";

function addDv01Help() {
    const section = [...document.querySelectorAll(".help-section")].find((candidate) =>
        candidate.querySelector("h3")?.textContent?.trim() === "Bond Analysis"
    );
    if (!section || section.dataset.dv01HelpAdded === "true") return Boolean(section);

    const grid = section.querySelector(".help-grid");
    if (!grid) return false;

    const card = document.createElement("div");
    card.className = "help-card";
    card.innerHTML = `
        <h4>${DV01_TITLE}</h4>
        <p><strong>DV01</strong> means <strong>Dollar Value of a 1 Basis Point</strong>. In this application, it tells you approximately how much the bond's price or position value would change if its yield moved by <strong>1 basis point (0.01%)</strong>.</p>
        <ol>
            <li>Find the bond's <strong>DV01</strong> in the bond analysis details.</li>
            <li>Read the number as the approximate currency-value sensitivity for a <strong>1 bp</strong> yield move for the position represented by the displayed calculation.</li>
            <li>If DV01 is ₹750, for example, a roughly <strong>1 bp rise</strong> in yield would imply an approximate <strong>₹750 fall</strong> in value, while a roughly <strong>1 bp fall</strong> would imply an approximate <strong>₹750 rise</strong>, all else equal.</li>
            <li>Use DV01 to compare the <strong>absolute interest-rate sensitivity</strong> of bonds or positions. A larger DV01 means a larger currency-value change for the same 1 bp yield movement.</li>
            <li>Use <strong>Modified Duration</strong> when you want percentage price sensitivity, and use <strong>DV01</strong> when you want the corresponding currency-value sensitivity.</li>
            <li>Use <strong>Convexity</strong> alongside duration/DV01 when considering larger yield changes, because the price-yield relationship is curved and the simple first-order DV01 estimate becomes less precise as the yield move gets larger.</li>
        </ol>
        <p><strong>Example:</strong> if Bond A has a DV01 of ₹300 and Bond B has a DV01 of ₹1,200 for comparable positions, Bond B has about four times the currency sensitivity to a 1 bp yield movement.</p>
        <p><strong>Important:</strong> DV01 is a <strong>sensitivity measure, not a forecast</strong>. It does not predict that yields will move by 1 bp; it tells you the approximate value impact if they do. The estimate also assumes the other relevant factors remain unchanged and is most useful for small yield movements.</p>
    `;
    grid.appendChild(card);
    section.dataset.dv01HelpAdded = "true";
    return true;
}

function install() {
    if (addDv01Help()) return;
    const root = document.body;
    if (!root) return;
    const observer = new MutationObserver(() => {
        if (addDv01Help()) observer.disconnect();
    });
    observer.observe(root, { childList: true, subtree: true });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
} else {
    install();
}

export { addDv01Help };