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

    $("#job-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = $("#job-name").value.trim();
        const jobType = $("#job-type").value;
        const industries = $$('input[name="industry"]:checked').map(cb => cb.value);

        if (!name) return;
        if (industries.length === 0) {
            alert("Please select at least one industry.");
            return;
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
