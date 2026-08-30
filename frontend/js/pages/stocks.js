import { initStockSelection } from "../features/stock-selection/index.js";
import { initStockDetail } from "../features/stock-selection/stock-detail/index.js";

document.addEventListener("DOMContentLoaded", () => {
    initStockSelection();
    initStockDetail();
});
