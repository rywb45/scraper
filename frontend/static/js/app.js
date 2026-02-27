// Shared API client
const api = {
    async get(url) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`GET ${url}: ${res.status}`);
        return res.json();
    },

    async post(url, data) {
        const res = await fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(data),
        });
        if (!res.ok) throw new Error(`POST ${url}: ${res.status}`);
        return res.json();
    },

    async patch(url, data) {
        const res = await fetch(url, {
            method: "PATCH",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(data),
        });
        if (!res.ok) throw new Error(`PATCH ${url}: ${res.status}`);
        return res.json();
    },

    async del(url) {
        const res = await fetch(url, {method: "DELETE"});
        if (!res.ok) throw new Error(`DELETE ${url}: ${res.status}`);
    },
};

// Utility helpers
function $(sel, parent = document) {
    return parent.querySelector(sel);
}

function $$(sel, parent = document) {
    return [...parent.querySelectorAll(sel)];
}

function statusBadge(status) {
    return `<span class="badge badge-${status}">${status}</span>`;
}

function progressBar(percent) {
    return `<div class="progress-bar">
        <div class="fill" style="width:${percent}%"></div>
        <span class="label">${percent}%</span>
    </div>`;
}

function confidenceClass(val) {
    if (val >= 80) return "confidence-high";
    if (val >= 50) return "confidence-medium";
    return "confidence-low";
}

function formatDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("en-US", {
        month: "short", day: "numeric", year: "numeric",
        hour: "2-digit", minute: "2-digit",
    });
}

function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function companyLogo(domain, size = 20) {
    if (!domain) return "";
    const logoUrl = `https://logo.clearbit.com/${encodeURIComponent(domain)}`;
    const fallbackUrl = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=${size}`;
    return `<img src="${logoUrl}" alt="" width="${size}" height="${size}" class="company-logo" onerror="this.onerror=null;this.src='${fallbackUrl}'">`;
}
