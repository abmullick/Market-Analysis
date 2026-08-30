import { showLoading, hideLoading } from "../../components/loading.js";
import { renderTable } from "../../components/table.js";

export function initPortfolioAnalysis() {
    const uploadContainer = document.getElementById("portfolio-upload");
    const resultsContainer = document.getElementById("portfolio-results");

    if (!uploadContainer || !resultsContainer) return;

    uploadContainer.innerHTML = `
        <div class="upload-zone">
            <p>Upload your portfolio (CSV, Excel)</p>
            <input type="file" id="portfolio-file" accept=".csv,.xlsx,.xls" />
        </div>
    `;

    renderTable(resultsContainer, [
        { key: "symbol", label: "Symbol" },
        { key: "name", label: "Name" },
        { key: "quantity", label: "Quantity" },
        { key: "invested_value", label: "Invested" },
        { key: "current_value", label: "Current" },
        { key: "portfolio_weight", label: "Weight" },
    ], []);
}
