document.addEventListener("DOMContentLoaded", () => {
    let refreshInterval = null;
    let jobStartTime = null;
    let elapsedTimer = null;
    let logVisible = false;
    let lastLogCount = 0;
    let currentJobStatus = "pending";

    // Phase detection from log messages
    const PHASES = [
        { key: "discovery", match: "Starting discovery phase", label: "Discovery" },
        { key: "thomasnet", match: "Searching ThomasNet", label: "ThomasNet" },
        { key: "kompass", match: "Searching Kompass", label: "Kompass" },
        { key: "industrynet", match: "Searching IndustryNet", label: "IndustryNet" },
        { key: "data_enrich", match: "Starting data enrichment", label: "Data Enrichment" },
        { key: "contacts", match: "Starting contact enrichment", label: "Contact Enrichment" },
        { key: "email", match: "Starting email pattern", label: "Email Patterns" },
    ];

    function parsePhases(logs) {
        const chronological = [...logs].reverse();
        const phases = [];
        let currentPhase = null;

        for (const log of chronological) {
            const ts = parseUTC(log.created_at);

            for (const p of PHASES) {
                if (log.message.includes(p.match)) {
                    if (currentPhase) {
                        currentPhase.endTime = ts;
                        currentPhase.duration = (ts - currentPhase.startTime) / 1000;
                        if (currentPhase.status === "running") currentPhase.status = "completed";
                    }
                    currentPhase = {
                        ...p,
                        startTime: ts,
                        endTime: null,
                        duration: null,
                        status: "running",
                        details: [],
                        companiesFound: 0,
                    };
                    phases.push(currentPhase);
                    continue;
                }
            }

            if (currentPhase) {
                if (log.message.startsWith("Found:")) currentPhase.companiesFound++;
                if (log.message.includes("complete:") || log.message.includes("complete.") || log.message.includes("enrichment complete") || log.message.includes("Enrichment complete") || log.message.includes("Email patterns:")) {
                    currentPhase.endTime = ts;
                    currentPhase.duration = (ts - currentPhase.startTime) / 1000;
                    currentPhase.status = "completed";
                    currentPhase.details.push(log.message);
                }
                if (log.message.startsWith("Sources:")) currentPhase.details.push(log.message);
                if (log.message.includes("found") && log.message.includes("new companies")) currentPhase.details.push(log.message);
            }
        }

        // If job is completed/failed/cancelled, mark last phase as done
        if (currentPhase && ["completed", "failed", "cancelled"].includes(currentJobStatus)) {
            if (currentPhase.status === "running") currentPhase.status = "completed";
        }

        return phases;
    }

    function formatDuration(seconds) {
        if (seconds == null) return "";
        const totalSec = Math.round(seconds);
        const h = Math.floor(totalSec / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const s = totalSec % 60;
        if (h > 0) return h + "h " + m + "m " + s + "s";
        return m + "m " + s + "s";
    }

    function parseUTC(iso) {
        if (!iso) return null;
        return new Date(iso.endsWith("Z") ? iso : iso + "Z");
    }

    function formatElapsed(startIso) {
        if (!startIso) return "—";
        const elapsed = (Date.now() - parseUTC(startIso).getTime()) / 1000;
        return formatDuration(elapsed);
    }

    function renderPipeline(phases) {
        const el = $("#pipeline");
        if (!el) return;
        if (phases.length === 0) {
            el.innerHTML = '<div class="pipeline-empty">No phases started yet</div>';
            return;
        }

        el.innerHTML = phases.map((p, i) => {
            const isLast = i === phases.length - 1;
            const isActive = isLast && currentJobStatus === "running" && p.status === "running";
            const statusClass = isActive ? "phase-active" : (p.status === "completed" ? "phase-done" : "phase-pending");

            let duration = "";
            if (p.duration != null) {
                duration = formatDuration(p.duration);
            } else if (isActive) {
                duration = formatDuration((Date.now() - p.startTime.getTime()) / 1000);
            }
            const durationHtml = duration ? '<span class="phase-duration">' + duration + '</span>' : "";

            let detail = "";
            if (p.companiesFound > 0) detail = p.companiesFound + " companies found";
            for (const d of p.details) {
                if (d.includes("found") && d.includes("companies")) { detail = d; break; }
                if (d.startsWith("Sources:")) detail = d;
            }

            const spinner = isActive ? '<span class="phase-spinner"></span>' : '';
            const check = p.status === "completed" ? '<span class="phase-check">&#10003;</span>' : '';

            const connector = i < phases.length - 1 ? '<div class="phase-connector"></div>' : '';

            return '<div class="phase-card ' + statusClass + '">' +
                '<div class="phase-header">' +
                    '<span class="phase-label">' + spinner + check + escapeHtml(p.label) + '</span>' +
                    durationHtml +
                '</div>' +
                (detail ? '<div class="phase-detail">' + escapeHtml(detail) + '</div>' : '') +
            '</div>' + connector;
        }).join("");
    }

    function renderActivity(logs) {
        const feed = $("#activity-feed");
        if (!feed) return;

        const recent = logs.slice(0, 40);
        if (recent.length === 0) {
            feed.innerHTML = '<p class="activity-empty">Waiting for activity...</p>';
            return;
        }

        let html = "";
        for (let i = 0; i < recent.length; i++) {
            const l = recent[i];
            const time = parseUTC(l.created_at);
            const timeStr = time.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

            let icon = "&#8226;";
            let cls = "activity-info";
            const msg = l.message;

            if (msg.startsWith("Found:")) { icon = "+"; cls = "activity-found"; }
            else if (msg.startsWith("Enriched ")) { icon = "&#8593;"; cls = "activity-enriched"; }
            else if (msg.startsWith("Enriching ")) { icon = "&#8230;"; cls = "activity-enriching"; }
            else if (msg.includes("Searching ")) { icon = "&#8594;"; cls = "activity-search"; }
            else if (msg.includes("complete") || msg.includes("Complete")) { icon = "&#10003;"; cls = "activity-done"; }
            else if (l.level === "warning") { icon = "!"; cls = "activity-warn"; }
            else if (l.level === "error") { icon = "&#10007;"; cls = "activity-error"; }
            else if (msg.startsWith("Sources:")) { icon = "&#9881;"; cls = "activity-info"; }

            let displayMsg = "";
            if (msg.startsWith("Enriching ") && msg.includes("(need:")) {
                const name = msg.split("(need:")[0].replace("Enriching ", "").trim();
                const needs = msg.split("(need:")[1].replace(")", "").trim();
                displayMsg = "Enriching <strong>" + escapeHtml(name) + "</strong> &rarr; " + escapeHtml(needs);
            } else if (msg.startsWith("Enriched ") && msg.includes(": ")) {
                const idx = msg.indexOf(": ");
                const name = msg.substring(9, idx);
                const vals = msg.substring(idx + 2);
                displayMsg = "Enriched <strong>" + escapeHtml(name) + "</strong> &rarr; " + escapeHtml(vals);
            } else if (msg.startsWith("Found: ")) {
                displayMsg = "Found <strong>" + escapeHtml(msg.substring(7)) + "</strong>";
            } else {
                displayMsg = escapeHtml(msg);
            }

            html += '<div class="activity-item ' + cls + '">' +
                '<span class="activity-icon">' + icon + '</span>' +
                '<span class="activity-time">' + timeStr + '</span>' +
                '<span class="activity-msg">' + displayMsg + '</span>' +
            '</div>';
        }

        feed.innerHTML = html;

        if (logs.length > lastLogCount) {
            feed.scrollTop = 0;
        }
        lastLogCount = logs.length;
    }

    async function loadJob() {
        try {
            const job = await api.get("/api/jobs/" + JOB_ID);
            currentJobStatus = job.status;
            $("#job-name").textContent = job.name;
            $("#js-status").innerHTML = statusBadge(job.status);
            $("#js-companies").textContent = job.companies_found;
            $("#js-contacts").textContent = job.contacts_found;

            if (job.started_at) {
                jobStartTime = job.started_at;
                if (["completed", "failed", "cancelled"].includes(job.status) && job.completed_at) {
                    const elapsed = (parseUTC(job.completed_at) - parseUTC(job.started_at)) / 1000;
                    $("#js-elapsed").textContent = formatDuration(elapsed);
                    if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
                } else {
                    updateElapsed();
                    if (!elapsedTimer) {
                        elapsedTimer = setInterval(updateElapsed, 1000);
                    }
                }
            }

            const actions = $("#job-actions");
            actions.innerHTML = "";
            if (job.status === "running") {
                actions.innerHTML = '<button onclick="pauseJob()" class="secondary" style="font-size:12px;padding:0.35rem 0.85rem">Pause</button>' +
                    '<button onclick="cancelJob()" class="danger" style="font-size:12px;padding:0.35rem 0.85rem">Cancel</button>';
            } else if (job.status === "paused") {
                actions.innerHTML = '<button onclick="resumeJob()" style="font-size:12px;padding:0.35rem 0.85rem">Resume</button>' +
                    '<button onclick="cancelJob()" class="danger" style="font-size:12px;padding:0.35rem 0.85rem">Cancel</button>';
            } else if (job.status === "pending") {
                actions.innerHTML = '<button onclick="startJob()" style="font-size:12px;padding:0.35rem 0.85rem">Start</button>' +
                    '<button onclick="cancelJob()" class="danger" style="font-size:12px;padding:0.35rem 0.85rem">Cancel</button>';
            }

            if (["completed", "failed", "cancelled"].includes(job.status) && refreshInterval) {
                clearInterval(refreshInterval);
                refreshInterval = null;
            }
        } catch (err) {
            console.error("Load job error:", err);
        }
    }

    function updateElapsed() {
        if (jobStartTime) {
            $("#js-elapsed").textContent = formatElapsed(jobStartTime);
        }
    }

    async function loadLogs() {
        try {
            const logs = await api.get("/api/jobs/" + JOB_ID + "/logs?limit=500");
            const phases = parsePhases(logs);
            renderPipeline(phases);
            renderActivity(logs);
            if (logVisible) renderFullLog(logs);
        } catch (err) {
            console.error("Load logs error:", err);
        }
    }

    function renderFullLog(logs) {
        const feed = $("#log-feed");
        if (!feed) return;
        if (logs.length === 0) {
            feed.innerHTML = "<p>No logs yet.</p>";
        } else {
            feed.innerHTML = logs.map(function(l) {
                return '<div class="log-entry log-' + l.level + '">' +
                    '<small>' + formatDate(l.created_at) + '</small> ' +
                    '[' + l.level.toUpperCase() + '] ' + escapeHtml(l.message) +
                    (l.url ? '<br><small>' + escapeHtml(l.url) + '</small>' : '') +
                '</div>';
            }).join("");
        }
    }

    window.toggleLogFeed = function() {
        logVisible = !logVisible;
        var el = $("#log-feed");
        var btn = $("#log-toggle-btn");
        el.style.display = logVisible ? "block" : "none";
        btn.textContent = logVisible ? "Hide" : "Show";
        if (logVisible) loadLogs();
    };

    window.pauseJob = async function() {
        await api.post("/api/jobs/" + JOB_ID + "/pause");
        loadJob();
    };
    window.resumeJob = async function() {
        await api.post("/api/jobs/" + JOB_ID + "/resume");
        loadJob();
    };
    window.cancelJob = async function() {
        if (confirm("Cancel this job?")) {
            await api.post("/api/jobs/" + JOB_ID + "/cancel");
            loadJob();
        }
    };
    window.startJob = async function() {
        await api.post("/api/jobs/" + JOB_ID + "/start");
        loadJob();
    };

    loadJob();
    loadLogs();
    refreshInterval = setInterval(function() { loadJob(); loadLogs(); }, 2000);
});
