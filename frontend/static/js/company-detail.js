let _editingContactId = null;

document.addEventListener("DOMContentLoaded", async () => {
    try {
        const company = await api.get(`/api/companies/${COMPANY_ID}`);
        $("#company-name").innerHTML = companyLogo(company.domain, 32) + " " + escapeHtml(company.name);

        const empDisplay = company.employee_count
            ? `${company.employee_count.toLocaleString()}${company.employee_count_range ? ` (${company.employee_count_range})` : ""}`
            : company.employee_count_range;
        const revDisplay = company.estimated_revenue
            ? `${company.estimated_revenue}${company.revenue_source === "estimated" ? " (estimated from headcount)" : ""}`
            : null;

        const fields = [
            ["Domain", company.domain],
            ["Website", company.website, "url"],
            ["Industry", company.industry],
            ["Sub-Industry", company.sub_industry],
            ["Description", company.description],
            ["Employees", empDisplay],
            ["Est. Revenue", revDisplay],
            ["City", company.city && company.city.trim() ? company.city : null],
            ["State", company.state && company.state.trim() ? company.state : null],
            ["Zip Code", company.zip_code],
            ["Phone", company.phone],
            ["Source", company.source],
        ];

        $("#company-info").innerHTML = fields
            .filter(([, v]) => v)
            .map(([k, v, type]) => {
                let cell;
                if (type === "url") {
                    cell = `<a href="${escapeHtml(v)}" target="_blank" rel="noopener">${escapeHtml(v)}</a>`;
                } else {
                    cell = escapeHtml(String(v));
                }
                return `<tr><th>${k}</th><td>${cell}</td></tr>`;
            })
            .join("");

        await loadContacts();
    } catch (err) {
        console.error("Company detail error:", err);
        $("#company-name").textContent = "Company not found";
    }
});

async function loadContacts() {
    const contacts = await api.get(`/api/contacts?company_id=${COMPANY_ID}`);
    $("#contact-count").textContent = `(${contacts.length})`;
    const body = $("#contacts-body");

    if (contacts.length === 0) {
        body.innerHTML = '<tr><td colspan="6" style="color:var(--text-secondary)">No contacts yet — click "+ Add Contact" to add one</td></tr>';
    } else {
        body.innerHTML = contacts.map(c => {
            const name = escapeHtml(c.full_name || [c.first_name, c.last_name].filter(Boolean).join(" ") || "—");
            const linkedin = c.linkedin_url
                ? `<a href="${escapeHtml(c.linkedin_url)}" target="_blank" rel="noopener" title="${escapeHtml(c.linkedin_url)}">Profile</a>`
                : "—";
            return `<tr>
                <td>${name}</td>
                <td>${escapeHtml(c.title || "—")}</td>
                <td>${c.email ? `<a href="mailto:${escapeHtml(c.email)}">${escapeHtml(c.email)}</a>` : "—"}</td>
                <td>${escapeHtml(c.phone || "—")}</td>
                <td>${linkedin}</td>
                <td style="white-space:nowrap">
                    <button class="btn-edit-contact" onclick="editContact(${c.id})" title="Edit">&#9998;</button>
                    <button class="btn-delete-co" onclick="deleteContact(${c.id})" title="Delete">&times;</button>
                </td>
            </tr>`;
        }).join("");
    }
}

function toggleContactForm() {
    _editingContactId = null;
    const wrap = $("#contact-form-wrap");
    wrap.style.display = wrap.style.display === "none" ? "block" : "none";
    if (wrap.style.display === "block") {
        _clearForm();
        $("#cf-first").focus();
        $("#cf-save-btn").textContent = "Save Contact";
    }
}

function cancelContactForm() {
    $("#contact-form-wrap").style.display = "none";
    _editingContactId = null;
    _clearForm();
}

function _clearForm() {
    $("#cf-first").value = "";
    $("#cf-last").value = "";
    $("#cf-title").value = "";
    $("#cf-email").value = "";
    $("#cf-phone").value = "";
    $("#cf-linkedin").value = "";
}

async function saveContact() {
    const first = $("#cf-first").value.trim();
    const last = $("#cf-last").value.trim();
    const title = $("#cf-title").value.trim();
    const email = $("#cf-email").value.trim();
    const phone = $("#cf-phone").value.trim();
    const linkedin = $("#cf-linkedin").value.trim();

    if (!first && !last && !email) {
        alert("Please enter at least a name or email.");
        return;
    }

    const btn = $("#cf-save-btn");
    btn.disabled = true;

    try {
        if (_editingContactId) {
            await api.patch(`/api/contacts/${_editingContactId}`, {
                first_name: first || null,
                last_name: last || null,
                full_name: [first, last].filter(Boolean).join(" ") || null,
                title: title || null,
                email: email || null,
                phone: phone || null,
                linkedin_url: linkedin || null,
            });
        } else {
            await api.post("/api/contacts", {
                company_id: COMPANY_ID,
                first_name: first || null,
                last_name: last || null,
                full_name: [first, last].filter(Boolean).join(" ") || null,
                title: title || null,
                email: email || null,
                email_confidence: email ? 100 : 0,
                phone: phone || null,
                linkedin_url: linkedin || null,
                source: "manual",
            });
        }
        cancelContactForm();
        await loadContacts();
    } catch (e) {
        console.error("Save contact error:", e);
        alert("Failed to save contact.");
    } finally {
        btn.disabled = false;
    }
}

async function editContact(id) {
    try {
        const c = await api.get(`/api/contacts/${id}`);
        _editingContactId = id;
        $("#cf-first").value = c.first_name || "";
        $("#cf-last").value = c.last_name || "";
        $("#cf-title").value = c.title || "";
        $("#cf-email").value = c.email || "";
        $("#cf-phone").value = c.phone || "";
        $("#cf-linkedin").value = c.linkedin_url || "";
        $("#cf-save-btn").textContent = "Update Contact";
        $("#contact-form-wrap").style.display = "block";
        $("#cf-first").focus();
    } catch (e) {
        console.error("Edit contact error:", e);
    }
}

async function deleteContact(id) {
    if (!confirm("Delete this contact?")) return;
    try {
        await api.del(`/api/contacts/${id}`);
        await loadContacts();
    } catch (e) {
        console.error("Delete contact error:", e);
    }
}
