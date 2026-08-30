import { renderFilters } from "../../components/filters.js";
import { renderTable } from "../../components/table.js";

export function initScreener() {
    const filtersContainer = document.getElementById("filters");
    const resultsContainer = document.getElementById("results");

    if (!filtersContainer || !resultsContainer) return;

    renderFilters(filtersContainer, [
        { name: "sector", label: "Sector", type: "select", options: [] },
        { name: "strategy", label: "Strategy", type: "select", options: [
            { value: "growth", label: "Growth" },
            { value: "roe", label: "ROE" },
            { value: "value", label: "Value" },
            { value: "quality", label: "Quality" },
            { value: "overall", label: "Overall" },
        ]},
    ]);

    renderTable(resultsContainer, [
        { key: "symbol", label: "Symbol" },
        { key: "name", label: "Name" },
        { key: "score", label: "Score" },
    ], []);
}
