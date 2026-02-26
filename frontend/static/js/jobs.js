document.addEventListener("DOMContentLoaded", async () => {
    async function loadJobs() {
        try {
            const jobs = await api.get("/api/jobs");
            const body = $("#jobs-body");
            if (jobs.length === 0) {
                body.innerHTML = '<tr><td colspan="8">No jobs yet. <a href="/jobs/new">Create one</a>.</td></tr>';
            } else {
                body.innerHTML = jobs.map(j => `
                    <tr>
                        <td><a href="/jobs/${j.id}">${escapeHtml(j.name)}</a></td>
                        <td>${escapeHtml(j.job_type || "—")}</td>
                        <td>${statusBadge(j.status)}</td>
                        <td style="min-width:120px">${progressBar(j.progress)}</td>
                        <td>${j.companies_found}</td>
                        <td>${j.contacts_found}</td>
                        <td>${j.errors_count}</td>
                        <td>${formatDate(j.created_at)}</td>
                    </tr>
                `).join("");
            }
        } catch (err) {
            console.error("Load jobs error:", err);
        }
    }

    loadJobs();
    // Auto-refresh every 5 seconds
    setInterval(loadJobs, 5000);
});
