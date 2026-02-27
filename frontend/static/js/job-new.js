document.addEventListener("DOMContentLoaded", () => {
    const INDUSTRIES = [
        "Aerospace & Defense",
        "Industrial Machinery & Equipment",
        "Specialty Chemicals",
        "Commodity Trading",
        "Medical & Scientific Equipment",
        "Building Materials",
        "Electrical & Electronic Hardware",
    ];

    const grid = $("#industries-grid");
    INDUSTRIES.forEach(ind => {
        const label = document.createElement("label");
        label.innerHTML = `<input type="checkbox" name="industry" value="${ind}"> ${ind}`;
        grid.appendChild(label);
    });

    $("#select-all").addEventListener("change", (e) => {
        $$('input[name="industry"]').forEach(cb => cb.checked = e.target.checked);
    });

    $("#job-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const jobType = $("#job-type").value;
        const industries = $$('input[name="industry"]:checked').map(cb => cb.value);

        if (industries.length === 0) {
            alert("Please select at least one industry.");
            return;
        }

        // Auto-generate name if blank
        let name = $("#job-name").value.trim();
        if (!name) {
            const date = new Date().toLocaleDateString("en-US", {month: "short", day: "numeric"});
            if (industries.length <= 2) {
                name = industries.join(" & ") + " — " + date;
            } else {
                name = industries.length + " Industries — " + date;
            }
        }

        try {
            const job = await api.post("/api/jobs", {
                name,
                job_type: jobType,
                industries,
            });
            window.location.href = `/jobs/${job.id}`;
        } catch (err) {
            console.error("Create job error:", err);
            alert("Failed to create job. Check console for details.");
        }
    });
});
