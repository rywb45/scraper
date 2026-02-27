document.addEventListener("DOMContentLoaded", async () => {
    try {
        const stats = await api.get("/api/stats");

        $("#total-companies").textContent = stats.total_companies;
        $("#total-contacts").textContent = stats.total_contacts;
        $("#total-jobs").textContent = stats.total_jobs;
        $("#active-jobs").textContent = stats.active_jobs;

        // Industry chart
        const chart = $("#industry-chart");
        const maxCount = Math.max(...stats.industries.map(i => i.company_count), 1);
        if (stats.industries.length === 0) {
            chart.innerHTML = "<p>No data yet. Create a scrape job to get started.</p>";
        } else {
            chart.innerHTML = stats.industries.map(i => `
                <div class="bar-row">
                    <span class="bar-label">${escapeHtml(i.industry)}</span>
                    <div class="bar-track">
                        <div class="bar-fill" style="width:${(i.company_count / maxCount * 100)}%"></div>
                    </div>
                    <span class="bar-value">${i.company_count}</span>
                </div>
            `).join("");
        }

        // Recent jobs
        const jobsBody = $("#recent-jobs");
        if (stats.recent_jobs.length === 0) {
            jobsBody.innerHTML = '<tr><td colspan="4">No jobs yet</td></tr>';
        } else {
            jobsBody.innerHTML = stats.recent_jobs.map(j => `
                <tr>
                    <td><a href="/jobs/${j.id}">${escapeHtml(j.name)}</a></td>
                    <td>${statusBadge(j.status)}</td>
                    <td>${j.companies_found}</td>
                    <td>${formatDate(j.created_at)}</td>
                </tr>
            `).join("");
        }

        // Recent companies
        const compBody = $("#recent-companies");
        if (stats.recent_companies.length === 0) {
            compBody.innerHTML = '<tr><td colspan="5">No companies yet</td></tr>';
        } else {
            compBody.innerHTML = stats.recent_companies.map(c => `
                <tr>
                    <td><a href="/companies/${c.id}" class="company-name-cell">${companyLogo(c.domain)} ${escapeHtml(c.name)}</a></td>
                    <td>${escapeHtml(c.domain)}</td>
                    <td>${escapeHtml(c.industry || "—")}</td>
                    <td>${escapeHtml(c.state || "—")}</td>
                    <td>${formatDate(c.created_at)}</td>
                </tr>
            `).join("");
        }
    } catch (err) {
        console.error("Dashboard load error:", err);
    }
});
