/* =============================================================
   CONTENT.JS — Chrome Extension cho Google ImageFX
   Tự động hóa lấy prompts từ Dashboard và upload ảnh trực tiếp
   ============================================================= */

// Khởi tạo Floating UI
const seenImageUrls = new Set();
let activeProject = null;
let isRunning = false;
let currentPromptIndex = 0;
let dashboardUrl = 'http://127.0.0.1:8085';
let expectedImageCount = 2; // Mặc định là 2 ảnh (theo phản hồi của người dùng)

// Lấy địa chỉ host hợp lệ từ localStorage
function getValidatedHost() {
    const saved = localStorage.getItem('imagefx_automator_host');
    if (saved && (saved.startsWith('http://') || saved.startsWith('https://'))) {
        return saved.trim();
    }
    return 'http://127.0.0.1:8085';
}

// Tạo và nhúng Floating Panel vào ImageFX
function createUI() {
    // Nếu UI đã tồn tại thì không tạo lại
    if (document.getElementById('imagefx-automator-panel')) return;

    // Đọc số ảnh mong đợi lưu trữ trong localStorage nếu có
    const savedCount = localStorage.getItem('imagefx_expected_count');
    if (savedCount) {
        expectedImageCount = parseInt(savedCount);
    }

    dashboardUrl = getValidatedHost();

    const panel = document.createElement('div');
    panel.id = 'imagefx-automator-panel';
    panel.className = 'automator-panel';
    panel.innerHTML = `
        <div class="automator-header">
            <span class="automator-title">🎨 ImageFX Automator</span>
            <button class="automator-minimize-btn" id="automator-min-btn">−</button>
        </div>
        <div class="automator-body" id="automator-body">
            <div class="automator-row">
                <input type="text" id="automator-host-input" value="${dashboardUrl}" placeholder="Dashboard Host">
                <button class="automator-btn" id="automator-connect-btn">Kết nối</button>
            </div>
            
            <div class="automator-project-info" id="automator-project-info">
                Chưa kết nối với Dashboard Doodle Video.
            </div>

            <div class="automator-controls hidden" id="automator-controls">
                <div class="automator-mode-select" style="margin-top: 8px;">
                    <span style="color: #9ca3af; font-size: 11px; margin-right: 8px;">Số ảnh/prompt:</span>
                    <label>
                        <input type="radio" name="expected-count" value="2" ${expectedImageCount === 2 ? 'checked' : ''}> 2 ảnh
                    </label>
                    <label style="margin-left: 10px;">
                        <input type="radio" name="expected-count" value="4" ${expectedImageCount === 4 ? 'checked' : ''}> 4 ảnh
                    </label>
                </div>
                
                <div class="automator-actions-row" style="margin-top: 8px;">
                    <button class="automator-btn btn-success" id="automator-start-btn">Bắt đầu chạy</button>
                    <button class="automator-btn btn-danger hidden" id="automator-stop-btn">Dừng</button>
                    <button class="automator-btn btn-warning" id="automator-retry-btn" title="Xóa ảnh cũ và sinh lại ảnh cho prompt hiện tại">Thử lại</button>
                </div>
            </div>

            <div class="automator-logs" id="automator-logs">
                [Hệ thống] Nhấp "Kết nối" để tải kịch bản dự án...
            </div>

            <div class="automator-prompts-list hidden" id="automator-prompts-list">
                <!-- Danh sách prompts kết nối -->
            </div>
        </div>
    `;

    document.body.appendChild(panel);

    // Bind events
    document.getElementById('automator-connect-btn').addEventListener('click', connectDashboard);
    document.getElementById('automator-min-btn').addEventListener('click', toggleMinimize);
    document.getElementById('automator-start-btn').addEventListener('click', startAutomation);
    document.getElementById('automator-stop-btn').addEventListener('click', stopAutomation);
    document.getElementById('automator-retry-btn').addEventListener('click', handleRetryCurrentPrompt);
    
    // Lắng nghe sự thay đổi số ảnh mong đợi
    document.querySelectorAll('input[name="expected-count"]').forEach(el => {
        el.addEventListener('change', (e) => {
            expectedImageCount = parseInt(e.target.value);
            localStorage.setItem('imagefx_expected_count', expectedImageCount);
            log(`Đã đổi số ảnh mong đợi mỗi prompt thành: ${expectedImageCount} ảnh`, 'warning');
        });
    });

    // Đồng bộ giá trị host
    document.getElementById('automator-host-input').value = dashboardUrl;
}

// Ẩn/Hiện Panel
function toggleMinimize() {
    const panel = document.getElementById('imagefx-automator-panel');
    const body = document.getElementById('automator-body');
    const btn = document.getElementById('automator-min-btn');
    if (body.style.display === 'none') {
        body.style.display = 'block';
        if (panel) panel.classList.remove('minimized');
        btn.textContent = '−';
    } else {
        body.style.display = 'none';
        if (panel) panel.classList.add('minimized');
        btn.textContent = '+';
    }
}

// Ghi log ra Panel
function log(msg, type = 'info') {
    const logBox = document.getElementById('automator-logs');
    const time = new Date().toLocaleTimeString('vi-VN', { hour12: false });
    const classMap = { info: '', success: 'text-success', error: 'text-danger', warning: 'text-warning' };
    
    logBox.innerHTML += `<div class="${classMap[type] || ''}">[${time}] ${msg}</div>`;
    logBox.scrollTop = logBox.scrollHeight;
}

// Tìm chỉ mục prompt chưa có ảnh đầu tiên để hỗ trợ chạy tiếp tục (Resume)
function getFirstMissingPromptIndex() {
    if (!activeProject || !activeProject.prompts) return 0;
    for (let i = 0; i < activeProject.prompts.length; i++) {
        const fileName = `${i}.png`;
        // Kiểm tra xem đã có ảnh chính cho prompt này chưa
        const exists = activeProject.existing_images.includes(fileName);
        if (!exists) {
            return i;
        }
    }
    return -1; // Tất cả đã hoàn thành
}

// Kết nối lấy dữ liệu từ Dashboard
async function connectDashboard() {
    const hostInput = document.getElementById('automator-host-input').value.trim();
    if (!hostInput) return;
    
    // Kiểm tra URL hợp lệ để tránh lưu nhầm prompt text vào localStorage
    if (!hostInput.startsWith('http://') && !hostInput.startsWith('https://')) {
        log(`URL không hợp lệ: "${hostInput.substring(0, 50)}...". Phải bắt đầu bằng http:// hoặc https://`, 'error');
        document.getElementById('automator-host-input').value = dashboardUrl; // Khôi phục giá trị cũ
        return;
    }
    
    dashboardUrl = hostInput;
    localStorage.setItem('imagefx_automator_host', dashboardUrl);
    
    log(`Đang kết nối tới Dashboard tại ${dashboardUrl}...`);
    
    try {
        const res = await fetch(`${dashboardUrl}/api/active-project`);
        if (!res.ok) throw new Error("Không phản hồi");
        
        const data = await res.json();
        if (data.status === 'error') {
            log(data.message, 'error');
            return;
        }

        activeProject = data;
        log(`Đã kết nối! Dự án: "${data.info.topic_title}"`, 'success');
        
        // Hiển thị thông tin dự án
        const infoBox = document.getElementById('automator-project-info');
        infoBox.innerHTML = `
            <div><strong>Dự án:</strong> ${data.info.topic_title}</div>
            <div><strong>Thư mục:</strong> <code>output/${data.info.project_name}</code></div>
            <div><strong>Tiến độ:</strong> Đã có ${data.images_count}/${data.prompts.length} ảnh</div>
        `;

        document.getElementById('automator-controls').classList.remove('hidden');
        document.getElementById('automator-prompts-list').classList.remove('hidden');
        
        renderPromptsList();
        
        // Tự động tìm và chọn prompt chưa có ảnh đầu tiên để hỗ trợ chạy tiếp tục (Resume)
        const firstMissing = getFirstMissingPromptIndex();
        selectPrompt(firstMissing !== -1 ? firstMissing : 0);
    } catch (e) {
        log(`Lỗi kết nối Dashboard! Hãy đảm bảo server đang chạy và không bị chặn CORS.`, 'error');
        console.error(e);
    }
}

// Hiển thị danh sách prompts
function renderPromptsList() {
    const container = document.getElementById('automator-prompts-list');
    if (!activeProject || !activeProject.prompts) return;

    container.innerHTML = '';
    
    const title = document.createElement('h4');
    title.textContent = 'Danh sách hình ảnh:';
    container.appendChild(title);

    activeProject.prompts.forEach((p, idx) => {
        const fileName = `${idx}.png`;
        const exists = activeProject.existing_images.includes(fileName);
        const statusClass = exists ? 'status-ready' : 'status-missing';
        const statusText = exists ? 'Đã có' : 'Chưa có';

        const item = document.createElement('div');
        item.className = `automator-prompt-item ${statusClass}`;
        item.id = `prompt-item-${idx}`;
        item.innerHTML = `
            <span class="prompt-idx">#${idx}</span>
            <span class="prompt-text-preview" title="${p.prompt}">${p.prompt.substring(0, 50)}...</span>
            <span class="prompt-status">${statusText}</span>
        `;
        item.addEventListener('click', () => {
            selectPrompt(idx);
        });
        container.appendChild(item);
    });
}

// Chọn một prompt cụ thể trên list
async function selectPrompt(idx) {
    currentPromptIndex = idx;
    
    // Cập nhật class active trên UI list
    document.querySelectorAll('.automator-prompt-item').forEach(el => el.classList.remove('active'));
    const activeItem = document.getElementById(`prompt-item-${idx}`);
    if (activeItem) activeItem.classList.add('active');

    // Điền prompt vào ô input của ImageFX bằng debugger
    log(`Đang chuẩn bị điền prompt #${idx} vào ImageFX bằng debugger...`);
    const success = await fillPromptToImageFX(activeProject.prompts[idx].prompt);
    if (success) {
        log(`Đã chọn prompt #${idx}. Điền và gửi thành công.`);
        return true;
    } else {
        log(`Điền prompt #${idx} thất bại! Hãy kiểm tra console hoặc DevTools.`, 'error');
        return false;
    }
}

// Điền prompt vào Textarea hoặc ô Chat của ImageFX / Google Flow bằng chrome.debugger
async function fillPromptToImageFX(text) {
    // 1. Thử tìm ô Slate.js Editor trước (của Google Flow / Google Labs mới)
    const slateEditor = document.querySelector('[data-slate-editor="true"]') || 
                        document.querySelector('div[role="textbox"][contenteditable="true"]');
                        
    let inputEl = null;
    if (slateEditor && !slateEditor.closest('.automator-panel')) {
        inputEl = slateEditor;
    }
    
    // 2. Fallback: Quét các ô nhập liệu thông thường (loại trừ ô tìm kiếm và panel của ta)
    if (!inputEl) {
        const textareas = Array.from(document.querySelectorAll('textarea'));
        const editables = Array.from(document.querySelectorAll('[contenteditable="true"]'));
        const inputs = Array.from(document.querySelectorAll('input[type="text"]')).filter(el => 
            el.getAttribute('data-testid') !== 'search-input' && !el.className.includes('search')
        );
        const textboxes = Array.from(document.querySelectorAll('[role="textbox"]'));
        
        const candidates = [...textareas, ...editables, ...inputs, ...textboxes].filter(el => {
            // Loại trừ các ô nhập liệu thuộc chính bảng điều khiển của Automator
            if (el.closest('.automator-panel') || el.closest('#imagefx-automator-panel') || el.closest('#aistudio-automator-panel')) {
                return false;
            }
            const rect = el.getBoundingClientRect();
            return rect.width > 150 && rect.height > 20;
        });
        
        if (candidates.length > 0) {
            inputEl = candidates[0];
        }
    }

    if (inputEl) {
        // Tự động đóng hộp thoại/modal tìm kiếm nếu đang bị mở (tránh cản trở click)
        const closeBtn = document.querySelector('button[aria-label*="Đóng"], button[title*="Đóng"], button[class*="close"]');
        if (closeBtn && document.querySelector('[role="dialog"]')) {
            log("Đang đóng hộp thoại phụ để tránh lỗi click nhầm...");
            closeBtn.click();
            await new Promise(r => setTimeout(r, 400));
        }

        // Cuộn ô nhập liệu vào tầm nhìn
        inputEl.scrollIntoView({ block: 'center' });
        await new Promise(r => setTimeout(r, 200));

        const rect = inputEl.getBoundingClientRect();
        // Lấy tọa độ tương đối với viewport của trình duyệt
        const x = Math.round(rect.left + rect.width / 2);
        const y = Math.round(rect.top + rect.height / 2);
        
        log(`Phát hiện ô nhập liệu tại tọa độ: X = ${x}, Y = ${y}. Đang gửi qua debugger...`);
        
        return new Promise((resolve) => {
            chrome.runtime.sendMessage({
                type: "DEBUG_SUBMIT",
                x: x,
                y: y,
                prompt: text
            }, (response) => {
                if (chrome.runtime.lastError) {
                    log(`Lỗi giao tiếp Background: ${chrome.runtime.lastError.message}`, 'error');
                    resolve(false);
                } else if (response && response.ok) {
                    log("Đã giả lập gõ chữ bằng Debugger thành công. Đang kích hoạt nút Tạo/Generate...");
                    setTimeout(() => {
                        const clicked = clickGenerateButton();
                        resolve(clicked);
                    }, 500);
                } else {
                    log(`Lỗi gỡ lỗi: ${response ? response.error : 'Không phản hồi'} (Nhớ ĐÓNG DevTools F12 trên tab Google Flow khi chạy)`, 'error');
                    resolve(false);
                }
            });
        });
    } else {
        log("Không tìm thấy ô nhập prompt nào trên màn hình!", "error");
        return false;
    }
}

// Bấm nút "Generate" hoặc nút gửi (mũi tên) trên ImageFX / Google Flow
function clickGenerateButton() {
    const buttons = Array.from(document.querySelectorAll('button'));
    
    // 1. Tìm nút có chứa icon arrow_forward (nút gửi chính thức của Google Flow)
    let generateBtn = buttons.find(b => b.innerHTML.includes('arrow_forward') || b.querySelector('svg[data-icon="arrow-forward"]'));

    // 2. Tìm nút theo nhãn chữ Generate (tiếng Anh) hoặc Tạo (tiếng Việt)
    if (!generateBtn) {
        generateBtn = buttons.find(b => {
            const txt = (b.textContent || b.innerText || "").trim().toLowerCase();
            return txt === 'generate' || txt === 'tạo';
        });
    }

    // 3. Fallback: Tìm nút có chứa icon send/submit hoặc chứa class/nhãn liên quan
    if (!generateBtn) {
        generateBtn = buttons.find(b => 
            b.innerHTML.includes('send') || 
            b.className.includes('send') || 
            b.className.includes('submit') || 
            b.getAttribute('aria-label') === 'Generate' ||
            b.getAttribute('aria-label') === 'Tạo'
        );
    }

    if (generateBtn) {
        generateBtn.click();
        log("Đã click nút Generate/Tạo!");
        return true;
    }
    
    log("Cảnh báo: Không tìm thấy nút Generate/Tạo trên giao diện. Trình duyệt thử tự gửi bằng phím Enter.", "warning");
    return true; // Vẫn trả về true để tiếp tục chờ xem phím Enter có hoạt động không
}



// Lọc và chỉ giữ lại cụm ảnh mới nằm ở dưới cùng màn hình (thuộc lượt sinh mới nhất)
function getLatestImageGroup(newImgs) {
    if (newImgs.length === 0) return [];
    
    // Tìm vị trí top lớn nhất trong số các ảnh mới
    let maxTop = -1;
    newImgs.forEach(img => {
        const rect = img.getBoundingClientRect();
        if (rect.top > maxTop) {
            maxTop = rect.top;
        }
    });
    
    // Giữ lại các ảnh có vị trí rect.top nằm sát với ảnh dưới cùng nhất (khoảng cách tối đa 250px)
    // Thiết kế này gom được toàn bộ ảnh của lưới sinh hiện tại (nằm thẳng hàng hoặc chia thành 2 hàng)
    const threshold = 250;
    const latestGroup = newImgs.filter(img => {
        const rect = img.getBoundingClientRect();
        return (maxTop - rect.top) <= threshold;
    });
    
    return latestGroup;
}

// So khớp xem ảnh có thuộc về prompt hiện tại không dựa trên alt text
function isImageMatchingPrompt(img, promptText) {
    if (!img.alt) return true; // Nếu không có alt, mặc định khớp (để tương thích)
    if (!promptText) return true;
    
    const altClean = img.alt.toLowerCase().trim();
    const promptClean = promptText.toLowerCase().trim();
    
    // Nếu trùng khớp trực tiếp hoặc chứa nhau
    if (altClean.includes(promptClean) || promptClean.includes(altClean)) {
        return true;
    }
    
    // So khớp từ khóa chính (bỏ các từ nối ngắn)
    const promptWords = promptClean.split(/[\s,.\-_]+/).filter(w => w.length > 3);
    const altWords = altClean.split(/[\s,.\-_]+/).filter(w => w.length > 3);
    
    if (promptWords.length === 0 || altWords.length === 0) return true;
    
    let matchCount = 0;
    altWords.forEach(word => {
        if (promptClean.includes(word)) {
            matchCount++;
        }
    });
    
    // Khớp từ 35% từ khóa trở lên là đạt (vì alt của ImageFX đôi khi ngắn hơn prompt gốc)
    const ratio = matchCount / altWords.length;
    return ratio >= 0.35;
}

// Phát hiện xem các ảnh mới đang được tạo hay đã tạo xong dựa trên ảnh mới xuất hiện
async function waitForImageGeneration(baseline, promptText) {
    log(`Đang chờ Google Flow xử lý và tạo ảnh (Chờ tối thiểu: ${expectedImageCount} ảnh)...`);
    const start = Date.now();
    const maxWaitMs = 60000; // Tối đa chờ 60 giây
    let lastLogTime = 0;
    
    let lastCount = 0;
    let lastChangeTime = Date.now();
    let stableRounds = 0; // Bộ đếm số đợt chờ 10s ổn định
    
    while (Date.now() - start < maxWaitMs) {
        if (!isRunning) return { status: 'error', error: 'user_stopped', message: 'Người dùng dừng' };
        
        // Kiểm tra xem có lỗi hiển thị trên giao diện không
        const error = detectImageFXError();
        if (error) {
            return { status: 'error', error: error.type, message: error.message };
        }
        
        const newImgs = getNewImages(baseline, promptText);
        const activeGroup = getLatestImageGroup(newImgs);
        const currentCount = activeGroup.length;
        
        // 1. Nếu đã đủ số lượng mong đợi (ví dụ 2 hoặc 4 ảnh), hoàn tất ngay lập tức
        if (currentCount >= expectedImageCount) {
            log(`Phát hiện đầy đủ ${currentCount}/${expectedImageCount} ảnh kết quả mới!`);
            await new Promise(r => setTimeout(r, 2000)); // Chờ 2 giây để ảnh hiển thị hoàn toàn
            const finalImgs = getLatestImageGroup(getNewImages(baseline, promptText));
            return { status: 'success', images: finalImgs };
        }
        
        // 2. Nếu đã có ít nhất 1 ảnh mới (nhưng chưa đủ số lượng mong đợi), kiểm tra sự thay đổi để ổn định
        if (currentCount > 0) {
            if (currentCount !== lastCount) {
                log(`Phát hiện ${currentCount}/${expectedImageCount} ảnh mới... đang đợi các ảnh còn lại...`);
                lastCount = currentCount;
                lastChangeTime = Date.now();
                stableRounds = 0; // Reset số đợt chờ nếu số lượng ảnh có thay đổi
            } else {
                // Tùy biến thời gian chờ ổn định:
                // Nếu đã đủ số lượng, chỉ cần chờ 3 giây ổn định.
                if (currentCount >= expectedImageCount) {
                    if (Date.now() - lastChangeTime >= 3000) {
                        log(`Số lượng ảnh mới giữ nguyên ở ${currentCount} trong 3 giây. Xem như hoàn tất.`);
                        await new Promise(r => setTimeout(r, 1000));
                        const finalImgs = getLatestImageGroup(getNewImages(baseline, promptText));
                        return { status: 'success', images: finalImgs };
                    }
                } else {
                    // Nếu chưa đủ số lượng expectedImageCount, chờ ổn định chia làm 3 đợt, mỗi đợt 10 giây (tổng cộng tối đa 30s)
                    if (Date.now() - lastChangeTime >= 10000) {
                        stableRounds++;
                        if (stableRounds < 3) {
                            log(`Số lượng ảnh giữ nguyên ở ${currentCount}/${expectedImageCount} sau 10s. Tiếp tục chờ đợt ${stableRounds + 1}/3...`, 'warning');
                            lastChangeTime = Date.now(); // Reset bộ đếm thời gian đợt mới
                        } else {
                            log(`Đã chờ ổn định đủ 3 đợt (30s) nhưng số lượng ảnh vẫn là ${currentCount}/${expectedImageCount}. Xem như hoàn tất.`);
                            await new Promise(r => setTimeout(r, 1000));
                            const finalImgs = getLatestImageGroup(getNewImages(baseline, promptText));
                            return { status: 'success', images: finalImgs };
                        }
                    }
                }
            }
        }
        
        const elapsed = Math.round((Date.now() - start) / 1000);
        if (elapsed - lastLogTime >= 5) {
            lastLogTime = elapsed;
            if (currentCount === 0) {
                log(`...đang tạo ảnh (${elapsed} giây)...`);
            }
        }
        
        await new Promise(r => setTimeout(r, 500)); // Kiểm tra mỗi 0.5s
    }
    
    log("Quá thời gian chờ (60s). Thử lấy các ảnh mới hiện có...");
    const finalImgs = getLatestImageGroup(getNewImages(baseline, promptText));
    if (finalImgs.length > 0) {
        return { status: 'success', images: finalImgs };
    }
    return { status: 'error', error: 'timeout', message: 'Quá thời gian chờ (60s) không thấy ảnh mới' };
}

// Lấy tất cả ảnh mới phù hợp (không có trong baseline)
function getNewImages(baseline, promptText) {
    const allImages = Array.from(document.querySelectorAll('img'));
    return allImages.filter(img => {
        if (!img.src || baseline.has(img.src)) return false;
        
        const rect = img.getBoundingClientRect();
        // Lọc kích thước ảnh kết quả (thường lớn hơn 100px)
        if (rect.width < 100 || rect.height < 100) return false;
        
        // Loại bỏ ảnh UI và avatar tài khoản Google
        const srcLower = img.src.toLowerCase();
        if (srcLower.includes('avatar') || 
            srcLower.includes('profile') || 
            srcLower.includes('logo') || 
            srcLower.includes('icon') ||
            srcLower.includes('sign-in')) {
            return false;
        }

        // Bổ sung lọc theo prompt alt text để tránh lấy nhầm ảnh của prompt cũ
        if (promptText && !isImageMatchingPrompt(img, promptText)) {
            return false;
        }
        
        return true;
    });
}



// Upload ảnh tự động kèm chỉ mục version
async function uploadImageToServer(imgElement, index, version = null) {
    if (!imgElement || !imgElement.src) {
        log(`Không tìm thấy ảnh kết quả để tải lên cho prompt #${index}!`, 'error');
        return false;
    }

    const verText = version !== null ? ` v${version}` : '';
    log(`Đang tải ảnh #${index}${verText} từ ImageFX và đẩy về Dashboard...`);
    
    try {
        const response = await fetch(imgElement.src);
        const blob = await response.blob();
        
        const formData = new FormData();
        const filename = version !== null ? `${index}_v${version}.png` : `${index}.png`;
        formData.append('file', blob, filename);
        
        let url = `${dashboardUrl}/api/projects/${activeProject.info.project_name}/upload-image?index=${index}`;
        if (version !== null) {
            url += `&version=${version}`;
        }
        
        const res = await fetch(url, {
            method: 'POST',
            body: formData
        });
        
        const data = await res.json();
        if (data.status === 'success') {
            log(`Upload thành công ảnh #${index}${verText}!`, 'success');
            // Cập nhật trạng thái trên UI
            updatePromptStatusUI(index, true);
            return true;
        } else {
            log(`Upload thất bại: ${data.message || 'Lỗi không xác định'}`, 'error');
            return false;
        }
    } catch (e) {
        log(`Lỗi kết nối upload: ${e.message}`, 'error');
        return false;
    }
}

// Cập nhật trạng thái prompt trên UI Extension
function updatePromptStatusUI(index, isSuccess) {
    const item = document.getElementById(`prompt-item-${index}`);
    if (item) {
        item.className = `automator-prompt-item ${isSuccess ? 'status-ready' : 'status-missing'}`;
        item.querySelector('.prompt-status').textContent = isSuccess ? 'Đã có' : 'Chưa có';
    }
}

// Phát hiện lỗi từ giao diện ImageFX (Safety block, Rate limit)
function detectImageFXError() {
    const textElements = Array.from(document.querySelectorAll('div, span, p, h1, h2, h3, li'));
    
    for (const el of textElements) {
        if (!el.textContent) continue;
        const text = el.textContent.trim().toLowerCase();
        
        // 1. Kiểm duyệt an toàn (Safety Block)
        if (text.includes("can't generate") || 
            text.includes("say something else") || 
            text.includes("try a different prompt") || 
            text.includes("violate our safety") || 
            text.includes("content warning") ||
            text.includes("không thể tạo ảnh này") || 
            text.includes("vi phạm chính sách")) {
            return { type: 'safety', message: el.textContent.trim() };
        }
        
        // 2. Hạn mức hạn chế (Daily limit/Rate limit)
        if (text.includes("reached your limit") || 
            text.includes("quota exceeded") || 
            text.includes("try again tomorrow") || 
            text.includes("too many requests") ||
            text.includes("đạt giới hạn") || 
            text.includes("vượt quá hạn mức")) {
            return { type: 'limit', message: el.textContent.trim() };
        }
    }
    return null;
}

// Phát âm thanh bip báo hiệu qua Web Audio API khi có lỗi giới hạn
function playAlertSound() {
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        let time = audioContext.currentTime;
        
        const playBeep = (freq, duration, delay) => {
            const osc = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            osc.type = 'sine';
            osc.frequency.value = freq;
            
            gainNode.gain.setValueAtTime(0.1, time + delay);
            gainNode.gain.exponentialRampToValueAtTime(0.01, time + delay + duration);
            
            osc.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            osc.start(time + delay);
            osc.stop(time + delay + duration);
        };
        
        // Bíp bíp bíp
        playBeep(880, 0.2, 0);
        playBeep(880, 0.2, 0.3);
        playBeep(880, 0.4, 0.6);
    } catch (e) {
        console.error("Không thể phát âm thanh cảnh báo:", e);
    }
}

// Bắt đầu quy trình tự động hóa
async function startAutomation() {
    if (!activeProject) {
        alert("Vui lòng kết nối với Dashboard trước!");
        return;
    }

    isRunning = true;
    localStorage.setItem('imagefx_automator_running', 'true');
    document.getElementById('automator-start-btn').classList.add('hidden');
    document.getElementById('automator-stop-btn').classList.remove('hidden');
    
    const mode = 'auto';
    log(`Khởi động tự động hóa. Chế độ: Tự động 100%`, 'warning');

    // Quét sạch các ảnh trên màn hình trước khi bắt đầu tự động hóa để tránh nhận nhầm ảnh cũ
    Array.from(document.querySelectorAll('img')).forEach(img => {
        if (img.src) seenImageUrls.add(img.src);
    });

    let retryCount = 0;

    // Chạy vòng lặp dynamic pull để lấy task từ server
    while (isRunning) {
        let task = null;
        try {
            const res = await fetch(`${dashboardUrl}/api/projects/${activeProject.info.project_name}/next-pending-prompt`);
            if (res.ok) {
                const data = await res.json();
                if (data.status === 'success') {
                    task = data;
                } else {
                    log("Không còn prompt nào cần sinh ảnh hoặc đang bị khóa bởi tab khác.", "info");
                    // Chờ 5 giây rồi thử lại hoặc dừng nếu đã hoàn tất hoàn toàn
                    await new Promise(r => setTimeout(r, 5000));
                    
                    // Reload trạng thái dự án để xem thực tế có còn thiếu ảnh không
                    const refreshRes = await fetch(`${dashboardUrl}/api/active-project`);
                    const refreshData = await refreshRes.json();
                    activeProject = refreshData;
                    
                    const firstMissing = getFirstMissingPromptIndex();
                    if (firstMissing === -1) {
                        log("Chúc mừng! Đã sinh và tải lên thành công toàn bộ ảnh cho dự án!", "success");
                        stopAutomation();
                        break;
                    }
                    continue;
                }
            } else {
                log("Không kết nối được Dashboard để lấy task. Đang thử lại...", "error");
                await new Promise(r => setTimeout(r, 5000));
                continue;
            }
        } catch (e) {
            log(`Lỗi kết nối Dashboard: ${e.message}`, "error");
            await new Promise(r => setTimeout(r, 5000));
            continue;
        }

        if (!isRunning) break;

        const i = task.index;
        currentPromptIndex = i;
        
        // Thêm các ảnh đang hiển thị vào seenImageUrls trước lượt sinh mới để bảo vệ baseline
        Array.from(document.querySelectorAll('img')).forEach(img => {
            if (img.src) seenImageUrls.add(img.src);
        });
        
        const baseline = new Set(seenImageUrls);
        log(`[Task] Bắt đầu sinh ảnh #${i}: "${task.prompt}"`);

        // 2. Điền và gửi prompt
        const filled = await fillPromptToImageFX(task.prompt);
        if (!filled) {
            log(`Lỗi điền prompt #${i}. Đang thử lại...`, "warning");
            await new Promise(r => setTimeout(r, 3000));
            continue;
        }
        
        if (!isRunning) break;

        // 3. Chờ tạo ảnh xong
        const genResult = await waitForImageGeneration(baseline, task.prompt);
        
        if (genResult.status === 'error') {
            if (genResult.error === 'safety') {
                log(`[Kiểm duyệt] Prompt #${i} bị chặn kiểm duyệt!`, 'error');
                if (retryCount < 1) {
                    retryCount++;
                    log(`[Kiểm duyệt] Đang gọi Gemini để tự động viết lại prompt #${i}...`);
                    try {
                        const rwRes = await fetch(`${dashboardUrl}/api/projects/${activeProject.info.project_name}/rewrite-prompt`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ index: i, prompt: task.prompt })
                        });
                        if (rwRes.ok) {
                            const rwData = await rwRes.json();
                            if (rwData.status === 'success') {
                                log(`[Kiểm duyệt] Đã viết lại thành công! Thử sinh lại...`, 'success');
                                await new Promise(r => setTimeout(r, 2000));
                                continue; // Lặp lại vòng lặp để lấy lại prompt này (đã được viết lại sạch hơn)
                            }
                        }
                    } catch (rwErr) {
                        log(`Lỗi gọi API viết lại: ${rwErr.message}`, 'error');
                    }
                }
                
                log(`[Kiểm duyệt] Bỏ qua prompt #${i} để bạn xử lý thủ công sau.`, 'warning');
                retryCount = 0; // Reset
                await new Promise(r => setTimeout(r, 2000));
            } else if (genResult.error === 'limit') {
                log(`[Hạn mức] Đã hết hạn mức sinh ảnh của ngày hôm nay!`, 'error');
                playAlertSound();
                stopAutomation();
                break;
            } else {
                log(`[Timeout/Hủy] ${genResult.message}. Dừng tiến trình để an toàn.`, 'warning');
                stopAutomation();
                break;
            }
        } else {
            // Sinh ảnh thành công
            retryCount = 0; // Reset
            const newImgs = genResult.images;
            
            // Đánh dấu các ảnh mới vừa sinh này là đã xem ngay lập tức để bảo vệ các prompt sau
            newImgs.forEach(img => {
                if (img.src) seenImageUrls.add(img.src);
            });

            log(`Đang tự động tải lên tất cả ${newImgs.length} ảnh vừa sinh cho prompt #${i}...`);
            let allSuccess = true;
            for (let v_idx = 0; v_idx < newImgs.length; v_idx++) {
                const img = newImgs[v_idx];
                const uploaded = await uploadImageToServer(img, i, v_idx);
                if (!uploaded) {
                    allSuccess = false;
                }
            }
            if (!allSuccess) {
                log("Tải ảnh thất bại. Tạm dừng để kiểm tra.", "error");
                stopAutomation();
                break;
            }
        }
        
        // Nghỉ 1.5 giây trước khi chạy prompt tiếp theo
        await new Promise(r => setTimeout(r, 1500));
    }
}

// Dừng tự động hóa
function stopAutomation() {
    isRunning = false;
    localStorage.setItem('imagefx_automator_running', 'false');
    document.getElementById('automator-start-btn').classList.remove('hidden');
    document.getElementById('automator-stop-btn').classList.add('hidden');
    log("Đã dừng tiến trình tự động hóa.", "warning");
    
    // Đóng debugger khi dừng chạy để ẩn thanh thông báo màu vàng
    chrome.runtime.sendMessage({ type: "DEBUG_DETACH" });
}

// Thử lại sinh ảnh cho prompt hiện tại
async function handleRetryCurrentPrompt() {
    if (!activeProject) {
        alert("Vui lòng kết nối với Dashboard trước!");
        return;
    }
    
    const idx = currentPromptIndex;
    log(`[Thử lại] Bắt đầu thử lại cho prompt #${idx}...`, 'warning');
    
    // 1. Dừng tự động hóa hiện tại nếu đang chạy
    stopAutomation();
    await new Promise(r => setTimeout(r, 1000)); // Chờ 1 giây để tiến trình cũ dừng hẳn
    
    // 2. Gọi API server để xóa ảnh cũ của prompt này
    try {
        const res = await fetch(`${dashboardUrl}/api/projects/${activeProject.info.project_name}/delete-image/${idx}`, {
            method: 'POST'
        });
        if (!res.ok) throw new Error("Không thể xóa ảnh cũ trên server");
        log(`[Thử lại] Đã xóa ảnh cũ của prompt #${idx} trên server.`, 'success');
    } catch (e) {
        log(`[Thử lại] Cảnh báo khi xóa ảnh: ${e.message}`, 'warning');
    }
    
    // 3. Quét sạch các ảnh đang hiển thị vào seenImageUrls trước lượt sinh mới để bảo vệ baseline
    Array.from(document.querySelectorAll('img')).forEach(img => {
        if (img.src) seenImageUrls.add(img.src);
    });
    
    // 4. Điền prompt và click Generate
    const promptText = activeProject.prompts[idx].prompt;
    log(`[Thử lại] Đang điền prompt và kích hoạt sinh lại...`);
    const filled = await fillPromptToImageFX(promptText);
    if (!filled) {
        log(`Lỗi điền prompt #${idx} khi thử lại.`, 'error');
        return;
    }
    
    // 5. Khởi động lại tự động hóa từ prompt này
    startAutomation();
}

// =============================================================
//  GOOGLE AI STUDIO AUTOMATION LOGIC
// =============================================================

let isAIStudioRunning = false;
let aiStudioPollTimer = null;

function createAIStudioUI() {
    if (document.getElementById('aistudio-automator-panel')) return;

    dashboardUrl = getValidatedHost();

    const isGemini = window.location.hostname.includes('gemini.google.com');
    const titleText = isGemini ? "🤖 Gemini Web Automator" : "🤖 AI Studio Automator";

    const panel = document.createElement('div');
    panel.id = 'aistudio-automator-panel';
    panel.className = 'automator-panel';
    panel.innerHTML = `
        <div class="automator-header">
            <span class="automator-title">${titleText}</span>
            <button class="automator-minimize-btn" id="aistudio-min-btn">−</button>
        </div>
        <div class="automator-body" id="aistudio-body">
            <div class="automator-row">
                <input type="text" id="aistudio-host-input" value="${dashboardUrl}" placeholder="Dashboard Host">
                <button class="automator-btn" id="aistudio-connect-btn">Kết nối</button>
            </div>
            
            <div class="automator-project-info" id="aistudio-project-info">
                Kết nối với Dashboard để tự động nhận task.
            </div>

            <div class="automator-controls hidden" id="aistudio-controls">
                <div class="automator-actions-row">
                    <button class="automator-btn btn-success" id="aistudio-start-btn">Bắt đầu chạy</button>
                    <button class="automator-btn btn-danger hidden" id="aistudio-stop-btn">Dừng</button>
                </div>
            </div>

            <div class="automator-logs" id="aistudio-logs" style="min-height: 350px;">
                [Hệ thống] Nhấp "Kết nối" để bắt đầu lắng nghe hàng đợi...
            </div>
        </div>
    `;

    document.body.appendChild(panel);

    // Bind events
    document.getElementById('aistudio-connect-btn').addEventListener('click', connectAIStudioDashboard);
    document.getElementById('aistudio-min-btn').addEventListener('click', toggleAIStudioMinimize);
    document.getElementById('aistudio-start-btn').addEventListener('click', startAIStudioAutomation);
    document.getElementById('aistudio-stop-btn').addEventListener('click', stopAIStudioAutomation);
}

function toggleAIStudioMinimize() {
    const panel = document.getElementById('aistudio-automator-panel');
    const body = document.getElementById('aistudio-body');
    const btn = document.getElementById('aistudio-min-btn');
    if (body.style.display === 'none') {
        body.style.display = 'block';
        if (panel) panel.classList.remove('minimized');
        btn.textContent = '−';
    } else {
        body.style.display = 'none';
        if (panel) panel.classList.add('minimized');
        btn.textContent = '+';
    }
}

function logAIStudio(msg, type = 'info') {
    const logBox = document.getElementById('aistudio-logs');
    if (!logBox) return;
    const time = new Date().toLocaleTimeString('vi-VN', { hour12: false });
    const classMap = { info: '', success: 'text-success', error: 'text-danger', warning: 'text-warning' };
    
    logBox.innerHTML += `<div class="${classMap[type] || ''}">[${time}] ${msg}</div>`;
    logBox.scrollTop = logBox.scrollHeight;
}

async function connectAIStudioDashboard() {
    const hostInput = document.getElementById('aistudio-host-input').value.trim();
    if (!hostInput) return;
    
    // Kiểm tra URL hợp lệ để tránh lưu nhầm prompt text vào localStorage
    if (!hostInput.startsWith('http://') && !hostInput.startsWith('https://')) {
        logAIStudio(`URL không hợp lệ: "${hostInput.substring(0, 50)}...". Phải bắt đầu bằng http:// hoặc https://`, 'error');
        document.getElementById('aistudio-host-input').value = dashboardUrl;
        return;
    }
    
    dashboardUrl = hostInput;
    localStorage.setItem('imagefx_automator_host', dashboardUrl);
    
    logAIStudio(`Đang kết nối tới Dashboard tại ${dashboardUrl}...`);
    
    try {
        const res = await fetch(`${dashboardUrl}/api/config`);
        if (!res.ok) throw new Error("Không phản hồi");
        
        logAIStudio(`Đã kết nối thành công với Dashboard!`, 'success');
        document.getElementById('aistudio-project-info').innerHTML = `
            <div><strong>Trạng thái:</strong> Sẵn sàng</div>
            <div><strong>Host:</strong> <code>${dashboardUrl}</code></div>
        `;
        
        document.getElementById('aistudio-controls').classList.remove('hidden');
        
    } catch (e) {
        logAIStudio(`Lỗi kết nối Dashboard! Hãy kiểm tra địa chỉ host.`, 'error');
        console.error(e);
    }
}

async function startAIStudioAutomation() {
    if (isAIStudioRunning) return;
    isAIStudioRunning = true;
    
    document.getElementById('aistudio-start-btn').classList.add('hidden');
    document.getElementById('aistudio-stop-btn').classList.remove('hidden');
    
    logAIStudio("Khởi động lắng nghe hàng đợi Web Gemini từ Dashboard...", "warning");
    runAIStudioLoop();
}

function stopAIStudioAutomation() {
    isAIStudioRunning = false;
    if (aiStudioPollTimer) {
        clearTimeout(aiStudioPollTimer);
        aiStudioPollTimer = null;
    }
    document.getElementById('aistudio-start-btn').classList.remove('hidden');
    document.getElementById('aistudio-stop-btn').classList.add('hidden');
    logAIStudio("Đã dừng tự động hóa AI Studio.", "warning");
}

async function runAIStudioLoop() {
    if (!isAIStudioRunning) return;
    
    try {
        const res = await fetch(`${dashboardUrl}/api/web-gemini/pending`);
        if (res.status === 200) {
            const task = await res.json();
            logAIStudio(`Nhận được task mới: ID=${task.task_id}, Type=${task.task_type}`, 'warning');
            
            // Tạm dừng check loop khi đang xử lý task
            stopAIStudioAutomation();
            
            try {
                const result = await executeAIStudioTask(task.prompt);
                logAIStudio(`Hoàn thành task ${task.task_id}! Đang gửi kết quả...`, 'success');
                await sendTaskResult(task.task_id, result, null);
            } catch (err) {
                logAIStudio(`Lỗi thực thi task ${task.task_id}: ${err.message}`, 'error');
                await sendTaskResult(task.task_id, null, err.message);
            }
            
            // Khởi chạy lại loop sau khi hoàn thành
            startAIStudioAutomation();
            return;
        } else if (res.status === 204) {
            // Không có task, tiếp tục
        }
    } catch (e) {
        logAIStudio(`Lỗi kết nối server Dashboard: ${e.message}`, 'error');
    }
    
    if (isAIStudioRunning) {
        aiStudioPollTimer = setTimeout(runAIStudioLoop, 3000);
    }
}

function findAIStudioInput() {
    const selectors = [
        'rich-textarea div[contenteditable="true"]',
        '.input-area div[contenteditable="true"]',
        'textarea.data-hotkey-target',
        'textarea.inputarea',
        'div.textarea-container textarea',
        'textarea',
        'div[contenteditable="true"]'
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) return el;
    }
    return null;
}

function findAIStudioRunButton() {
    // 1. Tìm bằng text content trước (rất chính xác cho AI Studio mới)
    const buttons = Array.from(document.querySelectorAll('button'));
    const runBtn = buttons.find(b => {
        const txt = b.textContent.trim().toLowerCase().replace(/\s+/g, '');
        // Hỗ trợ: "run", "runctrl+enter", "runctrl", "runprompt"
        return (txt === 'run' || txt === 'runctrl+enter' || txt === 'runctrl' || txt === 'runprompt');
    });
    if (runBtn) return runBtn;

    // 2. Fallback bằng các selector khác (AI Studio & Gemini)
    const selectors = [
        'button.run-button',
        'button[aria-label="Run"]',
        'button[mat-tooltip="Run (Ctrl+Enter)"]',
        'button[aria-label*="Run" i]',
        'button[aria-label*="Send" i]',
        'button[aria-label*="Gửi" i]',
        'button.send-button'
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) return el;
    }
    return null;
}

function findAIStudioStopButton() {
    const selectors = [
        'button.stop-button',
        'button[aria-label="Stop"]',
        'button[aria-label="Cancel"]',
        'button[aria-label*="Stop" i]',
        'button[aria-label*="Cancel" i]',
        'button[aria-label*="Dừng" i]',
        'button[aria-label*="Hủy" i]'
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) return el;
    }
    const buttons = Array.from(document.querySelectorAll('button'));
    const stopBtn = buttons.find(b => {
        const txt = b.textContent.trim().toLowerCase();
        return txt === 'stop' || txt === 'cancel' || txt === 'dừng' || txt === 'hủy' || txt.includes('stop generation');
    });
    if (stopBtn) return stopBtn;
    return null;
}

function getAIStudioResponseText() {
    const selectors = [
        '.model-response-text',
        'ms-markdown',
        '.markdown-content',
        'div.response-container',
        'message-content',
        '.message-content',
        '.markdown',
        'div.markdown'
    ];
    let responses = [];
    for (const sel of selectors) {
        const elList = document.querySelectorAll(sel);
        if (elList && elList.length > 0) {
            responses = Array.from(elList);
            break;
        }
    }
    if (responses.length === 0) {
        responses = Array.from(document.querySelectorAll('ms-markdown, .model-response-text, message-content, .message-content, .markdown'));
    }
    if (responses.length > 0) {
        const lastResponse = responses[responses.length - 1];
        return lastResponse.innerText || lastResponse.textContent || "";
    }
    return "";
}

async function waitForAIStudioGeneration() {
    logAIStudio("Đang chờ sinh kết quả...");
    const maxWaitMs = 10 * 60 * 1000; // 10 phút
    const startWait = Date.now();
    
    let lastTextLength = -1;
    let stableCount = 0;
    
    // Chờ 2 giây đầu tiên để quá trình sinh bắt đầu
    await new Promise(r => setTimeout(r, 2000));
    
    while (Date.now() - startWait < maxWaitMs) {
        const stopBtn = findAIStudioStopButton();
        const text = getAIStudioResponseText();
        
        // Nếu đã đợi hơn 15 giây mà không có phản hồi (text rỗng) và không thấy nút Stop
        if (Date.now() - startWait > 15000 && !stopBtn && text.length === 0) {
            throw new Error("Không khởi động được tiến trình sinh (nút Run hoặc phím tắt Ctrl+Enter không phản hồi).");
        }
        
        // Nếu nút Stop không còn hiển thị nữa
        if (!stopBtn) {
            if (text.length > 0) {
                logAIStudio("Sinh hoàn tất (không thấy nút Stop và đã có text).");
                break;
            }
        }
        
        // Kiểm tra sự ổn định của text
        if (text.length > 0 && text.length === lastTextLength) {
            stableCount++;
            if (stableCount >= 4) {
                logAIStudio("Sinh hoàn tất (độ dài văn bản ổn định).");
                break;
            }
        } else {
            lastTextLength = text.length;
            stableCount = 0;
        }
        
        const elapsedSec = Math.round((Date.now() - startWait) / 1000);
        if (elapsedSec > 0 && elapsedSec % 5 === 0) {
            logAIStudio(`...đang xử lý (${elapsedSec}s) | Độ dài text: ${text.length}...`);
        }
        
        await new Promise(r => setTimeout(r, 1000));
    }
    
    await new Promise(r => setTimeout(r, 1500));
}

async function executeAIStudioTask(prompt) {
    logAIStudio("Bắt đầu xử lý task...");
    
    const textarea = findAIStudioInput();
    if (!textarea) {
        throw new Error("Không tìm thấy ô nhập prompt nào của AI Studio hoặc Gemini!");
    }
    
    logAIStudio("Đang điền prompt vào editor...");
    textarea.focus();
    if (typeof textarea.select === 'function') {
        textarea.select();
    }
    await new Promise(r => setTimeout(r, 200));
    
    document.execCommand('insertText', false, prompt);
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 500));
    
    logAIStudio("Đang gửi yêu cầu (Run)...");
    const runBtn = findAIStudioRunButton();
    if (runBtn) {
        logAIStudio("Tìm thấy nút Run, tiến hành Click...");
        runBtn.click();
        
        // Gửi thêm Ctrl+Enter dự phòng sau 150ms
        setTimeout(() => {
            textarea.dispatchEvent(new KeyboardEvent('keydown', {
                key: 'Enter',
                code: 'Enter',
                keyCode: 13,
                which: 13,
                ctrlKey: true,
                bubbles: true,
                cancelable: true
            }));
        }, 150);
    } else {
        logAIStudio("Không tìm thấy nút Run. Thử bấm Ctrl+Enter dự phòng...", "warning");
        textarea.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            keyCode: 13,
            which: 13,
            ctrlKey: true,
            bubbles: true,
            cancelable: true
        }));
    }
    
    await waitForAIStudioGeneration();
    
    const resultText = getAIStudioResponseText();
    if (!resultText || resultText.trim().length === 0) {
        throw new Error("Không lấy được kết quả sinh từ giao diện!");
    }
    
    logAIStudio(`Lấy kết quả thành công! Độ dài: ${resultText.length} ký tự.`, 'success');
    return resultText;
}

async function sendTaskResult(taskId, result, error) {
    try {
        const res = await fetch(`${dashboardUrl}/api/web-gemini/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: taskId,
                result: result,
                error: error
            })
        });
        if (!res.ok) throw new Error("Gửi kết quả thất bại");
        logAIStudio(`Đã đồng bộ kết quả task ${taskId} lên server!`, 'success');
    } catch (e) {
        logAIStudio(`Lỗi gửi kết quả lên server: ${e.message}`, 'error');
    }
}

// Khởi chạy
setTimeout(async () => {
    const isAIStudio = window.location.hostname.includes('aistudio.google.com') || window.location.hostname.includes('gemini.google.com');
    if (isAIStudio) {
        createAIStudioUI();
    } else {
        createUI();
        // Quét sạch các ảnh trên màn hình khi tải trang lần đầu
        Array.from(document.querySelectorAll('img')).forEach(img => {
            if (img.src) seenImageUrls.add(img.src);
        });

        // Tự động khôi phục tiến trình nếu trang bị F5/Reload trong lúc đang chạy
        const savedRunning = localStorage.getItem('imagefx_automator_running') === 'true';
        dashboardUrl = getValidatedHost();
        // Cập nhật lại ô nhập liệu với URL đã xác thực
        const hostInputEl = document.getElementById('automator-host-input');
        if (hostInputEl) hostInputEl.value = dashboardUrl;

        if (savedRunning) {
            log("Phát hiện tiến trình đang chạy dở trước khi reload. Đang khôi phục...", "warning");
            await connectDashboard();
            if (activeProject) {
                setTimeout(() => {
                    startAutomation();
                }, 2000);
            }
        }
    }
}, 2000);
