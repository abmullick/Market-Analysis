window.APP_CONFIG = {
    API_BASE_URL: "/api",
};

export const utils = {
    formatNumber(value, decimals = 2) {
        if (value === null || value === undefined) return "N/A";
        return Number(value).toFixed(decimals);
    },
    formatPercent(value, decimals = 2) {
        if (value === null || value === undefined) return "N/A";
        return `${Number(value).toFixed(decimals)}%`;
    },
    debounce(fn, delay) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    },
};
