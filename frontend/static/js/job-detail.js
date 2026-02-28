document.addEventListener("DOMContentLoaded", () => {
    let refreshInterval = null;
    let jobStartTime = null;
    let elapsedTimer = null;
    let logVisible = false;
    let lastLogCount = 0;

    // Phase detection from log messages
    const PHASES = [
        { key: "discovery", match: "Starting discovery phase", label: "Discovery", icon: "🔍" },
        { key: "thomasnet", match: "Searching ThomasNet", label: "ThomasNet", icon: "📘" },
        { key: "kompass", match: "Searching Kompass", label: "Kompass", icon: "📗" },
        { key: "industrynet", match: "Searching IndustryNet", label: "IndustryNet", icon: "📙" },
        { key: "contacts", match: "Starting contact enrichment", label: "Contact Enrichment", icon: "👤" },
        { key: "email", match: "Starting email pattern", label: "Email Patterns", icon: "✉️" },
    ];

    function parsePhases(logs) {
        // logs come newest-first from API, reverse for chronological
        const chronological = [...logs].reverse();
        const phases = [];
        let currentPhase = null;

        for (const log of chronological) {
            const ts = new Date(log.created_at);

            // Check if this log starts a new phase
            for (const p of PHASES) {
                if (log.message.includes(p.match)) {
                    if (currentPhase) {
                        currentPhase.endTime = ts;
                        currentPhase.duration = (ts - currentPhase.startTime) / 1000;
                    }
                    currentPhase = {
                        ...p,
                        startTime: ts,
                        endTime: null,
                        duration: null,
                        status: "running",
                        details: [],
                        companiesFound: 0,
                        contactsFound: 0,
                    };
                    phases.push(currentPhase);
                    continue;
                }
            }

            // Capture details for current phase
            if (currentPhase) {
                if (log.message.startsWith("Found:")) {
                    currentPhase.companiesFound++;
                }
                if (log.message.startsWith("Enriched ")) {
                    currentPhase.details.push(log.message);
                }
                if (log.message.includes("found") && log.message.includes("new companies")) {
                    currentPhase.details.push(log.message);
                }
                if (log.message.includes("complete:") || log.message.includes("complete.")) {
                    currentPhase.endTime = ts;
                    currentPhase.duration = (ts - currentPhase.startTime) / 1000;
                    currentPhase.status = "completed";
                }
                if (log.level === "error") {
                    currentPhase.details.push(log.message);
                }
                // Sources info
                if (log.message.startsWith("Sources:")) {
                    currentPhase.details.push(log.message);
                }
            }
        }

        return phases;
    }

    function formatDuration(seconds) {
        if (seconds == null) return "";
        if (seconds < 60) return `${Math.round(seconds)}s`;
        const m = Math.floor(seconds / 60);
        const s = Math.round(seconds % 60);
        if (m < 60) return `${m}m ${s}s`;
        const h = Math.floor(m / 60);
        return `${h}h ${m % 60}m`;
    }

    function formatElapsed(startIso) {
        if (!startIso) return "—";
        const elapsed = (Date.now() - new Date(startIso).getTime()) / 1000;
        return formatDuration(elapsed);
    }

    function renderPipeline(phases, jobStatus) {
        const el = $("#pipeline");
        if (phases.length === 0) {
            el.innerHTML = '<div class="pipeline-empty">No phases started yet</div>';
            return;
        }

        el.innerHTML = phases.map((p, i) => {
            const isLast = i === phases.length - 1;
            const isActive = isLast && jobStatus === "running" && !p.endTime;
            const statusClass = isActive ? "phase-active" : (p.status === "completed" ? "phase-done" : "phase-pending");
            const duration = p.duration != null ? formatDuration(p.duration) : (isActive ? formatDuration((Date.now() - p.startTime.getTime()) / 1000) : "");
            const durationHtml = duration ? `<span class="phase-duration">${duration}</span>` : "";

            let detail = "";
            if (p.companiesFound > 0) {
                detail = `${p.companiesFound} companies`;
            }
            // Pull summary from details
            for (const d of p.details) {
                if (d.includes("found") && d.includes("companies")) {
                    detail = d;
                    break;
                }
                if (d.startsWith("Sources:")) {
                    detail = d;
                }
            }

            const spinner = isActive ? '<span class="phase-spinner"></span>' : '';
            const checkmark = p.status === "completed" ? '<span class="phase-check">✓</span>' : '';

            return `<div class="phase-card ${statusClass}">
                <div class="phase-header">
                    <span class="phase-label">${spinner}${checkmark}${escapeHtml(p.label)}</span>
                    ${durationHtml}
                </div>
                ${detail ? `<div class="phase-detail">${escapeHtml(detail)}</div>` : ""}
            </div>`;
        }).join('<div class="phase-connector"></div>');
    }

    function renderActivity(logs, jobStatus) {
        const feed = $("#activity-feed");
        // Show most recent logs as activity items
        const recent = logs.slice(0, 30); // newest first
        if (recent.length === 0) {
            feed.innerHTML = '<p class="activity-empty">Waiting for activity...</p>';
            return;
        }

        feed.innerHTML = recent.map(l => {
            const time = new Date(l.created_at);
            const timeStr = time.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

            let icon = "•";
            let cls = "activity-info";
            if (l.message.startsWith("Found:")) { icon = "+"; cls = "activity-found"; }
            else if (l.message.startsWith("Enriched ")) { icon = "↑"; cls = "activity-enriched"; }
            else if (l.message.startsWith("Enriching ")) { icon = "…"; cls = "activity-enriching"; }
            else if (l.message.includes("Searching ")) { icon = "→"; cls = "activity-search"; }
            else if (l.message.includes("complete")) { icon = "✓"; cls = "activity-done"; }
            else if (l.level === "warning") { icon = "!"; cls = "activity-warn"; }
            else if (l.level === "error") { icon = "✗"; cls = "activity-error"; }
            else if (l.message.startsWith("Sources:")) { icon = "⚙"; cls = "activity-info"; }

            // Shorten enrichment messages
            let msg = l.message;
            if (msg.startsWith("Enriching ") && msg.includes("(need:")) {
                const name = msg.split("(need:")[0].replace("Enriching ", "").trim();
                const needs = msg.split("(need:")[1].replace(")", "").trim();
                msg = `Enriching <strong>${escapeHtml(name)}</strong> → ${escapeHtml(needs)}`;
            } else if (msg.startsWith("Enriched ") && msg.includes(": ")) {
                const parts = msg.split(": ", 2);
                const name = parts[0].replace("Enriched ", "");
                msg = `Enriched <strong>${escapeHtml(name)}</strong> → ${escapeHtml(parts[1])}`;
            } else if (msg.startsWith("Found: ")) {
                const rest = msg.replace("Found: ", "");
                msg = `Found <strong>${escapeHtml(rest)}</strong>`;
            } else {
                msg = escapeHtml(msg);
            }

            return `<div class="activity-item ${cls}">
                <span class="activity-icon">${icon}</span>
                <span class="activity-time">${timeStr}</span>
                <span class="activity-msg">${msg}</span>
            </div>`;
        }).join("");

        // Auto-scroll to top (newest) if new logs arrived
        if (logs.length > lastLogCount) {
            feed.scrollTop = 0;
        }
        lastLogCount = logs.length;
    }

    async function loadJob() {
        try {
            const job = await api.get(`/api/jobs/${JOB_ID}`);
            $("#job-name").textContent = job.name;
            $("#js-status").innerHTML = statusBadge(job.status);
            $("#js-companies").textContent = job.companies_found;
            $("#js-contacts").textContent = job.contacts_found;

            // Elapsed time
            if (job.started_at) {
                jobStartTime = job.started_at;
                if (["completed", "failed", "cancelled"].includes(job.status) && job.completed_at) {
                    const elapsed = (new Date(job.completed_at) - new Date(job.started_at)) / 1000;
                    $("#js-elapsed").textContent = formatDuration(elapsed);
                    if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
                } else {
                    updateElapsed();
                    if (!elapsedTimer) {
                        elapsedTimer = setInterval(updateElapsed, 1000);
                    }
                }
            }

            // Actions
            const actions = $("#job-actions");
            actions.innerHTML = "";
            if (job.status === "running") {
                actions.innerHTML = `
                    <button onclick="pauseJob()" class="secondary" style="font-size:12px;padding:0.35rem 0.85rem">Pause</button>
                    <button onclick="cancelJob()" class="danger" style="font-size:12px;padding:0.35rem 0.85rem">Cancel</button>`;
            } else if (job.status === "paused") {
                actions.innerHTML = `
                    <button onclick="resumeJob()" style="font-size:12px;padding:0.35rem 0.85rem">Resume</button>
                    <button onclick="cancelJob()" class="danger" style="font-size:12px;padding:0.35rem 0.85rem">Cancel</button>`;
            } else if (job.status === "pending") {
                actions.innerHTML = `
                    <button onclick="startJob()" style="font-size:12px;padding:0.35rem 0.85rem">Start</button>
                    <button onclick="cancelJob()" class="danger" style="font-size:12px;padding:0.35rem 0.85rem">Cancel</button>`;
            }

            // Stop refreshing if terminal
            if (["completed", "failed", "cancelled"].includes(job.status) && refreshInterval) {
                clearInterval(refreshInterval);
                refreshInterval = null;
            }

            return job;
        } catch (err) {
            console.error("Load job error:", err);
            return null;
        }
    }

    function updateElapsed() {
        if (jobStartTime) {
            $("#js-elapsed").textContent = formatElapsed(jobStartTime);
        }
    }

    async function loadLogs() {
        try {
            const logs = await api.get(`/api/jobs/${JOB_ID}/logs?limit=500`);
            const job = await api.get(`/api/jobs/${JOB_ID}`);

            // Parse phases and render pipeline
            const phases = parsePhases(logs);
            renderPipeline(phases, job.status);

            // Render activity feed
            renderActivity(logs, job.status);

            // Render full log if visible
            if (logVisible) {
                renderFullLog(logs);
            }
        } catch (err) {
            console.error("Load logs error:", err);
        }
    }

    function renderFullLog(logs) {
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
    }

    window.toggleLogFeed = () => {
        logVisible = !logVisible;
        const el = $("#log-feed");
        const btn = $("#log-toggle-btn");
        el.style.display = logVisible ? "block" : "none";
        btn.textContent = logVisible ? "Hide" : "Show";
        if (logVisible) loadLogs();
    };

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
    refreshInterval = setInterval(() => { loadJob(); loadLogs(); }, 2000);
});
