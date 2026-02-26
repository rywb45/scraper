document.addEventListener("DOMContentLoaded", async () => {
    try {
        const company = await api.get(`/api/companies/${COMPANY_ID}`);
        $("#company-name").textContent = company.name;

        const fields = [
            ["Domain", company.domain],
            ["Website", company.website],
            ["Industry", company.industry],
            ["Sub-Industry", company.sub_industry],
            ["Description", company.description],
            ["Employees", company.employee_count_range],
            ["City", company.city],
            ["State", company.state],
            ["Zip Code", company.zip_code],
            ["Phone", company.phone],
            ["Source", company.source],
        ];

        $("#company-info").innerHTML = fields
            .filter(([, v]) => v)
            .map(([k, v]) => `<tr><th>${k}</th><td>${escapeHtml(v)}</td></tr>`)
            .join("");

        // Load contacts
        const contacts = await api.get(`/api/contacts?company_id=${COMPANY_ID}`);
        $("#contact-count").textContent = `(${contacts.length})`;
        const body = $("#contacts-body");

        if (contacts.length === 0) {
            body.innerHTML = '<tr><td colspan="5">No contacts found</td></tr>';
        } else {
            body.innerHTML = contacts.map(c => {
                const conf = Math.round(c.email_confidence);
                return `
                <tr>
                    <td>${escapeHtml(c.full_name || [c.first_name, c.last_name].filter(Boolean).join(" ") || "—")}</td>
                    <td>${escapeHtml(c.title || "—")}</td>
                    <td>${c.email ? `<a href="mailto:${escapeHtml(c.email)}">${escapeHtml(c.email)}</a>` : "—"}</td>
                    <td><span class="${confidenceClass(conf)}">${conf}%</span></td>
                    <td>${escapeHtml(c.phone || "—")}</td>
                </tr>`;
            }).join("");
        }
    } catch (err) {
        console.error("Company detail error:", err);
        $("#company-name").textContent = "Company not found";
    }
});
