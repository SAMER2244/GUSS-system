document.addEventListener("DOMContentLoaded", () => {
    // ─── DOM Elements ────────────────────────────────────────────────────────
    // Auth & Layout
    const loginOverlay = document.getElementById("loginOverlay");
    const appLayout = document.getElementById("appLayout");
    const loginForm = document.getElementById("loginForm");
    const usernameInput = document.getElementById("usernameInput");
    const passwordInput = document.getElementById("passwordInput");
    const loginError = document.getElementById("loginError");
    const btnLogout = document.getElementById("btnLogout");
    const loggedInUser = document.getElementById("loggedInUser");
    
    // Forgot Password Modal
    const btnForgotPassword = document.getElementById("btnForgotPassword");
    const forgotPasswordModal = document.getElementById("forgotPasswordModal");
    const btnCloseModal = document.getElementById("btnCloseModal");

    // Sidebar Nav
    const navTabBtns = document.querySelectorAll(".nav-tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");

    // Dashboard Filters & Table
    const systemStatus = document.getElementById("systemStatus");
    const officeFilter = document.getElementById("officeFilter");
    const monthFilter = document.getElementById("monthFilter");
    const statusFilter = document.getElementById("statusFilter");
    const submissionsTableBody = document.getElementById("submissionsTableBody");
    const themeToggle = document.getElementById("themeToggle");
    
    // Edit Submission Modal
    const editSubmissionModal = document.getElementById("editSubmissionModal");
    const editSubmissionForm = document.getElementById("editSubmissionForm");
    const editSubmissionId = document.getElementById("editSubmissionId");
    const editSubmitterName = document.getElementById("editSubmitterName");
    const editSubmitterPhone = document.getElementById("editSubmitterPhone");
    const editMonth = document.getElementById("editMonth");
    const editYear = document.getElementById("editYear");
    const editGeneralChallenges = document.getElementById("editGeneralChallenges");
    const editAdditionalNotes = document.getElementById("editAdditionalNotes");
    const editTasksContainer = document.getElementById("editTasksContainer");
    const btnAddTask = document.getElementById("btnAddTask");
    const editErrorMsg = document.getElementById("editErrorMsg");
    const btnCloseEditModal = document.getElementById("btnCloseEditModal");
    const btnCancelEdit = document.getElementById("btnCancelEdit");

    // Process Progress
    const progressCard = document.getElementById("progressCard");
    const currentOffice = document.getElementById("currentOffice");
    const currentStage = document.getElementById("currentStage");
    const progressBarFill = document.getElementById("progressBarFill");
    const processedCount = document.getElementById("processedCount");
    const totalProcessCount = document.getElementById("totalProcessCount");
    const progressPercent = document.getElementById("progressPercent");
    const runningLogs = document.getElementById("runningLogs");
    const btnReset = document.getElementById("btnReset");
    
    // Reports Archive
    const reportSearch = document.getElementById("reportSearch");
    const reportsList = document.getElementById("reportsList");

    // Settings Panel
    const settingsForm = document.getElementById("settingsForm");
    const settingGeminiKey = document.getElementById("settingGeminiKey");
    const settingDriveFolder = document.getElementById("settingDriveFolder");
    const settingDefaultModel = document.getElementById("settingDefaultModel");
    const settingFallbackModel = document.getElementById("settingFallbackModel");
    const settingAdminUsername = document.getElementById("settingAdminUsername");
    const settingAdminPassword = document.getElementById("settingAdminPassword");

    // ─── App State ───────────────────────────────────────────────────────────
    let statusInterval = null;
    let localReports = [];
    let authenticated = false;

    // ─── Theme Controller ────────────────────────────────────────────────────
    const savedTheme = localStorage.getItem("theme") || "dark";
    if (savedTheme === "light") {
        document.body.classList.add("light-mode");
        themeToggle.querySelector("i").className = "fa-solid fa-sun";
    } else {
        document.body.classList.remove("light-mode");
        themeToggle.querySelector("i").className = "fa-solid fa-moon";
    }

    themeToggle.addEventListener("click", () => {
        document.body.classList.toggle("light-mode");
        const isLight = document.body.classList.contains("light-mode");
        themeToggle.querySelector("i").className = isLight ? "fa-solid fa-sun" : "fa-solid fa-moon";
        localStorage.setItem("theme", isLight ? "light" : "dark");
    });

    // ─── Auth state on initial load ──────────────────────────────────────────
    checkAuthSession();

    async function checkAuthSession() {
        try {
            const res = await fetch("/api/user/me");
            if (res.status === 401) {
                showLoginOverlay();
            } else if (res.ok) {
                const user = await res.json();
                authenticated = true;
                loggedInUser.textContent = user.username;
                hideLoginOverlay();
                initApp();
            } else {
                showLoginOverlay();
            }
        } catch (err) {
            console.error("Auth check failed:", err);
            showLoginOverlay();
        }
    }

    function showLoginOverlay() {
        authenticated = false;
        loginOverlay.classList.remove("hidden");
        appLayout.classList.add("hidden");
        if (statusInterval) {
            clearInterval(statusInterval);
            statusInterval = null;
        }
    }

    function hideLoginOverlay() {
        loginOverlay.classList.add("hidden");
        appLayout.classList.remove("hidden");
    }

    function initApp() {
        fetchOfficesFilter();
        fetchSubmissions();
        fetchReports();
        checkRunningStatusOnLoad();
    }

    // Handle Login API
    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        loginError.classList.add("hidden");
        loginError.textContent = "";

        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        try {
            const res = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });

            if (res.ok) {
                const data = await res.json();
                authenticated = true;
                loggedInUser.textContent = data.username;
                hideLoginOverlay();
                initApp();
                usernameInput.value = "";
                passwordInput.value = "";
            } else {
                const errData = await res.json();
                loginError.textContent = errData.detail || "فشل تسجيل الدخول. يرجى التحقق من المدخلات.";
                loginError.classList.remove("hidden");
            }
        } catch (err) {
            console.error("Login request error:", err);
            loginError.textContent = "خطأ في الاتصال بالخادم. يرجى المحاولة مجدداً.";
            loginError.classList.remove("hidden");
        }
    });

    // Handle Logout API
    btnLogout.addEventListener("click", async () => {
        if (!confirm("هل أنت متأكد من رغبتك في تسجيل الخروج؟")) return;
        try {
            await fetch("/api/logout", { method: "POST" });
            showLoginOverlay();
        } catch (err) {
            console.error("Logout failed:", err);
            showLoginOverlay();
        }
    });

    // Forgot Password modal handlers
    btnForgotPassword.addEventListener("click", () => {
        forgotPasswordModal.classList.remove("hidden");
    });
    btnCloseModal.addEventListener("click", () => {
        forgotPasswordModal.classList.add("hidden");
    });
    forgotPasswordModal.addEventListener("click", (e) => {
        if (e.target === forgotPasswordModal) {
            forgotPasswordModal.classList.add("hidden");
        }
    });

    // ─── API Wrapper helper that redirects to login on 401 ───────────────────
    async function apiFetch(url, options = {}) {
        try {
            const res = await fetch(url, options);
            if (res.status === 401) {
                showLoginOverlay();
                throw new Error("Session expired. Please login again.");
            }
            return res;
        } catch (err) {
            throw err;
        }
    }

    // ─── Sidebar Navigation SPA tab controller ────────────────────────────────
    navTabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.dataset.tab;
            
            navTabBtns.forEach(b => b.classList.remove("active"));
            tabPanes.forEach(p => p.classList.remove("active-pane"));
            
            btn.classList.add("active");
            document.getElementById(`tab${targetTab.charAt(0).toUpperCase() + targetTab.slice(1)}`).classList.add("active-pane");

            if (targetTab === "settings") {
                fetchSettings();
            } else if (targetTab === "reports") {
                fetchReports();
            } else if (targetTab === "dashboard") {
                fetchSubmissions();
            }
        });
    });

    // ─── Fetch Offices for Filter ─────────────────────────────────────────────
    async function fetchOfficesFilter() {
        try {
            const res = await apiFetch("/api/offices-list");
            const data = await res.json();
            
            // Clear and populate select
            officeFilter.innerHTML = '<option value="all">كل المكاتب</option>';
            if (data.offices && data.offices.length > 0) {
                data.offices.forEach(office => {
                    const option = document.createElement("option");
                    option.value = office.id;
                    option.textContent = office.name;
                    officeFilter.appendChild(option);
                });
            }
        } catch (err) {
            console.error("Failed to fetch offices list for filter:", err);
        }
    }

    // ─── Fetch Submissions with Filters ───────────────────────────────────────
    async function fetchSubmissions() {
        setConnectionStatus("connecting", "جاري تحميل التقارير...");
        try {
            let url = "/api/submissions";
            const params = [];
            
            if (officeFilter.value !== "all") {
                params.push(`office_id=${officeFilter.value}`);
            }
            if (monthFilter.value !== "all") {
                params.push(`month=${monthFilter.value}`);
            }
            if (statusFilter.value !== "all") {
                params.push(`status=${statusFilter.value}`);
            }
            
            if (params.length > 0) {
                url += "?" + params.join("&");
            }

            const res = await apiFetch(url);
            const data = await res.json();
            
            renderSubmissionsTable(data.submissions);
            setConnectionStatus("connected", "متصل بالخادم");
        } catch (err) {
            console.error("Failed to fetch submissions:", err);
            setConnectionStatus("error", "فشل جلب التقارير");
            submissionsTableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="list-placeholder text-danger">
                        <i class="fa-solid fa-triangle-exclamation" style="font-size: 20px; margin-bottom: 8px; display: block;"></i>
                        فشل الاتصال بالخادم لجلب قائمة التقارير.
                    </td>
                </tr>
            `;
        }
    }

    // ─── Format Date ─────────────────────────────────────────────────────────
    function formatDate(isoStr) {
        if (!isoStr) return "—";
        try {
            const date = new Date(isoStr);
            return date.toLocaleString("ar-SY", {
                dateStyle: "short",
                timeStyle: "short"
            });
        } catch (e) {
            return isoStr;
        }
    }

    // ─── Render Submissions Table ─────────────────────────────────────────────
    function renderSubmissionsTable(submissions) {
        if (!submissions || submissions.length === 0) {
            submissionsTableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="list-placeholder">لا توجد تقارير مطابقة للفلاتر المحددة حالياً.</td>
                </tr>
            `;
            return;
        }
        
        submissionsTableBody.innerHTML = "";
        submissions.forEach(sub => {
            const row = document.createElement("tr");
            
            // Status Badge
            let statusClass = "pending";
            let statusText = "قيد الانتظار";
            if (sub.status === "processed") {
                statusClass = "processed";
                statusText = "تمت المعالجة";
            } else if (sub.status === "failed") {
                statusClass = "failed";
                statusText = "فشلت المعالجة";
            }
            const statusBadge = `<span class="badge-status ${statusClass}">${statusText}</span>`;
            
            // Drive link column
            let driveLinkHtml = "—";
            if (sub.drive_report_link) {
                driveLinkHtml = `
                    <a href="${sub.drive_report_link}" target="_blank" class="btn-table-action" title="فتح بـ Drive" style="text-decoration: none;">
                        <i class="fa-brands fa-google-drive" style="color: var(--accent-color); font-size: 14px;"></i>
                    </a>
                `;
            }
            
            // Action Buttons: Retry | Edit | Delete
            const actionsHtml = `
                <div class="actions-cell">
                    <button class="btn-table-action retry" data-id="${sub.id}" title="إعادة معالجة (Retry)">
                        <i class="fa-solid fa-rotate"></i>
                    </button>
                    <button class="btn-table-action edit" data-id="${sub.id}" title="تعديل (Edit)">
                        <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                    <button class="btn-table-action delete" data-id="${sub.id}" title="حذف (Delete)">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            `;
            
            row.innerHTML = `
                <td><strong>${sub.office_name || "—"}</strong></td>
                <td>${sub.submitter_name || "—"}</td>
                <td>${sub.month}/${sub.year}</td>
                <td>${statusBadge}</td>
                <td>${formatDate(sub.created_at)}</td>
                <td style="text-align: center;">${driveLinkHtml}</td>
                <td>${actionsHtml}</td>
            `;
            
            submissionsTableBody.appendChild(row);
        });
        
        // Add Event Listeners for actions
        submissionsTableBody.querySelectorAll(".btn-table-action.retry").forEach(btn => {
            btn.addEventListener("click", () => handleRetry(parseInt(btn.dataset.id)));
        });
        submissionsTableBody.querySelectorAll(".btn-table-action.edit").forEach(btn => {
            btn.addEventListener("click", () => handleEdit(parseInt(btn.dataset.id)));
        });
        submissionsTableBody.querySelectorAll(".btn-table-action.delete").forEach(btn => {
            btn.addEventListener("click", () => handleDelete(parseInt(btn.dataset.id)));
        });
    }

    // ─── Action Handlers ──────────────────────────────────────────────────────
    async function handleRetry(submissionId) {
        progressCard.classList.remove("hidden");
        btnReset.classList.add("hidden");
        runningLogs.innerHTML = "";
        currentOffice.textContent = "—";
        currentStage.textContent = "جاري الاتصال بالخادم لبدء المعالجة...";
        progressBarFill.style.width = "0%";
        progressPercent.textContent = "0%";
        processedCount.textContent = "0";
        totalProcessCount.textContent = "1";
        
        appendLog("info", `جاري بدء معالجة التقرير رقم ${submissionId}...`);
        
        try {
            const res = await apiFetch("/api/process", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ submission_id: submissionId })
            });
            
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "فشل بدء معالجة التقرير.");
            }
            
            startPollingStatus();
        } catch (err) {
            console.error(err);
            appendLog("error", `خطأ أثناء بدء التشغيل: ${err.message}`);
        }
    }

    async function handleDelete(submissionId) {
        if (!confirm("هل أنت متأكد من حذف هذا التقرير؟ هذا الإجراء لا يمكن التراجع عنه وسيحذف الملف المرفق من السيرفر نهائياً.")) return;
        try {
            const res = await apiFetch(`/api/submissions/${submissionId}`, {
                method: "DELETE"
            });
            if (res.ok) {
                alert("تم حذف التقرير بنجاح.");
                fetchSubmissions();
            } else {
                const errData = await res.json();
                alert("فشل حذف التقرير: " + (errData.detail || "خطأ غير معروف"));
            }
        } catch (err) {
            console.error("Delete error:", err);
            alert("خطأ في الاتصال بالخادم لحذف التقرير.");
        }
    }

    async function handleEdit(submissionId) {
        try {
            const res = await apiFetch(`/api/submissions/${submissionId}`);
            if (!res.ok) {
                const errData = await res.json();
                alert("فشل جلب تفاصيل التقرير: " + (errData.detail || "خطأ غير معروف"));
                return;
            }
            const submission = await res.json();
            
            // Fill form fields
            editSubmissionId.value = submission.id;
            editSubmitterName.value = submission.submitter_name || "";
            editSubmitterPhone.value = submission.submitter_phone || "";
            editMonth.value = submission.month;
            editYear.value = submission.year;
            editGeneralChallenges.value = submission.general_challenges || "";
            editAdditionalNotes.value = submission.additional_notes || "";
            
            // Clear and fill tasks
            editTasksContainer.innerHTML = "";
            if (submission.tasks && submission.tasks.length > 0) {
                submission.tasks.forEach((task, idx) => {
                    addTaskCard(task, idx + 1);
                });
            } else {
                // Default empty task card if none
                addTaskCard({}, 1);
            }
            
            // Hide error msg
            editErrorMsg.classList.add("hidden");
            editErrorMsg.textContent = "";
            
            // Open modal
            editSubmissionModal.classList.remove("hidden");
        } catch (err) {
            console.error("Edit fetch error:", err);
            alert("خطأ في الاتصال بالخادم لجلب تفاصيل التقرير.");
        }
    }

    function addTaskCard(task = {}, number) {
        const card = document.createElement("div");
        card.className = "task-card-edit glass-card";
        card.style.cssText = "padding: 20px; position: relative; border: 1px solid var(--card-border); border-radius: 12px; background: rgba(255,255,255,0.01); display: flex; flex-direction: column; gap: 12px;";
        
        const taskNum = number || (editTasksContainer.children.length + 1);
        
        card.innerHTML = `
            <button type="button" class="btn-delete-task" style="position: absolute; top: 12px; left: 12px; background: none; border: none; color: #ff4d6d; cursor: pointer; font-size: 16px; transition: color 0.2s;" title="حذف المهمة">
                <i class="fa-solid fa-trash-can"></i>
            </button>
            <h5 class="task-number-title" style="margin: 0 0 4px 0; color: var(--accent-color); font-size: 13px; font-weight: 700;">المهمة #${taskNum}</h5>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
                <div class="form-group" style="margin-bottom: 0;">
                    <label>اسم المهمة <span style="color: #ff4d6d;">*</span>:</label>
                    <input type="text" class="form-control task-name-input" value="${task.task_name || ""}" required placeholder="أدخل اسم المهمة">
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                    <label>المسؤول عنها <span style="color: #ff4d6d;">*</span>:</label>
                    <input type="text" class="form-control task-manager-input" value="${task.manager_name || ""}" required placeholder="أدخل اسم المسؤول">
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                    <label>هاتف المسؤول:</label>
                    <input type="text" class="form-control task-phone-input" value="${task.manager_phone || ""}" placeholder="أدخل رقم الهاتف">
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
                <div class="form-group" style="margin-bottom: 0;">
                    <label>نوع المهمة:</label>
                    <select class="form-control task-type-select">
                        <option value="ضمن الخطة الشهرية" ${task.task_type === "ضمن الخطة الشهرية" ? "selected" : ""}>ضمن الخطة الشهرية</option>
                        <option value="خارج الخطة الشهرية" ${task.task_type === "خارج الخطة الشهرية" ? "selected" : ""}>خارج الخطة الشهرية</option>
                    </select>
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                    <label>حالة المهمة:</label>
                    <select class="form-control task-status-select">
                        <option value="مكتملة" ${task.task_status === "مكتملة" ? "selected" : ""}>مكتملة</option>
                        <option value="قيد التنفيذ" ${task.task_status === "قيد التنفيذ" ? "selected" : ""}>قيد التنفيذ</option>
                        <option value="ملغاة" ${task.task_status === "ملغاة" ? "selected" : ""}>ملغاة</option>
                    </select>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
                <div class="form-group" style="margin-bottom: 0;">
                    <label>الوصف التفصيلي:</label>
                    <textarea class="form-control task-desc-input" rows="2" placeholder="وصف موجز للمهمة">${task.task_description || ""}</textarea>
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                    <label>آلية التنفيذ:</label>
                    <textarea class="form-control task-mechanism-input" rows="2" placeholder="كيف تم أو سيتم التنفيذ">${task.execution_mechanism || ""}</textarea>
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                    <label>المشاكل/العقبات:</label>
                    <textarea class="form-control task-issues-input" rows="2" placeholder="أي صعوبات واجهت التنفيذ">${task.issues || ""}</textarea>
                </div>
            </div>
        `;
        
        // Handle delete task button click
        card.querySelector(".btn-delete-task").addEventListener("click", () => {
            card.remove();
            renumberTaskCards();
        });
        
        editTasksContainer.appendChild(card);
    }

    function renumberTaskCards() {
        Array.from(editTasksContainer.children).forEach((card, idx) => {
            card.querySelector(".task-number-title").textContent = `المهمة #${idx + 1}`;
        });
    }

    // Submit Edit Form Handler
    editSubmissionForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        editErrorMsg.classList.add("hidden");
        editErrorMsg.textContent = "";
        
        const id = editSubmissionId.value;
        const submitterName = editSubmitterName.value.trim();
        const submitterPhone = editSubmitterPhone.value.trim();
        const month = parseInt(editMonth.value);
        const year = parseInt(editYear.value);
        const generalChallenges = editGeneralChallenges.value.trim();
        const additionalNotes = editAdditionalNotes.value.trim();
        
        // Gather tasks
        const taskCards = editTasksContainer.children;
        if (taskCards.length === 0) {
            editErrorMsg.textContent = "يجب أن يحتوي التقرير على مهمة واحدة على الأقل.";
            editErrorMsg.classList.remove("hidden");
            return;
        }
        
        const tasks = [];
        for (let i = 0; i < taskCards.length; i++) {
            const card = taskCards[i];
            const taskName = card.querySelector(".task-name-input").value.trim();
            const managerName = card.querySelector(".task-manager-input").value.trim();
            const managerPhone = card.querySelector(".task-phone-input").value.trim();
            const taskType = card.querySelector(".task-type-select").value;
            const taskStatus = card.querySelector(".task-status-select").value;
            const taskDescription = card.querySelector(".task-desc-input").value.trim();
            const executionMechanism = card.querySelector(".task-mechanism-input").value.trim();
            const issues = card.querySelector(".task-issues-input").value.trim();
            
            if (!taskName || !managerName) {
                editErrorMsg.textContent = `يرجى ملء الحقول المطلوبة (اسم المهمة والمسؤول عنها) للمهمة #${i + 1}.`;
                editErrorMsg.classList.remove("hidden");
                return;
            }
            
            tasks.push({
                manager_name: managerName,
                manager_phone: managerPhone || null,
                task_name: taskName,
                task_description: taskDescription || null,
                task_type: taskType,
                execution_mechanism: executionMechanism || null,
                task_status: taskStatus,
                issues: issues || null
            });
        }
        
        // Build payload
        const payload = {
            submitter_name: submitterName,
            submitter_phone: submitterPhone || null,
            month: month,
            year: year,
            general_challenges: generalChallenges || null,
            additional_notes: additionalNotes || null,
            tasks: tasks
        };
        
        try {
            const res = await apiFetch(`/api/submissions/${id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            
            if (res.ok) {
                alert("تم تحديث التقرير بنجاح!");
                editSubmissionModal.classList.add("hidden");
                fetchSubmissions();
            } else {
                const errData = await res.json();
                editErrorMsg.textContent = errData.detail || "فشل تحديث التقرير.";
                editErrorMsg.classList.remove("hidden");
            }
        } catch (err) {
            console.error("Patch submission error:", err);
            editErrorMsg.textContent = "خطأ في الاتصال بالخادم لحفظ التعديلات.";
            editErrorMsg.classList.remove("hidden");
        }
    });

    // Close Modals
    btnCloseEditModal.addEventListener("click", () => {
        editSubmissionModal.classList.add("hidden");
    });
    btnCancelEdit.addEventListener("click", () => {
        editSubmissionModal.classList.add("hidden");
    });
    editSubmissionModal.addEventListener("click", (e) => {
        if (e.target === editSubmissionModal) {
            editSubmissionModal.classList.add("hidden");
        }
    });
    btnAddTask.addEventListener("click", () => {
        addTaskCard({}, editTasksContainer.children.length + 1);
    });

    // Filter change listeners
    officeFilter.addEventListener("change", fetchSubmissions);
    monthFilter.addEventListener("change", fetchSubmissions);
    statusFilter.addEventListener("change", fetchSubmissions);
    
    reportSearch.addEventListener("input", filterReports);
    btnReset.addEventListener("click", resetPipeline);

    // ─── Fetch Reports List ──────────────────────────────────────────────────
    async function fetchReports() {
        try {
            const res = await apiFetch("/api/reports");
            const data = await res.json();
            localReports = data.reports;
            renderReports(localReports);
        } catch (err) {
            console.error(err);
            reportsList.innerHTML = `<div class="list-placeholder text-danger">فشل تحميل قائمة التقارير.</div>`;
        }
    }

    // ─── Check Running Status on Load ────────────────────────────────────────
    async function checkRunningStatusOnLoad() {
        try {
            const res = await apiFetch("/api/status");
            const state = await res.json();
            if (state.status === "running") {
                progressCard.classList.remove("hidden");
                startPollingStatus();
            }
        } catch (err) {
            console.error(err);
        }
    }

    // ─── UI Rendering Helpers ────────────────────────────────────────────────
    function setConnectionStatus(type, text) {
        const dot = systemStatus.querySelector(".status-dot");
        const txt = systemStatus.querySelector(".status-text");
        
        dot.className = "status-dot";
        txt.textContent = text;
        
        if (type === "connected") {
            dot.classList.add("green", "animate-pulse");
        } else if (type === "connecting") {
            dot.classList.add("yellow", "animate-pulse");
        } else {
            dot.classList.add("red");
        }
    }

    // ─── Polling Status ──────────────────────────────────────────────────────
    function startPollingStatus() {
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(fetchStatus, 1000);
    }

    async function fetchStatus() {
        try {
            const res = await apiFetch("/api/status");
            const state = await res.json();
            
            currentOffice.textContent = state.current_office || "—";
            currentStage.textContent = state.current_stage || "—";
            progressBarFill.style.width = `${state.progress}%`;
            progressPercent.textContent = `${state.progress}%`;
            processedCount.textContent = state.processed_offices;
            totalProcessCount.textContent = state.total_offices;
            
            renderStateLogs(state.results, state.status, state.current_office, state.current_stage);

            if (state.status === "completed" || state.status === "failed") {
                clearInterval(statusInterval);
                statusInterval = null;
                btnReset.classList.remove("hidden");
                fetchReports();
                fetchSubmissions();
            }
        } catch (err) {
            console.error("Status polling error:", err);
        }
    }

    let lastLoggedResultsCount = 0;
    let lastOfficeLogged = "";
    let lastStageLogged = "";

    function renderStateLogs(results, status, curOffice, curStage) {
        if (curOffice && curOffice !== lastOfficeLogged) {
            appendLog("info", `🟢 جاري بدء معالجة: ${curOffice}`);
            lastOfficeLogged = curOffice;
            lastStageLogged = "";
        }
        if (curStage && curStage !== lastStageLogged) {
            appendLog("info", `   ↳ ${curStage}`);
            lastStageLogged = curStage;
        }

        if (results.length > lastLoggedResultsCount) {
            for (let i = lastLoggedResultsCount; i < results.length; i++) {
                const res = results[i];
                if (res.status === "Success") {
                    appendLog("success", `✅ تم إنجاز مكتب (${res.office}) بنجاح! التقرير: ${res.report_name}`);
                } else {
                    appendLog("error", `❌ فشل مكتب (${res.office}): ${res.details}`);
                }
            }
            lastLoggedResultsCount = results.length;
        }

        if (status === "completed" && lastStageLogged !== "COMPLETED") {
            appendLog("success", `🎉 اكتملت المهمة بالكامل! تم إنتاج جميع التقارير بنجاح.`);
            lastStageLogged = "COMPLETED";
            lastLoggedResultsCount = 0;
            lastOfficeLogged = "";
        }
    }

    function appendLog(type, message) {
        const entry = document.createElement("div");
        entry.className = `log-entry ${type}`;
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        runningLogs.appendChild(entry);
        runningLogs.scrollTop = runningLogs.scrollHeight;
    }

    async function resetPipeline() {
        try {
            await apiFetch("/api/reset", { method: "POST" });
            
            progressCard.classList.add("hidden");
            btnReset.classList.add("hidden");
            
            lastLoggedResultsCount = 0;
            lastOfficeLogged = "";
            lastStageLogged = "";
        } catch (err) {
            console.error(err);
            alert("فشل إعادة تعيين الخادم: " + err.message);
        }
    }

    async function downloadReport(filename, btnElement) {
        try {
            btnElement.style.pointerEvents = "none";
            btnElement.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i>`;
            const res = await apiFetch(`/api/download/${encodeURIComponent(filename)}`);
            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            }
        } catch (err) {
            console.error("Download failed:", err);
        } finally {
            btnElement.style.pointerEvents = "";
            btnElement.innerHTML = `<i class="fa-solid fa-download"></i>`;
        }
    }

    function renderReports(reports) {
        if (reports.length === 0) {
            reportsList.innerHTML = `<div class="list-placeholder">لا توجد تقارير منشأة حالياً.</div>`;
            return;
        }
        
        reportsList.innerHTML = "";
        reports.forEach(report => {
            const dateStr = new Date(report.created_at * 1000).toLocaleString("ar-SY", {
                dateStyle: "short",
                timeStyle: "short"
            });
            const item = document.createElement("div");
            item.className = "report-item";
            item.innerHTML = `
                <div class="report-info">
                    <span class="report-name" title="${report.name}">${report.name}</span>
                    <span class="report-meta">${report.size_kb} KB | ${dateStr}</span>
                </div>
                <div class="report-actions">
                    <button class="btn-icon btn-download-report" data-filename="${report.name}" title="تحميل التقرير">
                        <i class="fa-solid fa-download"></i>
                    </button>
                </div>
            `;
            reportsList.appendChild(item);
        });

        reportsList.querySelectorAll(".btn-download-report").forEach(btn => {
            btn.addEventListener("click", () => {
                downloadReport(btn.dataset.filename, btn);
            });
        });
    }

    // Filter Local Reports
    function filterReports() {
        const query = reportSearch.value.toLowerCase().trim();
        const items = reportsList.querySelectorAll(".report-item");
        
        items.forEach(item => {
            const name = item.querySelector(".report-name").textContent.toLowerCase();
            if (name.includes(query)) {
                item.style.display = "flex";
            } else {
                item.style.display = "none";
            }
        });
    }

    // ─── Settings API Operations ─────────────────────────────────────────────
    async function fetchSettings() {
        try {
            const res = await apiFetch("/api/settings");
            const data = await res.json();
            
            settingGeminiKey.value = data.gemini_api_key || "";
            settingDriveFolder.value = data.drive_system_folder || "";
            settingDefaultModel.value = data.default_model || "";
            settingFallbackModel.value = data.fallback_model || "";
            settingAdminUsername.value = data.admin_username || "";
            settingAdminPassword.value = ""; // Clear password input mask
        } catch (err) {
            console.error("Failed to load settings:", err);
            alert("حدث خطأ أثناء تحميل الإعدادات من الخادم.");
        }
    }

    settingsForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const payload = {
            drive_system_folder: settingDriveFolder.value.trim(),
            default_model: settingDefaultModel.value.trim(),
            fallback_model: settingFallbackModel.value.trim(),
            admin_username: settingAdminUsername.value.trim()
        };

        // If key is not masked representation, include it
        const keyVal = settingGeminiKey.value.trim();
        if (keyVal === "" || (keyVal && !keyVal.includes("...") && !keyVal.includes("*"))) {
            payload.gemini_api_key = keyVal;
        }

        // If password is changed, include it
        const passVal = settingAdminPassword.value;
        if (passVal && passVal !== "********") {
            payload.admin_password = passVal;
        }

        try {
            const res = await apiFetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                alert("تم حفظ وتحديث الإعدادات بنجاح!");
                fetchSettings();
            } else {
                const errData = await res.json();
                alert("فشل حفظ الإعدادات: " + (errData.detail || "خطأ غير معروف"));
            }
        } catch (err) {
            console.error("Settings save error:", err);
            alert("خطأ في الاتصال بالخادم لحفظ الإعدادات.");
        }
    });
});
