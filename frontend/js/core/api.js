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

const api = {
    get: (path) => request(path, { method: "GET" }),
    post: (path, data) => request(path, { method: "POST", body: JSON.stringify(data) }),
};
