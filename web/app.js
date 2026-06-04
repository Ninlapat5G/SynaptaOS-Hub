// app.js

// คอนฟิกูเรชันและสถานะของแอปพลิเคชัน
const state = {
    token: localStorage.getItem("admin_token") || "",
    currentTab: "tab-users",
    currentUser: null,
    currentPart: "profile",
    users: {},
    tools: []
};

// การตรวจหาองค์ประกอบของ UI
const DOM = {
    tabs: document.querySelectorAll(".tab-btn"),
    tabContents: document.querySelectorAll(".tab-content"),
    loginModal: document.getElementById("login-modal"),
    loginForm: document.getElementById("login-form"),
    tokenInput: document.getElementById("admin-token-input"),
    loginError: document.getElementById("login-error"),
    btnLogout: document.getElementById("btn-logout"),
    
    // แท็บผู้ใช้งาน (Users)
    usersContainer: document.getElementById("users-container"),
    userDetailPanel: document.getElementById("user-detail-panel"),
    userEmptyPanel: document.getElementById("user-empty-panel"),
    currentUserTitle: document.getElementById("current-user-title"),
    currentUserSubtitle: document.getElementById("current-user-subtitle"),
    partBtns: document.querySelectorAll(".part-tab-btn"),
    uiViewPanel: document.getElementById("ui-view-panel"),
    editorFilenameLabel: document.getElementById("editor-filename-label"),
    btnRefreshUsers: document.getElementById("btn-refresh-users"),

    // แท็บเอเจนต์ (Agent)
    agentUserSelect: document.getElementById("agent-user-select"),
    chatMessagesBox: document.getElementById("chat-messages-box"),
    agentForm: document.getElementById("agent-form"),
    agentInputField: document.getElementById("agent-input-field"),
    agentThinkingLoader: document.getElementById("agent-thinking-loader"),

    // แท็บระบบหลังบ้าน (System)
    systemInfoText: document.getElementById("system-info-text"),
    toolsContainer: document.getElementById("tools-container"),

    // แท็บตั้งค่าความปลอดภัย (Settings)
    settingsForm: document.getElementById("settings-form"),
    settingsOldToken: document.getElementById("settings-old-token"),
    settingsNewAdminToken: document.getElementById("settings-new-admin-token"),
    settingsNewMcpToken: document.getElementById("settings-new-mcp-token"),
    settingsError: document.getElementById("settings-error"),
    settingsSuccess: document.getElementById("settings-success")
};

// ── ระบบการสลับแท็บเมนูหลัก ──────────────────────────────────────────────────
DOM.tabs.forEach(btn => {
    btn.addEventListener("click", () => {
        const tabId = btn.getAttribute("data-tab");
        switchTab(tabId);
    });
});

function switchTab(tabId) {
    state.currentTab = tabId;
    DOM.tabs.forEach(b => {
        if (b.getAttribute("data-tab") === tabId) {
            b.classList.add("active");
        } else {
            b.classList.remove("active");
        }
    });

    DOM.tabContents.forEach(content => {
        if (content.id === tabId) {
            content.classList.add("active");
        } else {
            content.classList.remove("active");
        }
    });

    // โหลดข้อมูลสำหรับแต่ละแท็บ
    if (tabId === "tab-users") {
        loadUsers();
    } else if (tabId === "tab-agent") {
        updateAgentUserDropdown();
    } else if (tabId === "tab-system") {
        loadSystemInfo();
    } else if (tabId === "tab-settings") {
        loadSettingsInfo();
    }
}

// ── การตรวจหาและส่งข้อมูลผ่าน API (Fetch Wrapper) ──────────────────────────
async function fetchAPI(url, options = {}) {
    options.headers = options.headers || {};
    if (state.token) {
        options.headers["Authorization"] = `Bearer ${state.token}`;
    }
    
    try {
        const response = await fetch(url, options);
        
        if (response.status === 401) {
            showLoginModal();
            throw new Error("unauthorized");
        }
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || `HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (err) {
        if (err.message !== "unauthorized") {
            console.error("API Call failed:", err);
        }
        throw err;
    }
}

// ── ระบบตรวจสอบสิทธิ์ (Authentication) ──────────────────────────────────────
function showLoginModal() {
    DOM.loginModal.style.display = "flex";
    DOM.loginError.style.display = "none";
}

function hideLoginModal() {
    DOM.loginModal.style.display = "none";
    if (state.token) {
        DOM.btnLogout.style.display = "block";
    } else {
        DOM.btnLogout.style.display = "none";
    }
    connectWebSocket();
}

DOM.loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const token = DOM.tokenInput.value.trim();
    state.token = token;
    
    try {
        // ทดสอบดึงผู้ใช้งานเพื่อทดสอบว่าโทเค็นถูกต้องไหม
        await fetchAPI("/admin/api/users");
        localStorage.setItem("admin_token", token);
        hideLoginModal();
        switchTab(state.currentTab);
    } catch (err) {
        DOM.loginError.style.display = "block";
        state.token = "";
        localStorage.removeItem("admin_token");
    }
});

DOM.btnLogout.addEventListener("click", () => {
    state.token = "";
    localStorage.removeItem("admin_token");
    DOM.btnLogout.style.display = "none";
    if (ws) {
        try { ws.close(); } catch(e) {}
        ws = null;
    }
    showLoginModal();
});

// ── แท็บที่ 1: การจัดการผู้ใช้ (Users Tab) ───────────────────────────────────
DOM.btnRefreshUsers.addEventListener("click", loadUsers);

async function loadUsers() {
    DOM.usersContainer.innerHTML = '<div class="loading-spinner">กำลังดึงข้อมูลรายชื่อ...</div>';
    try {
        const users = await fetchAPI("/admin/api/users");
        state.users = users;
        renderUsersList();
    } catch (err) {
        if (err.message !== "unauthorized") {
            DOM.usersContainer.innerHTML = `<div class="loading-spinner" style="color:var(--danger-color)">ดึงข้อมูลล้มเหลว: ${err.message}</div>`;
        }
    }
}

function renderUsersList() {
    const userIds = Object.keys(state.users);
    if (userIds.length === 0) {
        DOM.usersContainer.innerHTML = '<div class="loading-spinner">ไม่พบรายชื่อผู้ใช้งานในระบบ</div>';
        return;
    }

    DOM.usersContainer.innerHTML = "";
    userIds.forEach(uid => {
        const user = state.users[uid];
        const lastSeenDate = user.last_seen ? new Date(user.last_seen * 1000).toLocaleString("th-TH") : "ไม่ทราบข้อมูล";
        
        const item = document.createElement("div");
        item.className = "user-item";
        if (state.currentUser === uid) {
            item.classList.add("active");
        }
        
        item.innerHTML = `
            <div class="user-item-name">${uid}</div>
            <div class="user-item-detail">${user.app_name || "แอปนิรนาม"} • ล่าสุด: ${lastSeenDate}</div>
        `;
        
        item.addEventListener("click", () => {
            selectUser(uid);
        });
        
        DOM.usersContainer.appendChild(item);
    });
}

function selectUser(uid) {
    state.currentUser = uid;
    
    // อัปเดตการเลือกคลาส active บนรายการ
    document.querySelectorAll(".user-item").forEach(item => {
        const name = item.querySelector(".user-item-name").innerText;
        if (name === uid) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });

    const user = state.users[uid];
    DOM.currentUserTitle.innerText = `รหัสผู้ใช้งาน: ${uid}`;
    DOM.currentUserSubtitle.innerText = `ชื่อแอปพลิเคชัน: ${user.app_name || "ไม่มี"} | เชื่อมต่อล่าสุด: ${user.last_seen ? new Date(user.last_seen * 1000).toLocaleString("th-TH") : "ไม่มี"}`;
    
    DOM.userEmptyPanel.style.display = "none";
    DOM.userDetailPanel.style.display = "flex";
    
    // ไปยังส่วนข้อมูลย่อยที่เลือกอยู่
    selectPart(state.currentPart);
}

// การเลือกแท็บข้อมูลส่วนต่าง ๆ (Profile, KD, Scenes, Routines, Phone)
DOM.partBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        const part = btn.getAttribute("data-part");
        selectPart(part);
    });
});

function selectPart(part) {
    state.currentPart = part;
    DOM.partBtns.forEach(b => {
        if (b.getAttribute("data-part") === part) {
            b.classList.add("active");
        } else {
            b.classList.remove("active");
        }
    });

    const labels = {
        profile: "ข้อมูลส่วนตัว (Profile)",
        kd: "รายการอุปกรณ์ควบคุม (Devices)",
        scenes: "สภาพแวดล้อมที่ตั้งไว้ (Scenes)",
        routines: "กฎอัตโนมัติ (Routines)",
        phone: "สถานะโทรศัพท์มือถือ (Phone)"
    };
    DOM.editorFilenameLabel.innerText = labels[part] || part;
    loadUserPart();
}

async function loadUserPart() {
    if (!state.currentUser) return;
    DOM.uiViewPanel.innerHTML = '<div class="loading-spinner">กำลังดึงข้อมูล...</div>';
    
    try {
        const data = await fetchAPI(`/admin/api/users/${state.currentUser}/${state.currentPart}`);
        renderPartUI(state.currentPart, data);
    } catch (err) {
        if (err.message !== "unauthorized") {
            DOM.uiViewPanel.innerHTML = `<div class="loading-spinner" style="color:var(--danger-color)">เกิดข้อผิดพลาดในการโหลดข้อมูล: ${err.message}</div>`;
        }
    }
}

function renderPartUI(part, data) {
    if (!data) {
        DOM.uiViewPanel.innerHTML = '<div class="loading-spinner">ไม่มีข้อมูลสำหรับส่วนนี้</div>';
        return;
    }

    let html = "";
    if (part === "profile") {
        const displayName = data.displayName || "(ยังไม่ได้ซิงก์ / ไม่มีชื่อ)";
        const assistantName = data.assistantName || "(ยังไม่ได้ซิงก์ / ไม่มีชื่อ)";
        const userBio = data.userBio || "(ไม่มีข้อมูล)";
        const userMemory = data.userMemory || "(ไม่มีข้อมูล)";
        const systemPrompt = data.systemPrompt || "(ไม่มีข้อมูล)";
        const registeredAt = data.registered_at ? new Date(data.registered_at * 1000).toLocaleString("th-TH") : "ไม่ทราบ";

        html = `
            <div class="profile-card">
                <div class="profile-field">
                    <div class="profile-label">ชื่อผู้ใช้งาน (Display Name)</div>
                    <div class="profile-value">${displayName}</div>
                </div>
                <div class="profile-field">
                    <div class="profile-label">ชื่อบอทผู้ช่วย (Assistant Name)</div>
                    <div class="profile-value">${assistantName}</div>
                </div>
                <div class="profile-field">
                    <div class="profile-label">ข้อมูลเกี่ยวกับผู้ใช้ (Bio)</div>
                    <div class="profile-value">${userBio}</div>
                </div>
                <div class="profile-field">
                    <div class="profile-label">ความจำระยะยาวของบอท (Long-term Memory)</div>
                    <div class="profile-value">${userMemory}</div>
                </div>
                <div class="profile-field">
                    <div class="profile-label">System Prompt ของบอทส่วนบุคคล</div>
                    <div class="profile-value" style="font-family: monospace; font-size: 13.5px;">${systemPrompt}</div>
                </div>
                <div class="profile-field">
                    <div class="profile-label">ลงทะเบียนเมื่อ (Registered At)</div>
                    <div class="profile-value">${registeredAt}</div>
                </div>
            </div>
        `;
    } else if (part === "kd") {
        if (!Array.isArray(data) || data.length === 0) {
            html = '<div class="loading-spinner">ไม่มีรายการอุปกรณ์ควบคุม</div>';
        } else {
            html = '<div class="device-grid">';
            data.forEach(dev => {
                let iconClass = "🔌";
                if (dev.icon === "lamp") iconClass = "💡";
                else if (dev.icon === "sparkle") iconClass = "✨";
                else if (dev.icon === "gauge") iconClass = "📊";
                else if (dev.icon === "bulb") iconClass = "💡";

                html += `
                    <div class="device-card-ui">
                        <div class="device-icon-wrapper">${iconClass}</div>
                        <div class="device-info-wrapper">
                            <div class="device-name-ui" title="${dev.name}">${dev.name}</div>
                            <div class="device-room-ui">${dev.room}</div>
                            <div class="device-badge-ui">${dev.type}</div>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }
    } else if (part === "scenes") {
        if (!Array.isArray(data) || data.length === 0) {
            html = '<div class="loading-spinner">ไม่มีรายการสภาพแวดล้อม (Scenes)</div>';
        } else {
            html = '<div class="scene-list-ui">';
            data.forEach(sc => {
                const actionsHtml = Array.isArray(sc.actions) && sc.actions.length > 0
                    ? sc.actions.map(act => `
                        <div class="scene-action-item">
                            <span class="action-device">${act.deviceId}</span>
                            <span class="action-val">${act.value}</span>
                        </div>
                    `).join('')
                    : '<div style="color:var(--text-secondary); font-size: 12px;">(ไม่มีคำสั่งทำงานในซีนนี้)</div>';

                html += `
                    <div class="scene-card-ui">
                        <div class="scene-header-ui">
                            <div class="scene-title-ui">✨ ${sc.name}</div>
                            <span class="badge">${sc.id}</span>
                        </div>
                        <div class="scene-actions-ui">
                            <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--accent-primary); margin-bottom: 6px;">คำสั่งอุปกรณ์:</div>
                            ${actionsHtml}
                        </div>
                        ${sc.prompt ? `
                        <div style="font-size: 12px; margin-top: 4px;">
                            <span style="color: var(--accent-secondary); font-weight: 600;">Prompt สั่งการ:</span> ${sc.prompt}
                        </div>
                        ` : ''}
                    </div>
                `;
            });
            html += '</div>';
        }
    } else if (part === "routines") {
        if (!Array.isArray(data) || data.length === 0) {
            html = '<div class="loading-spinner">ไม่มีกฎการทำงานอัตโนมัติ (Routines)</div>';
        } else {
            html = '<div class="routine-list-ui">';
            data.forEach(rt => {
                const statusBadge = rt.enabled 
                    ? '<span class="badge" style="color:var(--success-color); border-color:var(--success-color); background:rgba(0,230,118,0.1)">เปิดใช้งาน</span>'
                    : '<span class="badge" style="color:var(--text-secondary); border-color:var(--text-secondary); background:rgba(255,255,255,0.05)">ปิดใช้งาน</span>';

                const condsHtml = Array.isArray(rt.conditions) && rt.conditions.length > 0
                    ? rt.conditions.map(cond => `
                        <div class="routine-cond-item">
                            <span class="cond-source">${cond.source}</span>
                            <span class="cond-val">${cond.op} ${cond.value}</span>
                        </div>
                    `).join('')
                    : '<div style="color:var(--text-secondary); font-size: 12px;">(ไม่มีเงื่อนไข)</div>';

                const actsHtml = Array.isArray(rt.actions) && rt.actions.length > 0
                    ? rt.actions.map(act => {
                        if (act.type === "prompt") {
                            return `<div style="font-size: 13px; color: var(--text-primary); margin-bottom: 4px;">💬 รัน Prompt: "${act.prompt}"</div>`;
                        } else if (act.type === "scene") {
                            return `<div style="font-size: 13px; color: var(--text-primary); margin-bottom: 4px;">🎬 เรียกซีรี่/ซีน: ID ${act.sceneId}</div>`;
                        }
                        return `<div style="font-size: 13px; color: var(--text-primary); margin-bottom: 4px;">⚙️ ปรับค่าอุปกรณ์</div>`;
                    }).join('')
                    : '<div style="color:var(--text-secondary); font-size: 12px;">(ไม่มีผลลัพธ์การทำงาน)</div>';

                html += `
                    <div class="routine-card-ui">
                        <div class="routine-header-ui">
                            <div class="routine-title-ui">🤖 ${rt.name}</div>
                            ${statusBadge}
                        </div>
                        <div class="routine-actions-ui">
                            <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--accent-primary); margin-bottom: 6px;">เมื่อตรงเงื่อนไข (${rt.logic || "AND"}):</div>
                            ${condsHtml}
                        </div>
                        <div style="background: rgba(255,255,255,0.02); border-radius: 8px; padding: 12px;">
                            <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--accent-secondary); margin-bottom: 6px;">ระบบจะทำงานดังนี้:</div>
                            ${actsHtml}
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }
    } else if (part === "phone") {
        const batteryPercent = data.level !== undefined ? data.level : 0;
        const chargingText = data.charging ? "กำลังชาร์จไฟ ⚡" : "ไม่ได้ชาร์จไฟ";
        const text = data.text || `แบตเตอรี่: ${batteryPercent}%`;

        html = `
            <div class="phone-card-ui">
                <div class="phone-battery-radial" style="--battery-percent: ${batteryPercent}">
                    <span class="phone-battery-text">${batteryPercent}%</span>
                </div>
                <div class="phone-details-ui">
                    <div class="phone-status-lbl">${text}</div>
                    <div class="phone-status-sub">สถานะพลังงาน: ${chargingText}</div>
                </div>
            </div>
        `;
    }

    DOM.uiViewPanel.innerHTML = html;
}

// ── แท็บที่ 2: การพูดคุยกับเอเจนต์ (Agent Tab) ───────────────────────────────
function updateAgentUserDropdown() {
    const prevVal = DOM.agentUserSelect.value;
    DOM.agentUserSelect.innerHTML = '<option value="">-- ไม่ใช้บริบทของผู้ใช้งาน --</option>';
    
    Object.keys(state.users).forEach(uid => {
        const opt = document.createElement("option");
        opt.value = uid;
        opt.innerText = `${uid} (${state.users[uid].app_name || "แอปนิรนาม"})`;
        DOM.agentUserSelect.appendChild(opt);
    });

    DOM.agentUserSelect.value = prevVal;
}

DOM.agentForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const taskText = DOM.agentInputField.value.trim();
    if (!taskText) return;
    
    // ลบข้อความที่กรอกออก
    DOM.agentInputField.value = "";
    
    // แสดงข้อความในหน้าต่างแชต
    appendChatMessage(taskText, "user-msg");
    
    // แสดงสัญลักษณ์การโหลดคิดของเอเจนต์
    DOM.agentThinkingLoader.style.display = "flex";
    DOM.agentInputField.disabled = true;
    DOM.agentForm.querySelector("button").disabled = true;
    
    const selectedUser = DOM.agentUserSelect.value;
    
    try {
        const response = await fetchAPI("/admin/api/agent", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                task: taskText,
                user_id: selectedUser || null
            })
        });
        
        appendChatMessage(response.reply || "[ไม่มีการตอบกลับจากระบบ]", "agent-msg");
    } catch (err) {
        if (err.message !== "unauthorized") {
            appendChatMessage(`เกิดข้อผิดพลาดในการรันสมองกล: ${err.message}`, "system-msg");
        }
    } finally {
        DOM.agentThinkingLoader.style.display = "none";
        DOM.agentInputField.disabled = false;
        DOM.agentForm.querySelector("button").disabled = false;
        DOM.agentInputField.focus();
    }
});

function appendChatMessage(text, typeClass) {
    const msg = document.createElement("div");
    msg.className = `message ${typeClass}`;
    
    // ป้องกันการแฮ็กจากการแทรก HTML (XSS)
    if (typeClass === "system-msg") {
        msg.innerText = text;
    } else {
        msg.innerText = text;
    }
    
    DOM.chatMessagesBox.appendChild(msg);
    DOM.chatMessagesBox.scrollTop = DOM.chatMessagesBox.scrollHeight;
}

// ── แท็บที่ 3: ระบบหลังบ้าน (System Tab) ─────────────────────────────────────
async function loadSystemInfo() {
    DOM.systemInfoText.innerText = "กำลังประมวลผลข้อมูลของตัวเครื่อง...";
    DOM.toolsContainer.innerHTML = '<div class="loading-spinner">กำลังโหลดอุปกรณ์เครื่องมือ...</div>';
    
    try {
        const systemData = await fetchAPI("/admin/api/system");
        
        // 1. โชว์ System Info
        DOM.systemInfoText.innerText = systemData.system_info;
        
        // 2. โชว์รายชื่อเครื่องมือที่มี
        DOM.toolsContainer.innerHTML = "";
        if (systemData.tools.length === 0) {
            DOM.toolsContainer.innerHTML = '<div class="loading-spinner">ไม่พบการเรียกใช้งานเครื่องมือภายนอกในขณะนี้</div>';
            return;
        }
        
        systemData.tools.forEach(tool => {
            const card = document.createElement("div");
            card.className = "tool-card";
            card.innerHTML = `
                <div class="tool-name">${tool.name}</div>
                <div class="tool-desc">${tool.description || "ไม่มีคำอธิบายเพิ่มเติม"}</div>
            `;
            DOM.toolsContainer.appendChild(card);
        });
    } catch (err) {
        if (err.message !== "unauthorized") {
            DOM.systemInfoText.innerText = `โหลดข้อมูลล้มเหลว: ${err.message}`;
            DOM.toolsContainer.innerHTML = `<div class="loading-spinner" style="color:var(--danger-color)">ดึงข้อมูลเครื่องมือล้มเหลว: ${err.message}</div>`;
        }
    }
}

// ── แท็บที่ 4: การตั้งค่ารหัสผ่านความปลอดภัย (Settings Tab) ──────────────────────
async function loadSettingsInfo() {
    DOM.settingsError.style.display = "none";
    DOM.settingsSuccess.style.display = "none";
    DOM.settingsOldToken.value = "";
    DOM.settingsNewAdminToken.value = "";
    DOM.settingsNewMcpToken.value = "กำลังโหลดข้อมูล...";
    DOM.settingsNewMcpToken.disabled = true;
    
    try {
        const passwordsData = await fetchAPI("/admin/api/settings/passwords");
        DOM.settingsNewMcpToken.disabled = false;
        DOM.settingsNewMcpToken.value = passwordsData.mcp_token || "";
        
        if (!passwordsData.admin_token_set) {
            DOM.settingsOldToken.placeholder = "ไม่มีการตั้งรหัสผ่านเดิมไว้ (เว้นว่างไว้ได้เลย)...";
            DOM.settingsOldToken.disabled = true;
        } else {
            DOM.settingsOldToken.placeholder = "ระบุรหัสผ่านผู้ดูแลระบบปัจจุบันเพื่อยืนยัน...";
            DOM.settingsOldToken.disabled = false;
        }
    } catch (err) {
        if (err.message !== "unauthorized") {
            DOM.settingsNewMcpToken.value = "โหลดข้อมูลล้มเหลว";
            DOM.settingsError.innerText = `เกิดข้อผิดพลาด: ${err.message}`;
            DOM.settingsError.style.display = "block";
        }
    }
}

if (DOM.settingsForm) {
    DOM.settingsForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        DOM.settingsError.style.display = "none";
        DOM.settingsSuccess.style.display = "none";
        
        const oldToken = DOM.settingsOldToken.value;
        const newAdminToken = DOM.settingsNewAdminToken.value.trim();
        const newMcpToken = DOM.settingsNewMcpToken.value.trim();
        
        const submitBtn = DOM.settingsForm.querySelector("button");
        submitBtn.disabled = true;
        submitBtn.innerText = "กำลังบันทึก...";
        
        try {
            await fetchAPI("/admin/api/settings/passwords", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    old_admin_token: oldToken,
                    new_admin_token: newAdminToken,
                    new_mcp_token: newMcpToken
                })
            });
            
            DOM.settingsSuccess.innerText = "✓ บันทึกรหัสผ่านใหม่เรียบร้อยแล้ว";
            DOM.settingsSuccess.style.display = "block";
            
            // อัปเดตโทเค็นภายในแอปด้วยเผื่อว่าเราเปลี่ยน ADMIN_TOKEN ของตัวเอง
            // เพื่อไม่ให้โดน 401 ใน fetch ครั้งถัดไป
            if (newAdminToken) {
                state.token = newAdminToken;
                localStorage.setItem("admin_token", newAdminToken);
            } else {
                state.token = "";
                localStorage.removeItem("admin_token");
            }
            
            // รีโหลดข้อมูลหลังเปลี่ยนผ่านสำเร็จ
            setTimeout(() => {
                loadSettingsInfo();
            }, 1000);
        } catch (err) {
            if (err.message !== "unauthorized") {
                DOM.settingsError.innerText = err.message === "incorrect old password" 
                    ? "รหัสผ่านเก่าไม่ถูกต้อง โปรดลองอีกครั้ง" 
                    : `บันทึกล้มเหลว: ${err.message}`;
                DOM.settingsError.style.display = "block";
            }
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerText = "บันทึกการตั้งค่า";
        }
    });
}

let ws = null;
function connectWebSocket() {
    if (ws) {
        try { ws.close(); } catch(e) {}
        ws = null;
    }
    
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const tokenParam = state.token ? `?token=${encodeURIComponent(state.token)}` : "";
    const wsUrl = `${protocol}//${window.location.host}/admin/ws${tokenParam}`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === "update") {
                const uid = msg.user_id;
                const kind = msg.kind;
                const data = msg.data;
                
                if (!state.users[uid]) {
                    loadUsers();
                } else {
                    state.users[uid].last_seen = Math.floor(Date.now() / 1000);
                    renderUsersList();
                    
                    if (state.currentUser === uid) {
                        const user = state.users[uid];
                        DOM.currentUserSubtitle.innerText = `ชื่อแอปพลิเคชัน: ${user.app_name || "ไม่มี"} | เชื่อมต่อล่าสุด: ${new Date().toLocaleString("th-TH")}`;
                        
                        if (state.currentPart === kind) {
                            if (document.activeElement !== DOM.jsonEditor) {
                                DOM.jsonEditor.value = JSON.stringify(data, null, 4);
                                DOM.jsonValidity.style.display = "none";
                                DOM.btnSavePart.disabled = false;
                            }
                        }
                    }
                }
            }
        } catch (e) {
            console.error("Error processing websocket message:", e);
        }
    };
    
    ws.onclose = () => {
        setTimeout(() => {
            if (state.token || !DOM.loginModal.style.display || DOM.loginModal.style.display === "none") {
                connectWebSocket();
            }
        }, 3000);
    };
    
    ws.onerror = (err) => {
        console.error("WebSocket error:", err);
    };
}

// ── เริ่มต้นระบบตอนเปิดหน้าเว็บ ────────────────────────────────────────────────
async function init() {
    // โหลดรายชื่อผู้ใช้งานครั้งแรกเพื่อทดสอบโทเค็นด้วย
    try {
        await fetchAPI("/admin/api/users");
        // ถ้าไม่ error แสดงว่าโทเค็นใช้ได้ หรือ ไม่ต้องใช้
        hideLoginModal();
        switchTab("tab-users");
    } catch (err) {
        // หากไม่ได้รับอนุญาตให้โชว์หน้าล็อกอินขึ้นมา
        if (err.message === "unauthorized" || state.token) {
            showLoginModal();
        }
    }
}

// โหลดระบบ
window.addEventListener("DOMContentLoaded", init);
