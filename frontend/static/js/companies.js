document.addEventListener("DOMContentLoaded", async () => {
    let page = 1;
    let sortBy = "created_at";
    let sortDir = "desc";
    let searchTimer = null;

    // Load filter options
    try {
        const [industries, states] = await Promise.all([
            api.get("/api/companies/industries"),
            api.get("/api/companies/states"),
        ]);
        const indSel = $("#filter-industry");
        industries.forEach(i => {
            const opt = document.createElement("option");
            opt.value = i;
            opt.textContent = i;
            indSel.appendChild(opt);
        });
        const stSel = $("#filter-state");
        states.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s;
            opt.textContent = s;
            stSel.appendChild(opt);
        });
    } catch (e) {
        console.error("Filter load error:", e);
    }

    async function loadCompanies() {
        const search = $("#search").value;
        const industry = $("#filter-industry").value;
        const state = $("#filter-state").value;
        const params = new URLSearchParams({
            page, per_page: 25, sort_by: sortBy, sort_dir: sortDir,
        });
        if (search) params.set("search", search);
        if (industry) params.set("industry", industry);
        if (state) params.set("state", state);

        try {
            const data = await api.get(`/api/companies?${params}`);
            const body = $("#companies-body");
            if (data.items.length === 0) {
                body.innerHTML = '<tr><td colspan="6">No companies found</td></tr>';
            } else {
                body.innerHTML = data.items.map(c => `
                    <tr>
                        <td><a href="/companies/${c.id}">${escapeHtml(c.name)}</a></td>
                        <td>${escapeHtml(c.domain)}</td>
                        <td>${escapeHtml(c.industry || "—")}</td>
                        <td>${escapeHtml(c.state || "—")}</td>
                        <td>${c.contact_count}</td>
                        <td>${formatDate(c.created_at)}</td>
                    </tr>
                `).join("");
            }

            // Pagination
            const pag = $("#pagination");
            pag.innerHTML = "";
            if (data.pages > 1) {
                const prevBtn = document.createElement("button");
                prevBtn.textContent = "Prev";
                prevBtn.disabled = page <= 1;
                prevBtn.className = "outline";
                prevBtn.onclick = () => { page--; loadCompanies(); };
                pag.appendChild(prevBtn);

                const info = document.createElement("span");
                info.textContent = `Page ${data.page} of ${data.pages} (${data.total} total)`;
                pag.appendChild(info);

                const nextBtn = document.createElement("button");
                nextBtn.textContent = "Next";
                nextBtn.disabled = page >= data.pages;
                nextBtn.className = "outline";
                nextBtn.onclick = () => { page++; loadCompanies(); };
                pag.appendChild(nextBtn);
            }
        } catch (err) {
            console.error("Load companies error:", err);
        }
    }

    // Sorting
    $$("th.sortable").forEach(th => {
        th.addEventListener("click", () => {
            const col = th.dataset.sort;
            if (sortBy === col) {
                sortDir = sortDir === "asc" ? "desc" : "asc";
            } else {
                sortBy = col;
                sortDir = "asc";
            }
            page = 1;
            loadCompanies();
        });
    });

    // Search debounce
    $("#search").addEventListener("input", () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => { page = 1; loadCompanies(); }, 300);
    });

    // Filters
    $("#filter-industry").addEventListener("change", () => { page = 1; loadCompanies(); });
    $("#filter-state").addEventListener("change", () => { page = 1; loadCompanies(); });

    // CSV export
    $("#btn-export").addEventListener("click", () => {
        const industry = $("#filter-industry").value;
        const state = $("#filter-state").value;
        const params = new URLSearchParams();
        if (industry) params.set("industry", industry);
        if (state) params.set("state", state);
        window.location.href = `/api/export/csv?${params}`;
    });

    loadCompanies();
});
