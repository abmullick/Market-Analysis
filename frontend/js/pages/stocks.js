import { initStockSelection } from "../js/features/stock-selection/index.js";
import { initStockDetail } from "../js/features/stock-selection/stock-detail/index.js";

document.addEventListener("DOMContentLoaded", () => {
    initStockSelection();
    initStockDetail();
});
