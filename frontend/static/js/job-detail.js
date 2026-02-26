document.addEventListener("DOMContentLoaded", () => {
    let refreshInterval = null;

    async function loadJob() {
        try {
            const job = await api.get(`/api/jobs/${JOB_ID}`);
            $("#job-name").textContent = job.name;
            $("#js-status").innerHTML = statusBadge(job.status);
            $("#js-companies").textContent = job.companies_found;
            $("#js-contacts").textContent = job.contacts_found;
            $("#js-errors").textContent = job.errors_count;
            $("#job-progress").innerHTML = progressBar(job.progress);

            // Actions
            const actions = $("#job-actions");
            actions.innerHTML = "";
            if (job.status === "running") {
                actions.innerHTML = `
                    <button onclick="pauseJob()" class="secondary" style="width:auto">Pause</button>
                    <button onclick="cancelJob()" class="contrast" style="width:auto">Cancel</button>`;
            } else if (job.status === "paused") {
                actions.innerHTML = `
                    <button onclick="resumeJob()" style="width:auto">Resume</button>
                    <button onclick="cancelJob()" class="contrast" style="width:auto">Cancel</button>`;
            } else if (job.status === "pending") {
                actions.innerHTML = `
                    <button onclick="startJob()" style="width:auto">Start Job</button>
                    <button onclick="cancelJob()" class="contrast" style="width:auto">Cancel</button>`;
            }

            // Stop refreshing if terminal
            if (["completed", "failed", "cancelled"].includes(job.status) && refreshInterval) {
                clearInterval(refreshInterval);
            }
        } catch (err) {
            console.error("Load job error:", err);
        }
    }

    async function loadLogs() {
        try {
            const logs = await api.get(`/api/jobs/${JOB_ID}/logs?limit=200`);
            const feed = $("#log-feed");
            if (logs.length === 0) {
                feed.innerHTML = "<p>No logs yet.</p>";
            } else {
                feed.innerHTML = logs.map(l => `
                    <div class="log-entry log-${l.level}">
                        <small>${formatDate(l.created_at)}</small>
                        [${l.level.toUpperCase()}] ${escapeHtml(l.message)}
                        ${l.url ? `<br><small>${escapeHtml(l.url)}</small>` : ""}
                    </div>
                `).join("");
            }
        } catch (err) {
            console.error("Load logs error:", err);
        }
    }

    // Action handlers
    window.pauseJob = async () => {
        await api.post(`/api/jobs/${JOB_ID}/pause`);
        loadJob();
    };
    window.resumeJob = async () => {
        await api.post(`/api/jobs/${JOB_ID}/resume`);
        loadJob();
    };
    window.cancelJob = async () => {
        if (confirm("Cancel this job?")) {
            await api.post(`/api/jobs/${JOB_ID}/cancel`);
            loadJob();
        }
    };
    window.startJob = async () => {
        await api.post(`/api/jobs/${JOB_ID}/start`);
        loadJob();
    };

    loadJob();
    loadLogs();
    refreshInterval = setInterval(() => { loadJob(); loadLogs(); }, 3000);
});
