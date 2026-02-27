document.addEventListener("DOMContentLoaded", async () => {
    let page = 1;
    let sortBy = "created_at";
    let sortDir = "desc";
    let searchTimer = null;

    // Load filter options
    try {
        const [industries, states, cities] = await Promise.all([
            api.get("/api/companies/industries"),
            api.get("/api/companies/states"),
            api.get("/api/companies/cities"),
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
        const citySel = $("#filter-city");
        cities.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c;
            opt.textContent = c;
            citySel.appendChild(opt);
        });
    } catch (e) {
        console.error("Filter load error:", e);
    }

    async function loadCompanies() {
        const search = $("#search").value;
        const industry = $("#filter-industry").value;
        const state = $("#filter-state").value;
        const city = $("#filter-city").value;
        const revenue = $("#filter-revenue").value;
        const params = new URLSearchParams({
            page, per_page: 25, sort_by: sortBy, sort_dir: sortDir,
        });
        if (search) params.set("search", search);
        if (industry) params.set("industry", industry);
        if (state) params.set("state", state);
        if (city) params.set("city", city);
        if (revenue) params.set("revenue_bracket", revenue);

        try {
            const data = await api.get(`/api/companies?${params}`);
            const body = $("#companies-body");
            if (data.items.length === 0) {
                body.innerHTML = '<tr><td colspan="11">No companies found</td></tr>';
            } else {
                body.innerHTML = data.items.map(c => {
                    const city = c.city && c.city.trim() ? escapeHtml(c.city) : "—";
                    const state = c.state && c.state.trim() ? escapeHtml(c.state) : "—";
                    const contacts = c.contact_count != null ? c.contact_count : 0;
                    return `<tr>
                        <td><a href="/companies/${c.id}" class="company-name-cell">${companyLogo(c.domain)} ${escapeHtml(c.name)}</a></td>
                        <td>${c.website ? `<a href="${escapeHtml(c.website)}" target="_blank" rel="noopener">${escapeHtml(c.domain)}</a>` : escapeHtml(c.domain || "—")}</td>
                        <td>${escapeHtml(c.industry || "—")}</td>
                        <td>${escapeHtml(c.employee_count_range || (c.employee_count ? c.employee_count.toLocaleString() : "—"))}</td>
                        <td>${c.estimated_revenue ? `<strong>${escapeHtml(c.estimated_revenue)}</strong>${c.revenue_source === "estimated" ? " <small>(est)</small>" : ""}` : "—"}</td>
                        <td>${city}</td>
                        <td>${state}</td>
                        <td>${contacts}</td>
                        <td>${sourceBadge(c.source)}</td>
                        <td><button class="btn-delete-co" onclick="deleteCompany(${c.id}, this)" title="Delete">&times;</button></td>
                    </tr>`;
                }).join("");
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
    $("#filter-city").addEventListener("change", () => { page = 1; loadCompanies(); });
    $("#filter-revenue").addEventListener("change", () => { page = 1; loadCompanies(); });

    // CSV export
    $("#btn-export").addEventListener("click", () => {
        const industry = $("#filter-industry").value;
        const state = $("#filter-state").value;
        const params = new URLSearchParams();
        if (industry) params.set("industry", industry);
        if (state) params.set("state", state);
        window.location.href = `/api/export/csv?${params}`;
    });

    // Expose for delete callback
    window._reloadCompanies = loadCompanies;
    loadCompanies();
});

async function deleteCompany(id, btn) {
    if (!confirm("Delete this company?")) return;
    btn.disabled = true;
    try {
        await api.del(`/api/companies/${id}`);
        if (window._reloadCompanies) window._reloadCompanies();
    } catch (e) {
        console.error("Delete error:", e);
        btn.disabled = false;
    }
}
