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
    return new Date(iso).toLocaleString("en-US", {
        month: "short", day: "numeric", year: "numeric",
        hour: "2-digit", minute: "2-digit",
        timeZone: "America/New_York",
    });
}

function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// Scrape dropdown
const DEFAULT_INDUSTRIES = [
    "Aerospace & Defense",
    "Industrial Machinery & Equipment",
    "Specialty Chemicals",
    "Commodity Trading",
    "Medical & Scientific Equipment",
    "Building Materials",
    "Electrical & Electronic Hardware",
];

let _scrapeIndustries = [...DEFAULT_INDUSTRIES];

function _initScrapeMenu() {
    const list = $("#scrape-industry-list");
    if (!list) return;
    // Load any custom industries from localStorage
    const custom = JSON.parse(localStorage.getItem("customIndustries") || "[]");
    _scrapeIndustries = [...DEFAULT_INDUSTRIES, ...custom];
    _renderIndustryList();
}

function _renderIndustryList() {
    const list = $("#scrape-industry-list");
    if (!list) return;
    list.innerHTML = _scrapeIndustries.map((ind, i) => `
        <label><input type="checkbox" class="scrape-ind-cb" value="${escapeHtml(ind)}" checked> ${escapeHtml(ind)}</label>
    `).join("");
    _syncSelectAll();
}

function toggleScrapeMenu(e) {
    e.stopPropagation();
    const menu = $("#scrape-menu");
    menu.classList.toggle("open");
}

// Close menu on outside click
document.addEventListener("click", (e) => {
    const dropdown = $("#scrape-dropdown");
    const menu = $("#scrape-menu");
    if (dropdown && menu && !dropdown.contains(e.target)) {
        menu.classList.remove("open");
    }
});

function toggleAllIndustries(el) {
    $$(".scrape-ind-cb").forEach(cb => cb.checked = el.checked);
}

function _syncSelectAll() {
    const all = $$(".scrape-ind-cb");
    const checked = all.filter(cb => cb.checked);
    const selectAll = $("#scrape-select-all");
    if (selectAll) selectAll.checked = checked.length === all.length;
}

// Delegate change events for industry checkboxes
document.addEventListener("change", (e) => {
    if (e.target.classList.contains("scrape-ind-cb")) _syncSelectAll();
});

function addCustomIndustry() {
    const input = $("#scrape-new-industry");
    const name = input.value.trim();
    if (!name) return;
    if (_scrapeIndustries.some(i => i.toLowerCase() === name.toLowerCase())) {
        input.value = "";
        return;
    }
    _scrapeIndustries.push(name);
    // Persist custom industries
    const custom = _scrapeIndustries.filter(i => !DEFAULT_INDUSTRIES.includes(i));
    localStorage.setItem("customIndustries", JSON.stringify(custom));
    _renderIndustryList();
    input.value = "";
}

async function runScrape() {
    const selected = $$(".scrape-ind-cb").filter(cb => cb.checked).map(cb => cb.value);
    if (selected.length === 0) return;

    const selectedSources = $$(".scrape-src-cb").filter(cb => cb.checked).map(cb => cb.value);
    if (selectedSources.length === 0) return;

    const goBtn = $("#scrape-go-btn");
    const scrapeBtn = $("#scrape-btn");
    goBtn.disabled = true;
    goBtn.textContent = "Starting...";
    scrapeBtn.disabled = true;
    scrapeBtn.innerHTML = `<svg class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> Scraping...`;

    try {
        const date = new Date().toLocaleDateString("en-US", {month: "short", day: "numeric"});
        const location = ($("#scrape-location")?.value || "").trim();
        const srcLabel = selectedSources.length === 4 ? "" : " (" + selectedSources.join(", ") + ")";
        const locLabel = location ? " — " + location : "";
        const label = selected.length === _scrapeIndustries.length ? "All Industries" : selected.length + " Industries";
        const job = await api.post("/api/jobs", {
            name: label + srcLabel + locLabel + " — " + date,
            job_type: "full",
            industries: selected,
            sources: selectedSources,
            location: location || undefined,
        });
        await api.post(`/api/jobs/${job.id}/start`);
        window.location.href = `/jobs/${job.id}`;
    } catch (err) {
        console.error("Scrape error:", err);
        goBtn.disabled = false;
        goBtn.textContent = "Start Scrape";
        scrapeBtn.disabled = false;
        scrapeBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> Scrape`;
    }
}

// Initialize scrape menu on load
_initScrapeMenu();

// Load API credits on every page
(async function loadApiCredits() {
    try {
        const data = await api.get("/api/stats/api-usage");
        const el = $("#api-credits");
        if (!el || data.error) return;
        const credits = data.credit || data.balance || 0;
        el.innerHTML = `<span class="dot"></span>${credits.toLocaleString()} searches`;
        el.classList.add("loaded");
        if (credits < 100) el.classList.add("critical");
        else if (credits < 500) el.classList.add("low");
    } catch (e) {
        // silently fail
    }
})();

function companyLogo(domain, size = 20) {
    if (!domain) return "";
    const logoUrl = `https://logo.clearbit.com/${encodeURIComponent(domain)}`;
    const fallbackUrl = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=${size}`;
    return `<img src="${logoUrl}" alt="" width="${size}" height="${size}" class="company-logo" onerror="this.onerror=null;this.src='${fallbackUrl}'">`;
}

const SOURCE_LABELS = {
    "google_search": "Google",
    "web": "Google",
    "thomasnet": "ThomasNet",
    "kompass": "Kompass",
    "industrynet": "IndustryNet",
    "manual": "Manual",
};

function sourceBadge(source) {
    const label = SOURCE_LABELS[source] || source || "Unknown";
    return `<span class="badge badge-source" title="Data source: ${escapeHtml(label)}">${escapeHtml(label)}</span>`;
}

function revenueSourceLabel(src) {
    if (!src) return "";
    const labels = {
        "knowledge_graph": "Google Knowledge Graph",
        "search_snippet": "Google Search",
        "estimated": "Estimated from headcount",
        "page_text": "Company website",
    };
    return labels[src] || src;
}
