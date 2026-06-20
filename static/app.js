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

    // Dashboard
    const systemStatus = document.getElementById("systemStatus");
    const monthSelect = document.getElementById("monthSelect");
    const btnStart = document.getElementById("btnStart");
    const selectedCountSpan = document.getElementById("selectedCount");
    const btnSelectAll = document.getElementById("btnSelectAll");
    const btnDeselectAll = document.getElementById("btnDeselectAll");
    const officeSearch = document.getElementById("officeSearch");
    const monthFilterDropdown = document.getElementById("monthFilterDropdown");
    const colMapSummary = document.getElementById("colMapSummary");
    const officeGrid = document.getElementById("officeGrid");
    const themeToggle = document.getElementById("themeToggle");
    
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
    const settingSpreadsheetName = document.getElementById("settingSpreadsheetName");
    const settingDriveFolder = document.getElementById("settingDriveFolder");
    const settingDefaultModel = document.getElementById("settingDefaultModel");
    const settingFallbackModel = document.getElementById("settingFallbackModel");
    const settingAdminUsername = document.getElementById("settingAdminUsername");
    const settingAdminPassword = document.getElementById("settingAdminPassword");

    // ─── App State ───────────────────────────────────────────────────────────
    let allOffices = [];
    let selectedOffices = new Set();
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
        fetchOffices();
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
                fetchOffices();
            }
        });
    });

    // ─── Fetch Offices & Month List Extraction ────────────────────────────────
    function parseDate(dateStr) {
        if (!dateStr || dateStr === "—") return new Date(0);
        try {
            dateStr = dateStr.trim();
            const parts = dateStr.split(" ");
            const dateParts = parts[0].split(dateStr.includes("/") ? "/" : "-");
            const timeParts = parts[1] ? parts[1].split(":") : [0, 0];
            
            if (dateStr.includes("/")) {
                const day = parseInt(dateParts[0]);
                const month = parseInt(dateParts[1]) - 1;
                const year = parseInt(dateParts[2]);
                const hour = parseInt(timeParts[0]);
                const min = parseInt(timeParts[1]);
                return new Date(year, month, day, hour, min);
            } else {
                const year = parseInt(dateParts[0]);
                const month = parseInt(dateParts[1]) - 1;
                const day = parseInt(dateParts[2]);
                const hour = parseInt(timeParts[0]);
                const min = parseInt(timeParts[1]);
                return new Date(year, month, day, hour, min);
            }
        } catch (e) {
            console.error("Error parsing date: " + dateStr, e);
            return new Date(0);
        }
    }

    async function fetchOffices() {
        setConnectionStatus("connecting", "جاري الاتصال بالجدول...");
        try {
            const res = await apiFetch("/api/offices");
            const data = await res.json();
            allOffices = data.offices;
            
            // Sort offices descending by timestamp (newest first)
            allOffices.sort((a, b) => parseDate(b.timestamp) - parseDate(a.timestamp));
            
            // Build dynamic Month Filter Options based on office target months
            populateMonthFilterDropdown();

            // Render Column discovery
            renderColumnMapSummary(data.column_map);
            
            // Render offices
            renderOffices(allOffices);
            setConnectionStatus("connected", "متصل بالجدول");
        } catch (err) {
            console.error(err);
            setConnectionStatus("error", "فشل جلب المكاتب");
            officeGrid.innerHTML = `
                <div class="list-placeholder" style="grid-column: 1 / -1; color: #ff4d6d;">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 24px; margin-bottom: 8px;"></i>
                    <p>فشل الاتصال بخادم البيانات. يرجى التحقق من اسم ملف الـ Spreadsheet ومفاتيح الربط في الإعدادات.</p>
                </div>
            `;
        }
    }

    // Dynamic month selection list extraction
    function populateMonthFilterDropdown() {
        // Collect unique month keys
        const monthKeys = new Set();
        const monthsList = [];

        allOffices.forEach(office => {
            if (office.target_month_name && office.timestamp) {
                const yearDate = parseDate(office.timestamp);
                const year = yearDate.getFullYear() !== 1970 ? yearDate.getFullYear() : new Date().getFullYear();
                const displayMonth = `${office.target_month_name} ${year}`;
                if (!monthKeys.has(displayMonth)) {
                    monthKeys.add(displayMonth);
                    monthsList.push({
                        text: displayMonth,
                        monthName: office.target_month_name,
                        year: year
                    });
                }
            }
        });

        // Store selected value to preserve it if reloading
        const previousSelection = monthFilterDropdown.value;

        // Reset dropdown except first
        monthFilterDropdown.innerHTML = '<option value="all">جميع الأشهر</option>';
        monthsList.forEach(m => {
            const option = document.createElement("option");
            option.value = m.text;
            option.textContent = m.text;
            monthFilterDropdown.appendChild(option);
        });

        // Restore previous selection if still exists
        if (monthKeys.has(previousSelection)) {
            monthFilterDropdown.value = previousSelection;
        }
    }

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
                btnStart.disabled = true;
                monthSelect.disabled = true;
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

    function renderColumnMapSummary(colMap) {
        if (!colMap) return;
        const taskCount = colMap.tasks ? colMap.tasks.length : 0;
        colMapSummary.innerHTML = `
            اسم المكتب (العمود ${colMap.office_name}) | 
            مقدم التقرير (العمود ${colMap.submitter}) | 
            تم اكتشاف <strong>${taskCount} مهام</strong> ديناميكياً.
        `;
    }

    function renderOffices(offices) {
        if (offices.length === 0) {
            officeGrid.innerHTML = `<div class="list-placeholder" style="grid-column: 1 / -1;">الجدول لا يحتوي على أي صفوف مكاتب حالياً.</div>`;
            return;
        }
        
        // Calculate duplicate submissions based on name + target_month_name
        const counts = {};
        offices.forEach(office => {
            const key = `${office.name.trim()}_${(office.target_month_name || "").trim()}`;
            counts[key] = (counts[key] || 0) + 1;
        });
        const seen = {};
        
        officeGrid.innerHTML = "";
        offices.forEach(office => {
            const card = document.createElement("div");
            card.className = "office-card";
            card.dataset.id = office.id;
            
            // Preserve selection
            if (selectedOffices.has(office.id)) {
                card.classList.add("selected");
            }
            
            const badgeMonth = office.target_month_name ? `<span class="badge-month">${office.target_month_name}</span>` : "";
            const submitterText = office.submitter ? `<div class="office-meta-item"><i class="fa-solid fa-user"></i> مقدم التقرير: ${office.submitter}</div>` : "";
            
            // Build duplicate badge if applicable
            let duplicateBadge = "";
            const dupKey = `${office.name.trim()}_${(office.target_month_name || "").trim()}`;
            if (counts[dupKey] > 1) {
                if (!seen[dupKey]) {
                    seen[dupKey] = true;
                    duplicateBadge = `<span class="badge-duplicate latest"><i class="fa-solid fa-clock-rotate-left"></i> أحدث إرسال</span>`;
                } else {
                    duplicateBadge = `<span class="badge-duplicate older"><i class="fa-solid fa-triangle-exclamation"></i> نسخة سابقة (مكررة)</span>`;
                }
            }

            card.innerHTML = `
                <div class="checkbox-custom">
                    <i class="fa-solid fa-check"></i>
                </div>
                <div class="office-card-content">
                    <span class="office-card-name">${office.name}</span>
                    <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                        ${badgeMonth}
                        ${duplicateBadge}
                    </div>
                    <div class="office-card-meta">
                        ${submitterText}
                        <div class="office-meta-item"><i class="fa-regular fa-calendar-days"></i> تاريخ رفع التقرير: ${office.timestamp}</div>
                    </div>
                </div>
            `;
            
            card.addEventListener("click", () => toggleOfficeSelection(office.id, card));
            officeGrid.appendChild(card);
        });
        
        applyFilters(); // Apply search & filter immediately on render
    }

    function toggleOfficeSelection(id, cardElement) {
        if (selectedOffices.has(id)) {
            selectedOffices.delete(id);
            cardElement.classList.remove("selected");
        } else {
            selectedOffices.add(id);
            cardElement.classList.add("selected");
        }
        updateStartButtonState();
    }

    function updateStartButtonState() {
        btnStart.disabled = selectedOffices.size === 0;
        selectedCountSpan.textContent = selectedOffices.size;
    }

    function selectAllOffices() {
        // Select only visible cards
        const visibleCards = officeGrid.querySelectorAll(".office-card");
        visibleCards.forEach(card => {
            if (card.style.display !== "none") {
                const id = parseInt(card.dataset.id);
                selectedOffices.add(id);
                card.classList.add("selected");
            }
        });
        updateStartButtonState();
    }

    function deselectAllOffices() {
        // Deselect only visible cards
        const visibleCards = officeGrid.querySelectorAll(".office-card");
        visibleCards.forEach(card => {
            if (card.style.display !== "none") {
                const id = parseInt(card.dataset.id);
                selectedOffices.delete(id);
                card.classList.remove("selected");
            }
        });
        updateStartButtonState();
    }

    // Search and Dropdown Filter synchronization
    function applyFilters() {
        const query = officeSearch.value.toLowerCase().trim();
        const selectedMonth = monthFilterDropdown.value; // e.g. "حزيران 2026" or "all"

        const cards = officeGrid.querySelectorAll(".office-card");
        
        cards.forEach(card => {
            const officeId = parseInt(card.dataset.id);
            const office = allOffices.find(o => o.id === officeId);
            if (!office) return;

            const name = office.name.toLowerCase();
            const submitter = (office.submitter || "").toLowerCase();
            const yearDate = parseDate(office.timestamp);
            const tsYear = yearDate.getFullYear() !== 1970 ? yearDate.getFullYear() : new Date().getFullYear();
            const officeMonth = office.target_month_name ? `${office.target_month_name} ${tsYear}` : "";
            
            // Check keyword match
            const matchesKeyword = name.includes(query) || submitter.includes(query);
            
            // Check month dropdown match
            const matchesMonth = (selectedMonth === "all") || (officeMonth === selectedMonth);

            if (matchesKeyword && matchesMonth) {
                card.style.display = "flex";
            } else {
                card.style.display = "none";
            }
        });
    }

    officeSearch.addEventListener("input", applyFilters);
    monthFilterDropdown.addEventListener("change", applyFilters);
    btnSelectAll.addEventListener("click", selectAllOffices);
    btnDeselectAll.addEventListener("click", deselectAllOffices);
    reportSearch.addEventListener("input", filterReports);
    btnStart.addEventListener("click", startProcessing);
    btnReset.addEventListener("click", resetPipeline);

    // ─── Process Pipeline Operations ──────────────────────────────────────────
    async function startProcessing() {
        if (selectedOffices.size === 0) return;
        
        btnStart.disabled = true;
        monthSelect.disabled = true;
        progressCard.classList.remove("hidden");
        btnReset.classList.add("hidden");
        runningLogs.innerHTML = "";
        
        const selectedRows = allOffices
            .filter(off => selectedOffices.has(off.id))
            .map(off => off.raw_row);
            
        const monthNum = parseInt(monthSelect.value);
        const monthName = monthSelect.options[monthSelect.selectedIndex].text.split(" ")[0];
        
        appendLog("info", `جاري بدء معالجة عدد ${selectedRows.length} مكاتب لشهر ${monthName}...`);
        
        try {
            const res = await apiFetch("/api/process", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    selected_rows: selectedRows,
                    target_month_num: monthNum,
                    target_month_name: monthName
                })
            });
            
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Failed to start pipeline processing");
            }
            
            startPollingStatus();
        } catch (err) {
            console.error(err);
            appendLog("error", `خطأ أثناء بدء التشغيل: ${err.message}`);
            btnStart.disabled = false;
            monthSelect.disabled = false;
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
            btnStart.disabled = selectedOffices.size === 0;
            monthSelect.disabled = false;
            
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
            settingSpreadsheetName.value = data.spreadsheet_name || "";
            settingDriveFolder.value = data.drive_system_folder || "";
            settingDefaultModel.value = data.default_model || "";
            settingFallbackModel.value = data.fallback_model || "";
            settingAdminUsername.value = data.admin_username || "";
            settingAdminPassword.value = data.admin_password || "";
        } catch (err) {
            console.error("Failed to load settings:", err);
            alert("حدث خطأ أثناء تحميل الإعدادات من الخادم.");
        }
    }

    settingsForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const payload = {
            spreadsheet_name: settingSpreadsheetName.value.trim(),
            drive_system_folder: settingDriveFolder.value.trim(),
            default_model: settingDefaultModel.value.trim(),
            fallback_model: settingFallbackModel.value.trim(),
            admin_username: settingAdminUsername.value.trim()
        };

        // If key is not masked representation, include it (or include empty string if cleared)
        const keyVal = settingGeminiKey.value.trim();
        if (keyVal === "" || (keyVal && !keyVal.includes("...") && !keyVal.includes("*"))) {
            payload.gemini_api_key = keyVal;
        }

        // If password is changed from asterisk mask, include it
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
                alert("تم حفظ وتحديث الإعدادات في settings.yaml والذاكرة بنجاح!");
                fetchSettings(); // reload to get new masks
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
