/* =============================================================
   APP.JS — Logic vận hành Web Dashboard Video Doodle (SPA)
   ============================================================= */

// TRẠNG THÁI TOÀN CỤC CỦA FRONTEND
const state = {
    activeTab: 'projects-tab',
    projects: [],
    profiles: [],
    activeProfile: null,
    currentProject: null, // Chi tiết dự án đang mở
    currentProjectName: '',
    activeStep: 2, // Giai đoạn làm việc (2-6) trong workspace
    config: {},
    sseConnection: null,
    chromeProfiles: []
};

// API ENDPOINTS CƠ BẢN
const handleResponse = (response) => {
    if (response.ok) {
        return response.json();
    }
    return response.json().then(err => {
        let msg = 'Lỗi API';
        if (err.detail) {
            if (typeof err.detail === 'string') {
                msg = err.detail;
            } else if (Array.isArray(err.detail)) {
                msg = err.detail.map(d => {
                    if (typeof d === 'string') return d;
                    return d.msg || JSON.stringify(d);
                }).join(', ');
            } else {
                msg = JSON.stringify(err.detail);
            }
        }
        throw new Error(msg);
    }).catch(e => {
        if (e instanceof Error) throw e;
        throw new Error('Lỗi phản hồi từ server');
    });
};

const API = {
    getConfig: () => fetch('/api/config').then(handleResponse),
    saveConfig: (cfg) => fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg)
    }).then(handleResponse),
    getProfiles: () => fetch('/api/profiles').then(handleResponse),
    createProfile: (payload) => fetch('/api/profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(handleResponse),
    getActiveProfile: () => fetch('/api/active-profile').then(handleResponse),
    setActiveProfile: (profileId) => fetch('/api/active-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: profileId })
    }).then(handleResponse),
    generateTopics: (lang) => fetch('/api/projects/generate-topics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: lang })
    }).then(handleResponse),
    getProjects: () => fetch('/api/projects').then(handleResponse),
    createProject: (payload) => fetch('/api/projects/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(handleResponse),
    getProjectDetails: (name) => fetch(`/api/projects/${name}`).then(handleResponse),
    deleteProject: (name) => fetch(`/api/projects/${name}`, { method: 'DELETE' }).then(handleResponse),
    saveScript: (name, scriptText) => fetch(`/api/projects/${name}/save-script`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script_text: scriptText })
    }).then(handleResponse),
    savePrompts: (name, prompts) => fetch(`/api/projects/${name}/save-prompts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prompts)
    }).then(handleResponse),
    runStage: (name, stage) => fetch(`/api/projects/${name}/run-stage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: stage })
    }).then(handleResponse),
    stopStage: (name) => fetch(`/api/projects/${name}/stop-stage`, {
        method: 'POST'
    }).then(handleResponse),
    updateImageConfig: (name, imageMode, activeProfile) => fetch(`/api/projects/${name}/update-image-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_mode: imageMode, active_profile: activeProfile })
    }).then(handleResponse)
};

// KHỞI ĐỘNG KHI TẢI TRANG
document.addEventListener('DOMContentLoaded', () => {
    initTabNavigation();
    initProfileSelector();
    loadConfiguration();
    loadProjectsList();
    initProjectModal();
    initWorkspaceControls();
    loadChromeProfiles();
});

// 1. ĐIỀU HƯỚNG TABS SIDEBAR
function initTabNavigation() {
    document.querySelectorAll('.sidebar-menu .menu-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = item.getAttribute('data-tab');
            
            // Xóa active cũ
            document.querySelectorAll('.sidebar-menu .menu-item').forEach(i => i.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            document.getElementById('workspace-view').classList.remove('active');
            
            // Set active mới
            item.classList.add('active');
            document.getElementById(tabId).classList.add('active');
            state.activeTab = tabId;

            // Đóng kết nối SSE nếu rời khỏi workspace
            closeSSE();

            // Làm mới danh sách dự án nếu mở tab Projects
            if (tabId === 'projects-tab') {
                loadProjectsList();
            }
        });
    });
}

// 2. TẢI VÀ LƯU CẤU HÌNH HỆ THỐNG
function loadConfiguration() {
    API.getConfig().then(cfg => {
        state.config = cfg;
        
        // Cập nhật trạng thái API kết nối trên sidebar
        updateApiStatusIndicator('gemini-api-status', cfg.GEMINI_API_KEY && cfg.GEMINI_API_KEY !== 'YOUR_GEMINI_API_KEY_HERE');
        updateApiStatusIndicator('tts-api-status', cfg.TTS_ENGINE === 'edge-tts' || (cfg.TTS_ENGINE === 'elevenlabs' && cfg.ELEVENLABS_API_KEY));

        // Điền vào form Cấu hình hệ thống
        setValue('cfg-gemini-key', cfg.GEMINI_API_KEY);
        setValue('cfg-elevenlabs-key', cfg.ELEVENLABS_API_KEY);
        setValue('cfg-tts-engine', cfg.TTS_ENGINE);
        setValue('cfg-image-mode', cfg.IMAGE_MODE);
        setValue('cfg-edge-voice', cfg.EDGE_TTS_VOICE);
        setValue('cfg-elevenlabs-voice', cfg.ELEVENLABS_VOICE_ID);
        setValue('cfg-elevenlabs-model', cfg.ELEVENLABS_MODEL_ID);
        setValue('cfg-script-model', cfg.GEMINI_SCRIPT_MODEL);
        setValue('cfg-prompt-model', cfg.GEMINI_PROMPT_MODEL);
        setValue('cfg-video-width', cfg.VIDEO_WIDTH);
        setValue('cfg-video-height', cfg.VIDEO_HEIGHT);
        setValue('cfg-video-fps', cfg.VIDEO_FPS);
        setValue('cfg-wobble', cfg.WOBBLE_INTENSITY);

        // Điền vào form Visual DNA
        setValue('cfg-channel-kb', cfg.CHANNEL_KNOWLEDGE_BASE);
        setValue('cfg-visual-dna', cfg.VISUAL_STYLE_DNA);
        setValue('cfg-style-anchor', cfg.IMAGE_PROMPT_STYLE_ANCHOR);
        setValue('cfg-style-lock', cfg.IMAGE_PROMPT_STYLE_LOCK);
        setValue('cfg-viral-angles', cfg.PROVEN_VIRAL_TOPIC_ANGLES);
        setValue('cfg-proposed-ideas', cfg.PROPOSED_IDEAS || '');
    });

    // Sự kiện lưu cấu hình
    document.getElementById('btn-save-config').addEventListener('click', () => {
        const payload = gatherConfigFromUI();
        API.saveConfig(payload).then(res => {
            if (res.status === 'success') {
                showToast(res.message, 'success');
                loadConfiguration(); // Refresh indicator
            } else {
                showToast('Lỗi lưu cấu hình', 'danger');
            }
        });
    });

    // Sự kiện lưu Visual DNA
    document.getElementById('btn-save-dna').addEventListener('click', () => {
        const payload = gatherConfigFromUI();
        API.saveConfig(payload).then(res => {
            if (res.status === 'success') {
                showToast('Đã lưu Visual DNA kênh!', 'success');
                loadConfiguration();
            } else {
                showToast('Lỗi lưu DNA', 'danger');
            }
        });
    });
}

function updateApiStatusIndicator(elemId, isActive) {
    const indicator = document.querySelector(`#${elemId} .status-indicator`);
    const label = document.querySelector(`#${elemId} span:last-child`);
    
    if (isActive) {
        indicator.className = 'status-indicator green';
        if (elemId === 'tts-api-status') {
            label.textContent = `TTS: ${state.config.TTS_ENGINE === 'edge-tts' ? 'Edge (Free)' : 'ElevenLabs'}`;
        }
    } else {
        indicator.className = 'status-indicator red';
        if (elemId === 'tts-api-status') {
            label.textContent = 'TTS (Thiếu key)';
        }
    }
}

function gatherConfigFromUI() {
    return {
        GEMINI_API_KEY: getValue('cfg-gemini-key'),
        ELEVENLABS_API_KEY: getValue('cfg-elevenlabs-key'),
        TTS_ENGINE: getValue('cfg-tts-engine'),
        IMAGE_MODE: getValue('cfg-image-mode'),
        EDGE_TTS_VOICE: getValue('cfg-edge-voice'),
        ELEVENLABS_VOICE_ID: getValue('cfg-elevenlabs-voice'),
        ELEVENLABS_MODEL_ID: getValue('cfg-elevenlabs-model'),
        GEMINI_SCRIPT_MODEL: getValue('cfg-script-model'),
        GEMINI_PROMPT_MODEL: getValue('cfg-prompt-model'),
        VIDEO_WIDTH: parseInt(getValue('cfg-video-width')) || 1920,
        VIDEO_HEIGHT: parseInt(getValue('cfg-video-height')) || 1080,
        VIDEO_FPS: parseInt(getValue('cfg-video-fps')) || 24,
        WOBBLE_INTENSITY: parseInt(getValue('cfg-wobble')) || 0,
        
        CHANNEL_KNOWLEDGE_BASE: getValue('cfg-channel-kb'),
        VISUAL_STYLE_DNA: getValue('cfg-visual-dna'),
        IMAGE_PROMPT_STYLE_ANCHOR: getValue('cfg-style-anchor'),
        IMAGE_PROMPT_STYLE_LOCK: getValue('cfg-style-lock'),
        PROVEN_VIRAL_TOPIC_ANGLES: getValue('cfg-viral-angles'),
        PROPOSED_IDEAS: getValue('cfg-proposed-ideas')
    };
}

// 3. TẢI DANH SÁCH DỰ ÁN
function loadProjectsList() {
    const container = document.getElementById('projects-list-container');
    container.innerHTML = `
        <div class="loading-state">
            <i class="fa-solid fa-circle-notch fa-spin text-accent"></i>
            <p>Đang tải danh sách dự án...</p>
        </div>
    `;

    API.getProjects().then(projects => {
        state.projects = projects;
        if (projects.length === 0) {
            container.innerHTML = `
                <div class="loading-state">
                    <i class="fa-solid fa-folder-open text-tip"></i>
                    <p>Chưa có dự án nào được tạo. Nhấp nút "Tạo dự án mới" để bắt đầu.</p>
                </div>
            `;
            return;
        }

        let html = '';
        projects.forEach(p => {
            const stages = {
                1: 'Chủ đề',
                2: 'Kịch bản',
                3: 'Giọng đọc',
                4: 'Prompts',
                5: 'Hình ảnh',
                6: 'Hoàn thành'
            };
            const stageLabel = stages[p.current_stage] || `Bước ${p.current_stage}`;
            const activeBadgeClass = p.current_stage === 6 ? 'badge-success' : 'badge-accent';
            const runningStatus = p.is_running ? '<span class="badge badge-info"><i class="fa-solid fa-spinner fa-spin"></i> Đang chạy</span>' : '';

            html += `
                <div class="glass-card project-card" onclick="openProjectWorkspace('${p.project_name}')">
                    <div class="card-header">
                        <i class="fa-solid fa-film text-accent"></i>
                        <span class="badge ${activeBadgeClass}">${stageLabel}</span>
                        ${runningStatus}
                    </div>
                    <div class="card-body">
                        <h4>${p.topic_title}</h4>
                        <div class="project-stats">
                            <span><i class="fa-solid fa-database"></i> ${p.folder_size_mb} MB</span>
                            <span><i class="fa-solid fa-clock"></i> ${formatDate(p.last_updated)}</span>
                        </div>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    });
}

// 4. MODAL TẠO DỰ ÁN MỚI
function initProjectModal() {
    const modal = document.getElementById('modal-new-project');
    const btnNew = document.getElementById('btn-new-project');
    const btnClose = document.getElementById('modal-close-new-project');
    const btnCancel = document.getElementById('modal-cancel-new-project');
    const btnSubmit = document.getElementById('btn-submit-new-project');
    
    // Toggle Mode: Manual vs AI Suggestions
    const modeManualBtn = document.getElementById('mode-manual-btn');
    const modeAiBtn = document.getElementById('mode-ai-btn');
    const manualForm = document.getElementById('new-project-manual-form');
    const aiForm = document.getElementById('new-project-ai-form');

    let selectedAiTopic = null;

    btnNew.addEventListener('click', () => {
        modal.classList.add('active');
        // Reset modal forms
        setValue('project-title-input', '');
        setValue('project-folder-input', '');
        document.getElementById('ai-topics-list-container').innerHTML = '';
        document.getElementById('ai-topics-list-container').classList.add('hidden');
        selectedAiTopic = null;
        switchModalMode('manual');
    });

    const closeModal = () => modal.classList.remove('active');
    btnClose.addEventListener('click', closeModal);
    btnCancel.addEventListener('click', closeModal);

    modeManualBtn.addEventListener('click', () => switchModalMode('manual'));
    modeAiBtn.addEventListener('click', () => switchModalMode('ai'));

    function switchModalMode(mode) {
        if (mode === 'manual') {
            modeManualBtn.classList.add('active');
            modeAiBtn.classList.remove('active');
            manualForm.classList.add('active');
            aiForm.classList.remove('active');
        } else {
            modeManualBtn.classList.remove('active');
            modeAiBtn.classList.add('active');
            manualForm.classList.remove('active');
            aiForm.classList.add('active');
        }
    }

    // AI Suggestions button
    const btnGenAi = document.getElementById('btn-generate-ai-topics');
    const loadingAi = document.getElementById('ai-topics-loading');
    const listAi = document.getElementById('ai-topics-list-container');

    btnGenAi.addEventListener('click', () => {
        btnGenAi.disabled = true;
        loadingAi.classList.remove('hidden');
        listAi.classList.add('hidden');

        const lang = getValue('project-language-select') || 'vi';
        API.generateTopics(lang).then(res => {
            btnGenAi.disabled = false;
            loadingAi.classList.add('hidden');
            
            if (res.status === 'success') {
                listAi.classList.remove('hidden');
                let html = '';
                res.topics.forEach(t => {
                    const score = t.score ? `${t.score}/10` : 'N/A';
                    const analysis = t.analysis ? `<p style="font-size: 12px; color: var(--text-muted); margin-top: 5px; line-height: 1.4; font-weight: normal; margin-bottom: 0;">${t.analysis}</p>` : '';
                    html += `
                        <div class="ai-topic-item" data-id="${t.id}" style="padding: 14px; margin-bottom: 10px; border-radius: 8px; cursor: pointer; border: 1px solid var(--border-color); background-color: rgba(255,255,255,0.02); transition: all 0.2s;">
                            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                                <strong style="font-size: 13.5px; color: var(--text-primary);">${t.id}. <span class="topic-title-text">${t.title}</span></strong>
                                <span class="badge badge-warning" style="font-size: 11px; white-space: nowrap; margin-left: 10px;">Độ viral: ${score}</span>
                            </div>
                            ${analysis}
                        </div>
                    `;
                });
                listAi.innerHTML = html;

                // Event click select topic
                listAi.querySelectorAll('.ai-topic-item').forEach(item => {
                    item.addEventListener('click', () => {
                        listAi.querySelectorAll('.ai-topic-item').forEach(i => i.classList.remove('selected'));
                        item.classList.add('selected');
                        selectedAiTopic = item.querySelector('.topic-title-text').textContent.trim();
                    });
                });
            }
        }).catch(err => {
            btnGenAi.disabled = false;
            loadingAi.classList.add('hidden');
            showToast(err, 'danger');
        });
    });

    // Tạo dự án submit
    btnSubmit.addEventListener('click', () => {
        let topicTitle = '';
        let folderName = '';

        if (modeManualBtn.classList.contains('active')) {
            topicTitle = getValue('project-title-input').trim();
            folderName = getValue('project-folder-input').trim();
        } else {
            topicTitle = selectedAiTopic;
            if (!topicTitle) {
                showToast('Vui lòng chọn 1 chủ đề từ gợi ý của Gemini!', 'warning');
                return;
            }
        }

        if (!topicTitle) {
            showToast('Chủ đề video không được để trống!', 'warning');
            return;
        }

        btnSubmit.disabled = true;

        const lang = getValue('project-language-select') || 'vi';
        API.createProject({
            topic_title: topicTitle,
            project_name: folderName,
            active_profile: state.activeProfile ? state.activeProfile.profile_id : 'ancient_history',
            language: lang
        }).then(res => {
            btnSubmit.disabled = false;
            if (res.status === 'success') {
                closeModal();
                showToast(`Đã tạo dự án '${res.project_name}' thành công!`, 'success');
                // Chuyển sang Workspace ngay lập tức
                openProjectWorkspace(res.project_name);
            } else {
                showToast('Lỗi tạo dự án', 'danger');
            }
        }).catch(err => {
            btnSubmit.disabled = false;
            showToast('Lỗi kết nối máy chủ', 'danger');
        });
    });
}

// 5. MỞ WORKSPACE DỰ ÁN CỤ THỂ
function openProjectWorkspace(projectName) {
    state.currentProjectName = projectName;
    
    // Đổi hiển thị tab sang Workspace panel
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.sidebar-menu .menu-item').forEach(i => i.classList.remove('active'));
    
    const wsPanel = document.getElementById('workspace-view');
    wsPanel.classList.add('active');
    
    // Tải thông tin dự án chi tiết
    reloadProjectDetails().then(() => {
        // Mở giai đoạn làm việc hiện tại
        const targetStep = Math.min(Math.max(state.currentProject.info.current_stage, 2), 6);
        switchWorkspaceStep(targetStep);
    });
}

function reloadProjectDetails() {
    return API.getProjectDetails(state.currentProjectName).then(details => {
        state.currentProject = details;
        
        // Cập nhật thông số tiêu đề
        document.getElementById('ws-project-title').textContent = details.info.topic_title;
        document.getElementById('ws-project-size').textContent = `${details.info.folder_size_mb || details.folder_size_mb || 0} MB`;
        
        const engineBadge = document.getElementById('ws-project-engine');
        engineBadge.textContent = `TTS: ${details.info.tts_engine.toUpperCase()}`;
        
        const modeBadge = document.getElementById('ws-project-img-mode');
        modeBadge.textContent = `Ảnh: ${details.info.image_mode.toUpperCase()}`;
        document.getElementById('ws-img-mode-badge-right').textContent = `Chế độ ảnh: ${details.info.image_mode.toUpperCase()}`;

        // Cập nhật trạng thái pipeline nodes (completed / active)
        const currentStage = details.info.current_stage;
        document.querySelectorAll('.pipeline-tracker .step-node').forEach(node => {
            const step = parseInt(node.getAttribute('data-step'));
            node.classList.remove('active', 'completed');
            if (step === state.activeStep) {
                node.classList.add('active');
            }
            if (step <= currentStage) {
                node.classList.add('completed');
            }
        });

        // Nạp kịch bản vào editor (Stage 2)
        setValue('ws-script-editor', details.script_text);

        // Nạp audio & timing (Stage 3)
        renderStage3Timing(details);

        // Nạp prompts (Stage 4)
        renderStage4Prompts(details);

        // Nạp ảnh (Stage 5)
        renderStage5Images(details);

        // Nạp video (Stage 6)
        renderStage6Video(details);

        // Nạp mô tả công việc của Giai đoạn hiện tại vào panel điều khiển bên trái
        updateWorkspaceControlPanel(state.activeStep);
        
        // Kiểm tra xem có đang chạy ngầm và kết nối SSE
        if (details.is_running) {
            connectSSE(state.currentProjectName);
        } else {
            closeSSE();
        }
    });
}

// 6. WORKSPACE STEP TRACKING & SWITCHING
function initWorkspaceControls() {
    // Back button
    document.getElementById('btn-workspace-back').addEventListener('click', () => {
        document.getElementById('workspace-view').classList.remove('active');
        document.querySelector('[data-tab="projects-tab"]').click(); // Quay lại màn hình chính
    });

    // Step tracker click nodes
    document.querySelectorAll('.pipeline-tracker .step-node').forEach(node => {
        node.addEventListener('click', () => {
            const step = parseInt(node.getAttribute('data-step'));
            switchWorkspaceStep(step);
        });
    });

    // Save buttons
    document.getElementById('btn-save-script').addEventListener('click', () => {
        const text = getValue('ws-script-editor');
        API.saveScript(state.currentProjectName, text).then(res => {
            if (res.status === 'success') {
                showToast(res.message, 'success');
                reloadProjectDetails();
            } else {
                showToast('Lỗi lưu kịch bản', 'danger');
            }
        });
    });

    document.getElementById('btn-save-prompts').addEventListener('click', () => {
        const prompts = gatherPromptsFromUI();
        API.savePrompts(state.currentProjectName, prompts).then(res => {
            if (res.status === 'success') {
                showToast(res.message, 'success');
                reloadProjectDetails();
            } else {
                showToast('Lỗi lưu prompts', 'danger');
            }
        });
    });

    document.getElementById('btn-save-img-config').addEventListener('click', () => {
        const mode = document.getElementById('cfg-img-mode-select').value;
        const profile = document.getElementById('cfg-img-profile-select').value;
        API.updateImageConfig(state.currentProjectName, mode, profile).then(res => {
            if (res.status === 'success') {
                showToast(res.message, 'success');
                const modeBadge = document.getElementById('ws-img-mode-badge-right');
                if (modeBadge) {
                    modeBadge.textContent = `Chế độ: ${mode === 'api' ? 'API (Imagen)' : 'Export'}`;
                }
                reloadProjectDetails();
            } else {
                showToast(res.message || 'Lỗi lưu cấu hình ảnh', 'danger');
            }
        }).catch(err => {
            showToast(err || 'Lỗi lưu cấu hình ảnh', 'danger');
        });
    });

    const imgModeSelect = document.getElementById('cfg-img-mode-select');
    if (imgModeSelect) {
        imgModeSelect.addEventListener('change', (e) => {
            const isExport = e.target.value === 'export';
            const chromeRow = document.getElementById('chrome-profile-config-row');
            if (chromeRow) {
                chromeRow.style.display = isExport ? 'flex' : 'none';
            }
            const instructions = document.getElementById('imagefx-instructions');
            if (instructions) {
                instructions.style.display = isExport ? 'block' : 'none';
            }
        });
    }

    document.getElementById('btn-open-chrome').addEventListener('click', () => {
        const profileFolder = document.getElementById('cfg-chrome-profile-select').value;
        fetch('/api/open-chrome', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile_folder: profileFolder })
        }).then(r => r.json())
        .then(res => {
            if (res.status === 'success') {
                showToast(res.message, 'success');
            } else {
                showToast(res.message || 'Lỗi mở Chrome', 'danger');
            }
        }).catch(err => {
            showToast('Không thể kết nối API mở Chrome', 'danger');
        });
    });

    document.getElementById('btn-create-chrome-profile').addEventListener('click', () => {
        const name = prompt("Nhập tên Profile Chrome mới (ví dụ: Kenh_Moi):");
        if (!name || !name.trim()) return;
        
        fetch('/api/chrome-profiles/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name.trim() })
        }).then(r => {
            if (!r.ok) return r.json().then(err => { throw new Error(err.detail || 'Lỗi khi tạo profile') });
            return r.json();
        }).then(res => {
            if (res.status === 'success') {
                showToast(res.message, 'success');
                loadChromeProfiles().then(() => {
                    const select = document.getElementById('cfg-chrome-profile-select');
                    if (select) select.value = res.folder;
                });
            } else {
                showToast(res.message || 'Lỗi tạo profile', 'danger');
            }
        }).catch(err => {
            showToast(err || 'Không thể kết nối API tạo profile', 'danger');
        });
    });

    // Delete Project button
    document.getElementById('btn-delete-project').addEventListener('click', () => {
        const confirmed = confirm(`CẢNH BÁO: Bạn có chắc chắn muốn xóa dự án '${state.currentProject.info.topic_title}'? Thao tác này sẽ xóa vĩnh viễn toàn bộ kịch bản, âm thanh và video đã xuất.`);
        if (confirmed) {
            API.deleteProject(state.currentProjectName).then(res => {
                if (res.status === 'success') {
                    showToast(res.message, 'success');
                    document.getElementById('btn-workspace-back').click();
                } else {
                    showToast(res.detail || 'Lỗi khi xóa dự án', 'danger');
                }
            });
        }
    });

    // Dropdown chọn chạy stage
    const dropdownBtn = document.getElementById('btn-run-stage-dropdown-btn');
    const dropdownMenu = document.getElementById('stage-picker-dropdown');
    
    dropdownBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdownMenu.classList.toggle('hidden');
    });

    document.addEventListener('click', () => {
        dropdownMenu.classList.add('hidden');
    });

    dropdownMenu.querySelectorAll('.dropdown-item').forEach(item => {
        item.addEventListener('click', () => {
            const stage = parseInt(item.getAttribute('data-run-stage'));
            triggerRunStage(stage);
        });
    });

    // Chạy Stage đang hoạt động chính
    document.getElementById('btn-run-current-stage').addEventListener('click', () => {
        triggerRunStage(state.activeStep);
    });

    // Dừng Stage đang hoạt động chính
    document.getElementById('btn-stop-pipeline').addEventListener('click', () => {
        stopPipeline();
    });

    // Lưu YouTube SEO Metadata
    const saveMetadataBtn = document.getElementById('btn-save-metadata');
    if (saveMetadataBtn) {
        saveMetadataBtn.addEventListener('click', () => {
            const title = document.getElementById('yt-title-input').value.trim();
            const desc = document.getElementById('yt-desc-textarea').value.trim();
            const tagsRaw = document.getElementById('yt-tags-input').value.trim();
            const tags = tagsRaw ? tagsRaw.split(',').map(t => t.trim()).filter(Boolean) : [];
            
            saveMetadataBtn.disabled = true;
            saveMetadataBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang lưu...';
            
            fetch(`/api/projects/${state.currentProjectName}/metadata`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, description: desc, tags })
            })
            .then(res => res.json())
            .then(res => {
                saveMetadataBtn.disabled = false;
                saveMetadataBtn.innerHTML = '<i class="fa-solid fa-save"></i> Lưu Metadata';
                if (res.status === 'success') {
                    showToast('Đã lưu YouTube SEO Metadata!', 'success');
                } else {
                    showToast('Lỗi lưu metadata: ' + (res.detail || 'Lỗi không xác định'), 'danger');
                }
            })
            .catch(err => {
                saveMetadataBtn.disabled = false;
                saveMetadataBtn.innerHTML = '<i class="fa-solid fa-save"></i> Lưu Metadata';
                showToast('Lỗi kết nối: ' + err.message, 'danger');
            });
        });
    }
}

let galleryPollInterval = null;

function switchWorkspaceStep(step) {
    state.activeStep = step;
    
    // Hủy polling cũ nếu có
    if (galleryPollInterval) {
        clearInterval(galleryPollInterval);
        galleryPollInterval = null;
    }

    // Nếu chuyển sang Stage 5 (Hình ảnh), thiết lập polling tải lại danh sách ảnh mỗi 2 giây
    if (step === 5) {
        galleryPollInterval = setInterval(() => {
            const wsView = document.getElementById('workspace-view');
            if (wsView && wsView.classList.contains('active') && state.activeStep === 5 && state.currentProjectName) {
                API.getProjectDetails(state.currentProjectName).then(details => {
                    const oldImagesStr = JSON.stringify(state.currentProject ? state.currentProject.existing_images : []);
                    const newImagesStr = JSON.stringify(details.existing_images);
                    if (oldImagesStr !== newImagesStr) {
                        state.currentProject = details;
                        renderStage5Images(details);
                    }
                }).catch(err => console.warn("Lỗi poll ảnh:", err));
            } else {
                clearInterval(galleryPollInterval);
                galleryPollInterval = null;
            }
        }, 2000);
    }

    // Cập nhật Pipeline Nodes Active
    document.querySelectorAll('.pipeline-tracker .step-node').forEach(node => {
        const nStep = parseInt(node.getAttribute('data-step'));
        node.classList.remove('active');
        if (nStep === step) node.classList.add('active');
    });

    // Cập nhật các Tab View bên phải
    document.querySelectorAll('.stage-view-container').forEach(view => {
        view.classList.remove('active');
    });
    const targetView = document.getElementById(`stage-view-${step}`);
    if (targetView) targetView.classList.add('active');

    // Nếu chuyển sang Stage 7 (Đăng YouTube), tải metadata
    if (step === 7) {
        loadProjectMetadata();
    }

    // Cập nhật mô tả hoạt động bên trái
    updateWorkspaceControlPanel(step);
}

async function loadProjectMetadata() {
    if (!state.currentProjectName) return;
    const titleInput = document.getElementById('yt-title-input');
    const descTextarea = document.getElementById('yt-desc-textarea');
    const tagsInput = document.getElementById('yt-tags-input');
    
    if (!titleInput || !descTextarea || !tagsInput) return;
    
    titleInput.value = '';
    titleInput.placeholder = 'Đang tải hoặc tự sinh SEO Title...';
    descTextarea.value = '';
    descTextarea.placeholder = 'Đang tải hoặc tự sinh SEO Description...';
    tagsInput.value = '';
    tagsInput.placeholder = 'Đang tải SEO Tags...';
    
    try {
        const res = await fetch(`/api/projects/${state.currentProjectName}/metadata`);
        if (res.ok) {
            const data = await res.json();
            if (data.status === 'success' && data.metadata) {
                titleInput.value = data.metadata.title || '';
                descTextarea.value = data.metadata.description || '';
                tagsInput.value = (data.metadata.tags || []).join(', ');
            }
        }
    } catch (err) {
        console.error("Lỗi khi tải metadata:", err);
        showToast("Lỗi tải YouTube SEO Metadata", "danger");
    }
}

function updateWorkspaceControlPanel(step) {
    const title = document.getElementById('ws-stage-title');
    const desc = document.getElementById('ws-stage-desc');
    const runBtn = document.getElementById('btn-run-current-stage');

    const stageDetails = {
        2: {
            title: 'Giai đoạn 2: Tạo kịch bản giáo dục',
            desc: 'Dùng Gemini AI biên soạn một kịch bản hoạt hình chuẩn dài khoảng 1500-2000 từ dựa trên DNA kênh.',
            icon: 'fa-file-signature'
        },
        3: {
            title: 'Giai đoạn 3: Tạo giọng đọc & mốc thời gian',
            desc: 'Chuyển kịch bản thành giọng đọc truyền cảm qua Edge-TTS / ElevenLabs và lưu chính xác mốc thời gian từng câu.',
            icon: 'fa-volume-high'
        },
        4: {
            title: 'Giai đoạn 4: Thiết kế Prompt hình ảnh',
            desc: 'Gemini phân tích từng câu thoại và thiết kế các prompt vẽ tranh hoạt hình người que thích hợp.',
            icon: 'fa-wand-magic-sparkles'
        },
        5: {
            title: 'Giai đoạn 5: Tải hoặc tạo hình ảnh',
            desc: 'Trong chế độ API, hệ thống tự động sinh ảnh qua Imagen. Ở chế độ Export, bạn sao chép prompts để paste vào ImageFX và kéo thả ảnh về images/.',
            icon: 'fa-images'
        },
        6: {
            title: 'Giai đoạn 6: Ghép và dựng video',
            desc: 'Ghép nối tất cả âm thanh, hình ảnh và tạo hiệu ứng nhấp nhô rung lắc hoạt hình sống động thành tệp video .mp4.',
            icon: 'fa-film'
        },
        7: {
            title: 'Giai đoạn 7: Đăng video lên YouTube',
            desc: 'Tự động tạo tiêu đề/mô tả chuẩn SEO bằng Gemini và điều khiển Chrome tự động tải video lên YouTube Studio.',
            icon: 'fa-cloud-arrow-up'
        }
    };

    const details = stageDetails[step];
    title.textContent = details.title;
    desc.textContent = details.desc;
    runBtn.innerHTML = `<i class="fa-solid ${details.icon}"></i> Chạy Giai đoạn ${step}`;

    // Vô hiệu hóa nút bấm nếu pipeline đang chạy
    const stopBtn = document.getElementById('btn-stop-pipeline');
    if (state.currentProject && state.currentProject.is_running) {
        runBtn.disabled = true;
        if (stopBtn) stopBtn.disabled = false;
    } else {
        runBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
    }
}

// KÍCH HOẠT CHẠY STAGE PIPELINE
function triggerRunStage(stage) {
    const runBtn = document.getElementById('btn-run-current-stage');
    runBtn.disabled = true;
    
    // Hiện spinner console
    document.getElementById('console-spinner').classList.remove('hidden');

    API.runStage(state.currentProjectName, stage).then(res => {
        if (res.status === 'success') {
            showToast(res.message, 'info');
            // Mở kết nối SSE để theo dõi log
            connectSSE(state.currentProjectName);
        } else {
            showToast('Chạy lỗi: ' + res.message, 'danger');
            runBtn.disabled = false;
            document.getElementById('console-spinner').classList.add('hidden');
        }
    }).catch(err => {
        showToast(err, 'danger');
        runBtn.disabled = false;
        document.getElementById('console-spinner').classList.add('hidden');
    });
}

// 7. REAL-TIME LOG STREAMING (SERVER-SENT EVENTS)
function connectSSE(projectName) {
    closeSSE(); // Đóng kết nối cũ nếu có

    const consoleBox = document.getElementById('console-log-box');
    const spinner = document.getElementById('console-spinner');
    const runBtn = document.getElementById('btn-run-current-stage');
    const stopBtn = document.getElementById('btn-stop-pipeline');

    spinner.classList.remove('hidden');
    runBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = false;

    // Tạo EventSource mới
    state.sseConnection = new EventSource(`/api/projects/${projectName}/logs`);

    state.sseConnection.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            // Xử lý ghi đè log ban đầu (chứa toàn bộ nội dung cũ)
            if (data.log) {
                // Thay đổi ký tự xuống dòng xuống console
                consoleBox.innerHTML = data.log.replace(/\n/g, '<br>');
                consoleBox.scrollTop = consoleBox.scrollHeight; // Tự động cuộn
                
                // Đồng bộ hiển thị luôn khi có tiến trình hoàn thành (Batch hoặc Tiến độ tải về)
                if (data.log.includes('Batch') || data.log.includes('[Tiến độ]') || data.log.includes('timing.json') || data.log.includes('timing hoàn tất')) {
                    throttleReloadProjectDetails();
                }
            }
            
            // Nếu tiến trình kết thúc
            if (data.is_running === false || data.log.includes('=== HOÀN TẤT ===')) {
                closeSSE();
                spinner.classList.add('hidden');
                runBtn.disabled = false;
                if (stopBtn) stopBtn.disabled = true;
                showToast('Quy trình chạy đã hoàn thành!', 'success');
                // Tải lại chi tiết dự án để cập nhật tài nguyên mới tạo
                reloadProjectDetails();
            }
        } catch (e) {
            console.error('SSE JSON error:', e);
        }
    };

    state.sseConnection.onerror = (e) => {
        console.error('SSE Error:', e);
        closeSSE();
        spinner.classList.add('hidden');
        runBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
    };
}

function closeSSE() {
    if (state.sseConnection) {
        state.sseConnection.close();
        state.sseConnection = null;
        document.getElementById('console-spinner').classList.add('hidden');
        const runBtn = document.getElementById('btn-run-current-stage');
        if (runBtn) runBtn.disabled = false;
        const stopBtn = document.getElementById('btn-stop-pipeline');
        if (stopBtn) stopBtn.disabled = true;
    }
}

function stopPipeline() {
    if (!state.currentProjectName) return;
    const stopBtn = document.getElementById('btn-stop-pipeline');
    if (stopBtn) stopBtn.disabled = true;
    
    API.stopStage(state.currentProjectName).then(res => {
        if (res.status === 'success') {
            showToast(res.message, 'warning');
            closeSSE();
            document.getElementById('console-spinner').classList.add('hidden');
            const runBtn = document.getElementById('btn-run-current-stage');
            if (runBtn) runBtn.disabled = false;
            reloadProjectDetails();
        } else {
            showToast('Lỗi khi dừng: ' + res.message, 'danger');
            if (stopBtn) stopBtn.disabled = false;
        }
    }).catch(err => {
        showToast(err, 'danger');
        if (stopBtn) stopBtn.disabled = false;
    });
}

let lastReloadTime = 0;
function throttleReloadProjectDetails() {
    const now = Date.now();
    if (now - lastReloadTime > 2000) { // Tối đa 2 giây 1 lần
        lastReloadTime = now;
        reloadProjectDetails();
    }
}

// 8. RENDER CÁC STAGES RIÊNG BIỆT (BÊN PHẢI WORKSPACE)

// Giai đoạn 3: Giọng đọc & Timing
function renderStage3Timing(details) {
    const audioContainer = document.getElementById('ws-audio-player-container');
    if (details.voice_exists) {
        audioContainer.innerHTML = `
            <audio controls src="/api/projects/${details.info.project_name}/file?path=voice.mp3"></audio>
        `;
    } else {
        audioContainer.innerHTML = `
            <p class="no-audio-text"><i class="fa-solid fa-volume-xmark"></i> Chưa tạo file giọng đọc voice.mp3</p>
        `;
    }

    const tbody = document.getElementById('ws-timing-table-body');
    if (details.timing && details.timing.length > 0) {
        let html = '';
        details.timing.forEach(t => {
            const min = Math.floor(t.start / 60);
            const sec = (t.start % 60).toFixed(2);
            const displayTime = `${min.toString().padStart(2, '0')}:${sec.toString().padStart(5, '0').replace('.', ':')}`;
            html += `
                <tr>
                    <td class="text-muted font-mono">#${t.index}</td>
                    <td class="font-mono text-accent">${displayTime}</td>
                    <td>${t.text}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
    } else {
        tbody.innerHTML = `
            <tr>
                <td colspan="3" class="text-center">Chưa có dữ liệu timing. Hãy chạy Giai đoạn 3.</td>
            </tr>
        `;
    }
}

// Giai đoạn 4: Prompts list
function renderStage4Prompts(details) {
    const list = document.getElementById('ws-prompts-editor-list');
    if (details.prompts && details.prompts.length > 0) {
        let html = '';
        details.prompts.forEach((p, idx) => {
            html += `
                <div class="prompt-item-card glass-card" data-index="${idx}">
                    <div class="prompt-item-header">
                        <span class="prompt-item-index"><i class="fa-regular fa-image"></i> Hình ảnh số ${idx}</span>
                        <span class="prompt-item-timing font-mono"><i class="fa-regular fa-clock"></i> ${p.timestamp}</span>
                    </div>
                    <div class="prompt-sentence-preview">${p.sentence}</div>
                    <textarea rows="3" class="prompt-edit-textarea" placeholder="Nhập prompt chi tiết tại đây...">${p.prompt}</textarea>
                </div>
            `;
        });
        list.innerHTML = html;
    } else {
        list.innerHTML = `
            <p class="text-center" style="color: var(--text-muted); padding: 40px 0;">
                Chưa có dữ liệu prompts. Hãy chạy Giai đoạn 4 để sinh tự động.
            </p>
        `;
    }
}

function gatherPromptsFromUI() {
    const prompts = [];
    document.querySelectorAll('#ws-prompts-editor-list .prompt-item-card').forEach(card => {
        const index = parseInt(card.getAttribute('data-index'));
        const timestamp = card.querySelector('.prompt-item-timing').textContent.trim();
        const sentence = card.querySelector('.prompt-sentence-preview').textContent.trim();
        const promptText = card.querySelector('.prompt-edit-textarea').value.trim();
        
        prompts.push({
            index: index,
            timestamp: timestamp,
            sentence: sentence,
            prompt: promptText
        });
    });
    return prompts;
}

// Giai đoạn 5: Grid ảnh & Upload
function renderStage5Images(details) {
    const modeSelect = document.getElementById('cfg-img-mode-select');
    if (modeSelect) {
        modeSelect.value = details.info.image_mode || 'export';
    }

    const profileSelect = document.getElementById('cfg-img-profile-select');
    if (profileSelect && state.profiles) {
        profileSelect.innerHTML = '';
        state.profiles.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.profile_id;
            opt.textContent = p.profile_name;
            profileSelect.appendChild(opt);
        });
        profileSelect.value = details.info.active_profile || 'ancient_history';
    }

    const grid = document.getElementById('ws-images-grid');
    const isExportMode = (details.info.image_mode || 'export') === 'export';
    document.getElementById('imagefx-instructions').style.display = isExportMode ? 'block' : 'none';

    const chromeRow = document.getElementById('chrome-profile-config-row');
    if (chromeRow) {
        chromeRow.style.display = isExportMode ? 'flex' : 'none';
    }
    populateChromeProfilesDropdown();

    if (details.prompts && details.prompts.length > 0) {
        let html = '';
        details.prompts.forEach((p, idx) => {
            const imgData = details.image_map && details.image_map[idx.toString()];
            const versions = imgData ? imgData.versions : [];
            const activeImageName = imgData ? imgData.active : null;
            
            const imageExists = activeImageName !== null && versions.length > 0;
            const activeVersion = (details.info.active_image_versions && 
                                   details.info.active_image_versions[idx.toString()]) !== undefined ? 
                                   parseInt(details.info.active_image_versions[idx.toString()]) : 0;

            html += `
                <div class="image-box-card glass-card" data-index="${idx}">
                    <div class="image-preview-wrapper" id="img-wrapper-${idx}">
                        <span class="image-box-index">Ảnh #${idx}</span>
                        ${imageExists ? `
                            <div class="image-stacked-container">
                                ${versions.map((v_file, v_idx) => {
                                    const isActive = v_idx === activeVersion;
                                    let layerClass = '';
                                    if (isActive) {
                                        layerClass = 'active';
                                    } else {
                                        const diff = (v_idx - activeVersion + versions.length) % versions.length;
                                        if (diff === 1) layerClass = 'layer-1';
                                        else if (diff === 2) layerClass = 'layer-2';
                                        else layerClass = 'layer-3';
                                    }
                                    const vSrc = `/api/projects/${details.info.project_name}/file?path=images/${v_file}&t=${Date.now()}`;
                                    return `<img src="${vSrc}" class="stacked-img ${layerClass}" alt="v${v_idx}" id="img-view-${idx}-${v_idx}">`;
                                }).join('')}
                            </div>
                            <span class="image-version-indicator">v${activeVersion + 1}/${versions.length}</span>
                            ${versions.length > 1 ? `
                                <button class="stacked-next-btn" onclick="cycleImage(${idx}, event)">
                                    <i class="fa-solid fa-chevron-right"></i> Next
                                </button>
                            ` : ''}
                        ` : `
                            <div class="image-upload-dropzone" onclick="triggerFileInput(${idx})">
                                <i class="fa-solid fa-cloud-arrow-up"></i>
                                <span>Thêm ảnh</span>
                            </div>
                        `}
                        <!-- Hidden input file for upload -->
                        <input type="file" id="file-input-${idx}" class="hidden" accept="image/png" onchange="handleFileSelect(event, ${idx})">
                    </div>
                    <div class="image-box-controls">
                        <button class="image-box-btn" onclick="copyPromptToClipboard(${idx})">
                            <i class="fa-solid fa-copy"></i> Copy Prompt
                        </button>
                        ${imageExists ? `
                            <button class="image-box-btn" onclick="triggerFileInput(${idx})">
                                <i class="fa-solid fa-rotate"></i> Đổi ảnh
                            </button>
                        ` : `
                            <button class="image-box-btn" style="opacity:0.3; cursor:default;" disabled>
                                <i class="fa-solid fa-ban"></i> Chưa có
                            </button>
                        `}
                    </div>
                </div>
            `;
        });
        grid.innerHTML = html;
        
        // Cài đặt drag and drop cho mỗi card
        setTimeout(() => {
            details.prompts.forEach((p, idx) => {
                setupDragAndDrop(idx);
            });
        }, 100);
        
    } else {
        grid.innerHTML = `
            <p class="text-center" style="grid-column: span 3; color: var(--text-muted); padding: 40px 0;">
                Chưa có dữ liệu prompts. Vui lòng hoàn thành Giai đoạn 4 trước.
            </p>
        `;
    }
}

// Xoay vòng đổi ảnh phiên bản hoạt động chính
function cycleImage(index, event) {
    if (event) event.stopPropagation(); // Ngăn sự kiện click lan truyền lên wrapper (nhầm kích hoạt input file)
    
    const imgData = state.currentProject.image_map && state.currentProject.image_map[index.toString()];
    if (!imgData || !imgData.versions || imgData.versions.length <= 1) return;
    
    // Lấy version active hiện tại (nếu chưa lưu mặc định là 0)
    const activeVersion = (state.currentProject.info.active_image_versions && 
                           state.currentProject.info.active_image_versions[index.toString()]) !== undefined ? 
                           parseInt(state.currentProject.info.active_image_versions[index.toString()]) : 0;
                           
    const nextVersion = (activeVersion + 1) % imgData.versions.length;
    
    // Gọi API để thiết lập ảnh hoạt động chính
    fetch(`/api/projects/${state.currentProjectName}/set-active-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            index: index,
            version: nextVersion
        })
    })
    .then(r => r.json())
    .then(res => {
        if (res.status === 'success') {
            // Cập nhật trạng thái trong state local để chuẩn hóa
            if (!state.currentProject.info.active_image_versions) {
                state.currentProject.info.active_image_versions = {};
            }
            state.currentProject.info.active_image_versions[index.toString()] = nextVersion;
            
            // Cập nhật trực tiếp các class CSS trên DOM để tạo hiệu ứng chuyển đổi xoay mượt mà
            const versions = imgData.versions;
            const card = document.querySelector(`.image-box-card[data-index="${index}"]`);
            if (card) {
                const indicator = card.querySelector('.image-version-indicator');
                if (indicator) {
                    indicator.textContent = `v${nextVersion + 1}/${versions.length}`;
                }
                
                versions.forEach((v_file, v_idx) => {
                    const imgEl = card.querySelector(`#img-view-${index}-${v_idx}`);
                    if (imgEl) {
                        imgEl.className = 'stacked-img'; // Reset
                        const isActive = v_idx === nextVersion;
                        if (isActive) {
                            imgEl.classList.add('active');
                        } else {
                            const diff = (v_idx - nextVersion + versions.length) % versions.length;
                            if (diff === 1) imgEl.classList.add('layer-1');
                            else if (diff === 2) imgEl.classList.add('layer-2');
                            else imgEl.classList.add('layer-3');
                        }
                    }
                });
            }
            showToast(`Đã chọn bản v${nextVersion} làm ảnh chính ghép video!`, 'success');
        } else {
            showToast('Lỗi khi thiết lập ảnh hoạt động', 'danger');
        }
    })
    .catch(e => {
        console.error(e);
        showToast('Lỗi kết nối máy chủ!', 'danger');
    });
}

// Drag & drop file uploads
function setupDragAndDrop(index) {
    const wrapper = document.getElementById(`img-wrapper-${index}`);
    if (!wrapper) return;

    wrapper.addEventListener('dragover', (e) => {
        e.preventDefault();
        wrapper.classList.add('dragover');
    });

    wrapper.addEventListener('dragleave', () => {
        wrapper.classList.remove('dragover');
    });

    wrapper.addEventListener('drop', (e) => {
        e.preventDefault();
        wrapper.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadImageFile(files[0], index);
        }
    });
}

function triggerFileInput(index) {
    document.getElementById(`file-input-${index}`).click();
}

function handleFileSelect(event, index) {
    const files = event.target.files;
    if (files.length > 0) {
        uploadImageFile(files[0], index);
    }
}

function uploadImageFile(file, index) {
    if (file.type !== 'image/png') {
        showToast('Vui lòng chỉ tải lên ảnh định dạng PNG (.png)!', 'warning');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    showToast(`Đang upload ảnh ${index}.png...`, 'info');

    fetch(`/api/projects/${state.currentProjectName}/upload-image?index=${index}`, {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(res => {
        if (res.status === 'success') {
            showToast(res.message, 'success');
            reloadProjectDetails(); // Tải lại chi tiết dự án để vẽ lại grid ảnh chồng và versions
        } else {
            showToast('Lỗi khi tải ảnh lên!', 'danger');
        }
    })
    .catch(() => {
        showToast('Lỗi kết nối upload!', 'danger');
    });
}

// Copy prompt của ảnh vào Clipboard
function copyPromptToClipboard(index) {
    if (!state.currentProject || !state.currentProject.prompts) return;
    const promptObj = state.currentProject.prompts[index];
    if (!promptObj) return;

    const textToCopy = promptObj.prompt;
    navigator.clipboard.writeText(textToCopy).then(() => {
        showToast(`Đã copy prompt của ảnh #${index} vào clipboard!`, 'success');
    }).catch(err => {
        console.error('Lỗi copy:', err);
    });
}

// Giai đoạn 6: Video thành phẩm
function renderStage6Video(details) {
    const container = document.getElementById('ws-video-player-container');
    const vName = details.video_filename || 'final_video.mp4';
    if (details.video_exists) {
        container.innerHTML = `
            <video controls src="/api/projects/${details.info.project_name}/file?path=${vName}"></video>
            <div style="margin-top: 16px;">
                <a href="/api/projects/${details.info.project_name}/file?path=${vName}" download="${vName}" class="btn btn-primary">
                    <i class="fa-solid fa-download"></i> Tải xuống video thành phẩm
                </a>
            </div>
        `;
    } else {
        container.innerHTML = `
            <div class="video-placeholder">
                <i class="fa-solid fa-video-slash"></i>
                <p>Chưa dựng video ${vName}. Hãy bấm nút chạy Giai đoạn 6 ở bảng bên trái.</p>
            </div>
        `;
    }
}

// 9. TIỆN ÍCH DÙNG CHUNG
function formatDate(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString('vi-VN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getValue(id) {
    return document.getElementById(id).value;
}

function setValue(id, val) {
    const elem = document.getElementById(id);
    if (elem) elem.value = val || '';
}

// HIỂN THỊ TOAST NOTIFICATION TRỰC QUAN
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: 'fa-check-circle',
        info: 'fa-info-circle',
        warning: 'fa-exclamation-triangle',
        danger: 'fa-times-circle'
    };
    const icon = icons[type] || 'fa-info-circle';

    let displayMessage = message;
    if (message && typeof message === 'object') {
        displayMessage = message.message || JSON.stringify(message);
    } else if (message === undefined || message === null) {
        displayMessage = 'Lỗi không xác định';
    } else {
        displayMessage = String(message);
    }

    toast.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <span>${displayMessage}</span>
    `;

    container.appendChild(toast);

    // Fade out and remove after 4.5s
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 4500);
}

// 9.5 QUẢN LÝ PROFILE TRÌNH DUYỆT CHROME
function loadChromeProfiles() {
    return fetch('/api/chrome-profiles')
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                state.chromeProfiles = data.profiles;
                populateChromeProfilesDropdown();
            }
        }).catch(err => console.error("Lỗi tải Chrome profiles:", err));
}

function populateChromeProfilesDropdown() {
    const select = document.getElementById('cfg-chrome-profile-select');
    if (!select || !state.chromeProfiles) return;
    
    select.innerHTML = '';
    state.chromeProfiles.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.folder;
        const nameText = p.name !== p.folder ? `${p.name} (${p.folder})` : p.folder;
        opt.textContent = nameText + (p.email ? ` - ${p.email}` : '');
        select.appendChild(opt);
    });
}

// 10. QUẢN LÝ HỒ SƠ KÊNH DNA (PROFILE SELECTOR & CREATION)
function initProfileSelector() {
    const dropdown = document.getElementById('profile-select-dropdown');
    const btnManage = document.getElementById('btn-manage-profiles');
    const modal = document.getElementById('modal-manage-profiles');
    
    const btnClose = document.getElementById('modal-close-manage-profiles');
    const btnCancel = document.getElementById('modal-cancel-manage-profiles');
    
    const tabListBtn = document.getElementById('profile-mode-list-btn');
    const tabAiBtn = document.getElementById('profile-mode-ai-btn');
    const listEditSection = document.getElementById('profile-list-edit-section');
    const createAiSection = document.getElementById('profile-create-ai-section');
    
    const btnSubmitSave = document.getElementById('btn-submit-save-profile');
    const btnSubmitCreate = document.getElementById('btn-submit-create-profile');
    
    let currentSelectedProfile = null;

    // Thiết lập Kênh active và cập nhật toàn diện
    function setActiveProfileAndReload(id) {
        return API.setActiveProfile(id).then(res => {
            if (res.status === 'success') {
                showToast(`Đã chuyển sang Kênh DNA: ${id}`, 'success');
                loadConfiguration();
                if (state.currentProjectName) {
                    reloadProjectDetails();
                }
                return refreshProfiles(id);
            }
        });
    }

    // Nạp danh sách profile và active profile
    function refreshProfiles(activeIdToSet = null) {
        return Promise.all([API.getProfiles(), API.getActiveProfile()]).then(([profiles, active]) => {
            state.profiles = profiles;
            state.activeProfile = active;
            
            const activeId = activeIdToSet || active.profile_id;
            
            // Render main dropdown
            dropdown.innerHTML = '';
            profiles.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.profile_id;
                opt.textContent = p.profile_name;
                if (p.profile_id === activeId) {
                    opt.selected = true;
                }
                dropdown.appendChild(opt);
            });
            
            if (activeId) {
                dropdown.value = activeId;
            }

            // Đồng bộ sang Hồ sơ Kênh DNA trong thiết lập (cfg-img-profile-select)
            const profileSelect = document.getElementById('cfg-img-profile-select');
            if (profileSelect) {
                profileSelect.innerHTML = '';
                profiles.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.profile_id;
                    opt.textContent = p.profile_name;
                    if (p.profile_id === activeId) {
                        opt.selected = true;
                    }
                    profileSelect.appendChild(opt);
                });
                if (activeId) {
                    profileSelect.value = activeId;
                }
            }
            
            renderModalProfilesList();
        });
    }

    // Khi chọn profile khác từ dropdown
    dropdown.addEventListener('change', (e) => {
        const id = e.target.value;
        setActiveProfileAndReload(id);
    });

    // Mở modal
    btnManage.addEventListener('click', () => {
        modal.classList.add('active');
        switchModalTab('list');
        currentSelectedProfile = null;
        refreshProfiles();
    });

    const closeModal = () => modal.classList.remove('active');
    btnClose.addEventListener('click', closeModal);
    btnCancel.addEventListener('click', closeModal);

    // Chuyển tab modal
    tabListBtn.addEventListener('click', () => switchModalTab('list'));
    tabAiBtn.addEventListener('click', () => switchModalTab('ai'));

    function switchModalTab(tab) {
        if (tab === 'list') {
            tabListBtn.classList.add('active');
            tabAiBtn.classList.remove('active');
            listEditSection.classList.add('active');
            createAiSection.classList.remove('active');
            
            btnSubmitSave.classList.remove('hidden');
            btnSubmitCreate.classList.add('hidden');
        } else {
            tabListBtn.classList.remove('active');
            tabAiBtn.classList.add('active');
            listEditSection.classList.remove('active');
            createAiSection.classList.add('active');
            
            btnSubmitSave.classList.add('hidden');
            btnSubmitCreate.classList.remove('hidden');
        }
    }

    function renderModalProfilesList() {
        const container = document.getElementById('profiles-list-container');
        container.innerHTML = '';
        
        state.profiles.forEach(p => {
            const isActive = state.activeProfile && p.profile_id === state.activeProfile.profile_id;
            const isEditing = currentSelectedProfile && p.profile_id === currentSelectedProfile.profile_id;
            const activeClass = isActive ? 'active' : '';
            const borderStyle = isEditing ? 'border: 1px dashed var(--accent);' : '';
            
            const row = document.createElement('div');
            row.className = `profile-item-row ${activeClass}`;
            row.style = `cursor: pointer; margin-bottom: 6px; ${borderStyle}`;
            row.innerHTML = `
                <div>
                    <strong>${p.profile_name} (${p.profile_id})</strong>
                    <span style="font-size: 11px; color: var(--text-muted); display: block;">${p.profile_description}</span>
                </div>
                <div>
                    ${isActive ? '<span class="badge badge-success btn-small">Đang chạy</span>' : `<button class="btn btn-secondary btn-small btn-activate-profile" data-id="${p.profile_id}">Kích hoạt</button>`}
                </div>
            `;
            
            row.addEventListener('click', (e) => {
                if (e.target.classList.contains('btn-activate-profile')) return;
                selectProfileForEdit(p.profile_id);
            });
            
            container.appendChild(row);
        });
        
        // Gắn sự kiện nút Kích hoạt
        container.querySelectorAll('.btn-activate-profile').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-id');
                API.setActiveProfile(id).then(res => {
                    if (res.status === 'success') {
                        showToast(`Đã kích hoạt hồ sơ kênh: ${id}`, 'success');
                        refreshProfiles(id);
                        loadConfiguration();
                        if (state.currentProjectName) {
                            reloadProjectDetails();
                        }
                    }
                });
            });
        });
        
        // Mặc định chọn profile active để hiển thị
        if (!currentSelectedProfile && state.activeProfile) {
            selectProfileForEdit(state.activeProfile.profile_id);
        }
    }

    function selectProfileForEdit(profileId) {
        const profile = state.profiles.find(p => p.profile_id === profileId);
        if (!profile) return;
        
        currentSelectedProfile = profile;
        renderModalProfilesList();
        
        setValue('profile-edit-name', profile.profile_name);
        setValue('profile-edit-desc', profile.profile_description);
        setValue('profile-edit-kb', profile.CHANNEL_KNOWLEDGE_BASE || '');
        setValue('profile-edit-visual', profile.VISUAL_STYLE_DNA || '');
        setValue('profile-edit-ideas', profile.PROPOSED_IDEAS || '');
    }

    // Lưu chỉnh sửa DNA
    btnSubmitSave.addEventListener('click', () => {
        if (!currentSelectedProfile) {
            showToast('Chưa chọn hồ sơ nào để lưu!', 'warning');
            return;
        }
        
        const updatedProfile = {
            ...currentSelectedProfile,
            profile_name: getValue('profile-edit-name').trim(),
            profile_description: getValue('profile-edit-desc').trim(),
            CHANNEL_KNOWLEDGE_BASE: getValue('profile-edit-kb'),
            VISUAL_STYLE_DNA: getValue('profile-edit-visual'),
            PROPOSED_IDEAS: getValue('profile-edit-ideas')
        };
        
        if (!updatedProfile.profile_name) {
            showToast('Tên hồ sơ không được để trống!', 'warning');
            return;
        }
        
        btnSubmitSave.disabled = true;
        
        API.createProfile({
            profile_id: updatedProfile.profile_id,
            profile_name: updatedProfile.profile_name,
            profile_description: updatedProfile.profile_description,
            use_ai: false,
            profile_data: updatedProfile
        }).then(res => {
            btnSubmitSave.disabled = false;
            if (res.status === 'success') {
                showToast(`Đã lưu cấu hình Kênh '${updatedProfile.profile_name}'!`, 'success');
                refreshProfiles(updatedProfile.profile_id).then(() => {
                    loadConfiguration();
                    if (state.currentProjectName) {
                        reloadProjectDetails();
                    }
                });
            } else {
                showToast('Lỗi khi lưu cấu hình hồ sơ', 'danger');
            }
        }).catch(err => {
            btnSubmitSave.disabled = false;
            showToast('Lỗi kết nối máy chủ', 'danger');
        });
    });

    document.getElementById('btn-analyze-profile-url').addEventListener('click', () => {
        const url = getValue('profile-new-url').trim();
        if (!url) {
            showToast('Vui lòng nhập Link video/playlist mẫu trước!', 'warning');
            return;
        }

        const loadingBox = document.getElementById('profile-ai-loading');
        const btn = document.getElementById('btn-analyze-profile-url');
        
        btn.disabled = true;
        loadingBox.classList.remove('hidden');
        
        fetch('/api/profiles/analyze-style', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        }).then(r => {
            if (!r.ok) return r.json().then(err => { throw new Error(err.detail || 'Lỗi khi phân tích link') });
            return r.json();
        }).then(res => {
            btn.disabled = false;
            loadingBox.classList.add('hidden');
            
            if (res.status === 'success') {
                showToast('Đã phân tích phong cách thành công! Hãy kiểm tra các thông tin tự điền bên dưới.', 'success');
                setValue('profile-new-id', res.suggested_id);
                setValue('profile-new-name', res.suggested_name);
                setValue('profile-new-desc', res.suggested_description);
                setValue('profile-new-prompt', res.suggested_concept_prompt);
            } else {
                showToast('Không thể phân tích phong cách từ URL này', 'danger');
            }
        }).catch(err => {
            btn.disabled = false;
            loadingBox.classList.add('hidden');
            showToast(err || 'Lỗi kết nối máy chủ', 'danger');
        });
    });

    // Tạo kênh mới bằng AI
    btnSubmitCreate.addEventListener('click', () => {
        const id = getValue('profile-new-id').trim();
        const name = getValue('profile-new-name').trim();
        const desc = getValue('profile-new-desc').trim();
        const url = getValue('profile-new-url').trim();
        const prompt = getValue('profile-new-prompt').trim();
        
        if (!id || !name || !desc || !prompt) {
            showToast('Vui lòng điền đầy đủ tất cả các trường để AI sinh DNA!', 'warning');
            return;
        }
        
        const loadingBox = document.getElementById('profile-ai-loading');
        
        btnSubmitCreate.disabled = true;
        loadingBox.classList.remove('hidden');
        
        API.createProfile({
            profile_id: id,
            profile_name: name,
            profile_description: desc,
            use_ai: true,
            ai_prompt: prompt,
            reference_url: url
        }).then(res => {
            btnSubmitCreate.disabled = false;
            loadingBox.classList.add('hidden');
            
            if (res.status === 'success') {
                showToast(`AI đã thiết kế DNA thành công cho Kênh '${name}'!`, 'success');
                setValue('profile-new-id', '');
                setValue('profile-new-name', '');
                setValue('profile-new-desc', '');
                setValue('profile-new-url', '');
                setValue('profile-new-prompt', '');
                
                switchModalTab('list');
                setActiveProfileAndReload(res.profile_id).then(() => {
                    selectProfileForEdit(res.profile_id);
                });
            } else {
                showToast('Lỗi AI sinh DNA kênh', 'danger');
            }
        }).catch(err => {
            btnSubmitCreate.disabled = false;
            loadingBox.classList.add('hidden');
            showToast('Không thể kết nối hoặc lỗi timeout từ AI', 'danger');
            console.error(err);
        });
    });

    // Khởi tạo ban đầu
    refreshProfiles();
}
