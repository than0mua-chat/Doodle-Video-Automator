// ============================================================
//  Doodle Video Automator — sidepanel.js
//  Orchestrator: Coordinates active projects, pulls prompts,
//  sends tasks to the content script, and uploads/downloads images.
// ============================================================

const $ = (id) => document.getElementById(id);
const els = {
  host: $("automator-host-input"),
  connectBtn: $("connect-btn"),
  conn: $("conn"),
  connText: $("connText"),
  projectInfoBlock: $("project-info-block"),
  projectName: $("projectName") || $("project-name"),
  projectNiche: $("project-niche"),
  projectDir: $("project-dir"),
  delayMin: $("delayMin"),
  delayMax: $("delayMax"),
  saveLocal: $("saveLocal"),
  startBtn: $("start-btn"),
  stopBtn: $("stop-btn"),
  retryBtn: $("retry-btn"),
  logsConsole: $("logs-console"),
  progress: $("progress"),
  pfill: $("pfill"),
  queue: $("queue"),
};

let dashboardUrl = "http://127.0.0.1:8085";
let activeProject = null;
let isRunning = false;
let expectedImageCount = 2;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- 1. Logs Printing Helper ----------
function log(message, type = "info") {
  const line = document.createElement("div");
  line.className = `log-line ${type}`;
  
  const time = new Date().toLocaleTimeString();
  line.textContent = `[${time}] ${message}`;
  
  els.logsConsole.appendChild(line);
  els.logsConsole.scrollTop = els.logsConsole.scrollHeight;
  console.log(`[SidePanel ${type}] ${message}`);
}

function clearLogs() {
  els.logsConsole.innerHTML = "";
}

// ---------- 2. Load / Save settings ----------
function saveSettings() {
  chrome.storage.local.set({
    host: els.host.value,
    delayMin: els.delayMin.value,
    delayMax: els.delayMax.value,
    saveLocal: els.saveLocal.checked,
    expectedImageCount: getExpectedImageCount(),
  });
  dashboardUrl = els.host.value.trim().replace(/\/$/, "");
}

async function loadSettings() {
  const s = await chrome.storage.local.get();
  if (s.host) els.host.value = s.host;
  if (s.delayMin) els.delayMin.value = s.delayMin;
  if (s.delayMax) els.delayMax.value = s.delayMax;
  if (s.saveLocal !== undefined) els.saveLocal.checked = s.saveLocal;
  if (s.expectedImageCount) {
    const radio = document.querySelector(`input[name="expected-count"][value="${s.expectedImageCount}"]`);
    if (radio) radio.checked = true;
  }
  dashboardUrl = els.host.value.trim().replace(/\/$/, "");
  updateExpectedImageCount();
}

function getExpectedImageCount() {
  const selected = document.querySelector('input[name="expected-count"]:checked');
  return selected ? parseInt(selected.value) : 2;
}

function updateExpectedImageCount() {
  expectedImageCount = getExpectedImageCount();
  saveSettings();
}

// ---------- 3. Connect and Sync with Dashboard ----------
async function connectDashboard() {
  saveSettings();
  setConn(false, "Đang kết nối tới Dashboard...");
  
  try {
    const res = await fetch(`${dashboardUrl}/api/active-project`);
    if (!res.ok) throw new Error(`Lỗi HTTP ${res.status}`);
    
    const data = await res.json();
    activeProject = data;
    
    // Hiển thị thông tin dự án
    els.projectName.textContent = data.info.project_name || "—";
    els.projectNiche.textContent = data.info.ai_niche_prompt || data.info.active_profile || "—";
    els.projectDir.textContent = data.info.project_dir || `output/${data.info.project_name}`;
    els.projectInfoBlock.style.display = "block";
    
    setConn(true, "Đã kết nối Dashboard");
    log(`Đã kết nối tới dự án: "${data.info.project_name}"`, "success");
    
    renderQueue();
  } catch (e) {
    setConn(false, "Lỗi kết nối Dashboard! Hãy đảm bảo server đang chạy.");
    log(`Lỗi kết nối Dashboard: ${e.message}. Hãy chắc chắn server python đang chạy tại ${dashboardUrl}`, "error");
    els.projectInfoBlock.style.display = "none";
  }
}

function setConn(on, text) {
  els.conn.className = "conn " + (on ? "conn--on" : "conn--off");
  els.connText.textContent = text;
}

// Periodic connection check (if not running)
async function periodicCheck() {
  if (isRunning) return;
  const tab = await getFlowTab();
  if (!tab) {
    setConn(false, "Mở tab Google ImageFX / Google Flow để chuẩn bị");
    return;
  }
  
  // Ping tab to check if content script is injected
  let resp = await sendToTab(tab.id, { type: "PING" });
  if (!resp) {
    // Try to auto-inject content script
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["content.js"],
      });
      await sleep(300);
      resp = await sendToTab(tab.id, { type: "PING" });
    } catch (_) {}
  }
  
  if (resp && resp.ok) {
    if (!activeProject) {
      await connectDashboard();
    } else {
      setConn(true, "Dashboard Sẵn Sàng · Tiện ích Đã Kết Nối");
    }
  } else {
    setConn(false, "F5 lại trang ImageFX rồi thử lại");
  }
}

// ---------- 4. Render Prompts Queue ----------
function renderQueue() {
  if (!activeProject || !activeProject.prompts) {
    els.queue.innerHTML = '<li style="text-align: center; color: var(--muted); padding: 20px 0;">Không có dữ liệu</li>';
    return;
  }
  
  els.queue.innerHTML = "";
  const prompts = activeProject.prompts;
  const imageMap = activeProject.image_map || {};
  
  let doneCount = 0;
  
  prompts.forEach((p, idx) => {
    let promptText = "";
    let promptIndex = idx;
    
    if (typeof p === "string") {
      promptText = p;
    } else if (p && typeof p === "object") {
      promptText = p.prompt || "";
      promptIndex = p.index !== undefined ? p.index : idx;
    }
    
    // Check status based on imageMap
    const mapEntry = imageMap[String(promptIndex)];
    const hasImage = mapEntry && mapEntry.active;
    const status = hasImage ? "done" : "pending";
    if (hasImage) doneCount++;
    
    const li = document.createElement("li");
    li.className = `qitem ${status}`;
    li.id = `qitem-${promptIndex}`;
    li.innerHTML = `
      <span class="num">${promptIndex}</span>
      <span class="txt">${escapeHtml(promptText)}</span>
      <span class="tag ${status}">${status === "done" ? "Đã có" : "Chưa có"}</span>
    `;
    els.queue.appendChild(li);
  });
  
  els.progress.textContent = `${doneCount}/${prompts.length} xong`;
  els.pfill.style.width = prompts.length ? Math.round((doneCount / prompts.length) * 100) + "%" : "0%";
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );
}

// ---------- 5. Locate active Flow/ImageFX tab ----------
async function getFlowTab() {
  const tabs = await chrome.tabs.query({});
  const tab = tabs.find(t => 
    /aitestkitchen\.withgoogle\.com\/tools\/image-fx/i.test(t.url || "") ||
    /labs\.google\/fx\/tools\/flow/i.test(t.url || "") ||
    /labs\.google\/.*\/tools\/flow/i.test(t.url || "")
  ) || null;
  
  if (tab && tab.url && /labs\.google/i.test(tab.url) && !tab.url.includes('/project/')) {
    tab.__isFlowHomepage = true;
  }
  return tab;
}

function sendToTab(tabId, msg) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, msg, async (resp) => {
      if (chrome.runtime.lastError) {
        console.warn("Lỗi sendMessage, có thể content script chưa được inject. Đang tiến hành tự động inject...");
        try {
          // Tự động inject content.js và style.css
          await chrome.scripting.executeScript({
            target: { tabId: tabId },
            files: ["content.js"]
          });
          try {
            await chrome.scripting.insertCSS({
              target: { tabId: tabId },
              files: ["style.css"]
            });
          } catch (_) {}
          
          // Đợi 500ms để script khởi chạy xong và lắng nghe
          await sleep(500);
          
          // Thử gửi lại lần 2
          chrome.tabs.sendMessage(tabId, msg, (resp2) => {
            if (chrome.runtime.lastError) resolve(null);
            else resolve(resp2);
          });
        } catch (injectErr) {
          console.error("Không thể tự động inject content script:", injectErr);
          resolve(null);
        }
      } else {
        resolve(resp);
      }
    });
  });
}

// Helper to convert data URL to Blob
function dataURLToBlob(dataURL) {
  const parts = dataURL.split(';base64,');
  const contentType = parts[0].split(':')[1];
  const raw = window.atob(parts[1]);
  const rawLength = raw.length;
  const uInt8Array = new Uint8Array(rawLength);
  for (let i = 0; i < rawLength; ++i) {
    uInt8Array[i] = raw.charCodeAt(i);
  }
  return new Blob([uInt8Array], { type: contentType });
}

// ---------- 6. Upload generated images back to Dashboard ----------
async function uploadImageToServer(imgDataUrl, project_name, index, version = null) {
  try {
    const blob = dataURLToBlob(imgDataUrl);
    const formData = new FormData();
    const filename = version !== null ? `${index}_v${version}.png` : `${index}.png`;
    formData.append('file', blob, filename);
    
    let url = `${dashboardUrl}/api/projects/${project_name}/upload-image?index=${index}`;
    if (version !== null) {
      url += `&version=${version}`;
    }
    
    const res = await fetch(url, {
      method: 'POST',
      body: formData
    });
    
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.status === 'success';
  } catch (e) {
    log(`Lỗi tải ảnh #${index} lên server: ${e.message}`, "error");
    return false;
  }
}

// ---------- 7. Download image locally (optional) ----------
async function downloadImageLocally(imgDataUrl, project_name, index, version = null) {
  if (!els.saveLocal.checked) return;
  try {
    const safeProject = project_name.replace(/[\\/:*?"<>|]/g, "").replace(/\s+/g, "_");
    const filename = version !== null 
      ? `doodle_images/${safeProject}/${index}_v${version}.png`
      : `doodle_images/${safeProject}/${index}.png`;
      
    await chrome.downloads.download({
      url: imgDataUrl,
      filename: filename,
      conflictAction: "uniquify",
      saveAs: false
    });
  } catch (e) {
    console.error("Lỗi download cục bộ:", e);
  }
}

// ---------- 8. Main Automation Control Loop ----------
async function startAutomation() {
  if (!activeProject) {
    alert("Vui lòng kết nối với Dashboard trước!");
    return;
  }
  
  const tab = await getFlowTab();
  if (!tab) {
    alert("Vui lòng mở trang Google ImageFX hoặc Google Flow trước!");
    return;
  }
  
  isRunning = true;
  chrome.storage.local.set({ imagefx_automator_running: true });
  els.startBtn.disabled = true;
  els.stopBtn.disabled = false;
  els.retryBtn.style.display = "none";
  
  clearLogs();
  log("🚀 Bắt đầu tiến trình tự động hóa điều phối...", "warning");
  
  let retryCount = 0;
  const projectName = activeProject.info.project_name;
  
  while (isRunning) {
    // 1. Tìm tab và kết nối
    const currentTab = await getFlowTab();
    if (!currentTab) {
      log("Không tìm thấy tab Google ImageFX/Flow. Đang chờ 5s...", "error");
      await sleep(5000);
      continue;
    }
    
    if (currentTab.__isFlowHomepage) {
      log("⚠️ Bạn đang ở trang chủ Google Flow. Vui lòng click mở một dự án cũ hoặc tạo 'Dự án mới' để bắt đầu!", "warning");
      await sleep(5000);
      continue;
    }
    
    // 2. Lấy prompt pending kế tiếp từ Dashboard
    let task = null;
    try {
      const res = await fetch(`${dashboardUrl}/api/projects/${projectName}/next-pending-prompt`);
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success") {
          task = data;
        } else {
          log("Không còn prompt nào cần sinh ảnh (hoặc các prompt khác đang bị khóa). Đang chờ 5s...", "info");
          await sleep(5000);
          
          // Refresh project details to check actual status
          const refreshRes = await fetch(`${dashboardUrl}/api/active-project`);
          activeProject = await refreshRes.json();
          renderQueue();
          
          // Check if completely finished
          const imageMap = activeProject.image_map || {};
          const missing = activeProject.prompts.some((p, idx) => {
            const index = (p && typeof p === "object") ? (p.index !== undefined ? p.index : idx) : idx;
            return !imageMap[String(index)] || !imageMap[String(index)].active;
          });
          
          if (!missing) {
            log("🎉 Chúc mừng! Đã sinh và tải lên thành công toàn bộ ảnh cho dự án!", "success");
            stopAutomation();
            break;
          }
          continue;
        }
      } else {
        log("Lỗi kết nối Dashboard để lấy task. Đang thử lại sau 5 giây...", "error");
        await sleep(5000);
        continue;
      }
    } catch (e) {
      log(`Lỗi kết nối tới server Dashboard: ${e.message}`, "error");
      await sleep(5000);
      continue;
    }
    
    if (!isRunning) break;
    
    const i = task.index;
    log(`[Prompt #${i}] Bắt đầu xử lý: "${task.prompt.substring(0, 60)}..."`);
    
    // Update UI status to generating
    const qitem = $(`qitem-${i}`);
    if (qitem) {
      qitem.className = "qitem generating";
      const tag = qitem.querySelector(".tag");
      if (tag) {
        tag.className = "tag generating";
        tag.textContent = "Đang tạo";
      }
    }
    
    // 3. Gửi prompt sang tab để điền và bấm tạo
    const submitResp = await sendToTab(currentTab.id, {
      type: "SUBMIT_PROMPT",
      prompt: task.prompt,
      index: i
    });
    
    if (!isRunning) break;
    
    if (!submitResp || !submitResp.ok) {
      const errMsg = (submitResp && submitResp.error) ? submitResp.error : "Không thể kết nối hoặc gửi tin nhắn sang tab.";
      log(`Gửi prompt #${i} sang tab thất bại! Chi tiết: ${errMsg}`, "error");
      if (qitem) qitem.className = "qitem error";
      await sleep(4000);
      continue;
    }
    
    log(`[Prompt #${i}] Đã điền và bấm Tạo. Đang chờ kết quả từ ImageFX...`);
    
    // 4. Chờ ảnh xong từ tab
    const waitResp = await sendToTab(currentTab.id, {
      type: "WAIT_IMAGE",
      prompt: task.prompt,
      expectedCount: expectedImageCount
    });
    
    if (!isRunning) break;
    
    if (!waitResp || !waitResp.ok || !waitResp.images || waitResp.images.length === 0) {
      // Xử lý lỗi
      const errType = waitResp ? waitResp.error : 'timeout';
      if (errType === 'safety') {
        log(`[Kiểm duyệt] Prompt #${i} bị ImageFX từ chối sinh do vi phạm chính sách!`, "error");
        if (retryCount < 1) {
          retryCount++;
          log(`[Kiểm duyệt] Đang gọi Gemini tự động viết lại prompt #${i}...`, "warning");
          try {
            const rwRes = await fetch(`${dashboardUrl}/api/projects/${projectName}/rewrite-prompt`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ index: i, prompt: task.prompt })
            });
            if (rwRes.ok) {
              const rwData = await rwRes.json();
              if (rwData.status === 'success') {
                log(`[Kiểm duyệt] Đã viết lại thành công! Sẽ tự động thử lại ở vòng lặp sau.`, "success");
                await sleep(2000);
                continue;
              }
            }
          } catch (rwErr) {
            console.error("Lỗi khi viết lại prompt:", rwErr);
          }
        }
        
        log(`[Kiểm duyệt] Bỏ qua prompt #${i} để bạn xử lý thủ công sau.`, "warning");
        retryCount = 0;
        if (qitem) qitem.className = "qitem error";
        await sleep(2000);
      } else if (errType === 'limit') {
        log(`[Hạn mức] Đạt giới hạn sinh ảnh hôm nay của tài khoản Google Labs!`, "error");
        playBeepAlert();
        stopAutomation();
        break;
      } else {
        log(`[Lỗi] Quá thời gian chờ (60s) hoặc có lỗi xảy ra trên ImageFX khi tạo prompt #${i}.`, "error");
        if (qitem) qitem.className = "qitem error";
        stopAutomation();
        break;
      }
    } else {
      // 5. Thành công: Lấy danh sách Data URLs và xử lý tải lên / lưu trữ
      retryCount = 0;
      const imageUrls = waitResp.images;
      log(`[Prompt #${i}] Đã nhận ${imageUrls.length} ảnh mới từ ImageFX. Đang tiến hành đồng bộ về Dashboard...`, "success");
      
      let allUploaded = true;
      for (let v = 0; v < imageUrls.length; v++) {
        // blob URL -> convert to DataURL first using tab if it is a blob
        let imgUrl = imageUrls[v];
        if (imgUrl.startsWith("blob:")) {
          const dataUrlResp = await sendToTab(currentTab.id, { type: "TODATAURL", src: imgUrl });
          if (dataUrlResp && dataUrlResp.dataUrl) {
            imgUrl = dataUrlResp.dataUrl;
          } else {
            log(`Không thể chuyển đổi blob URL ảnh #${i}_v${v}`, "error");
            allUploaded = false;
            continue;
          }
        }
        
        // Upload to Dashboard
        const uploaded = await uploadImageToServer(imgUrl, projectName, i, v);
        if (uploaded) {
          // Download locally if enabled
          await downloadImageLocally(imgUrl, projectName, i, v);
        } else {
          allUploaded = false;
        }
      }
      
      if (allUploaded) {
        log(`[Prompt #${i}] Đã đồng bộ tất cả ảnh thành công!`, "success");
        if (qitem) {
          qitem.className = "qitem done";
          const tag = qitem.querySelector(".tag");
          if (tag) {
            tag.className = "tag done";
            tag.textContent = "Đã có";
          }
        }
      } else {
        log(`[Prompt #${i}] Đồng bộ ảnh thất bại. Tạm dừng để bạn kiểm tra.`, "error");
        if (qitem) qitem.className = "qitem error";
        stopAutomation();
        break;
      }
      
      // 6. Nghỉ ngẫu nhiên giữa các prompt (trừ khi đã dừng)
      if (isRunning) {
        const delay = randDelay();
        log(`Nghỉ ngẫu nhiên ${(delay / 1000).toFixed(1)} giây trước prompt kế tiếp...`, "info");
        await sleep(delay);
      }
    }
    
    // Đồng bộ lại hàng đợi
    const refreshRes = await fetch(`${dashboardUrl}/api/active-project`);
    activeProject = await refreshRes.json();
    renderQueue();
  }
}

function randDelay() {
  const min = Math.max(0, parseInt(els.delayMin.value) || 0);
  const max = Math.max(min, parseInt(els.delayMax.value) || 0);
  return (min + Math.random() * (max - min)) * 1000;
}

function stopAutomation() {
  isRunning = false;
  chrome.storage.local.set({ imagefx_automator_running: false });
  els.startBtn.disabled = false;
  els.stopBtn.disabled = true;
  els.retryBtn.style.display = "inline-block";
  log("🛑 Đã dừng tiến trình tự động hóa điều phối.", "warning");
}

// Play Audio Beep on limit error
function playBeepAlert() {
  try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    let time = audioCtx.currentTime;
    const playBeep = (freq, duration, delay) => {
      const osc = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gainNode.gain.setValueAtTime(0.1, time + delay);
      gainNode.gain.exponentialRampToValueAtTime(0.01, time + delay + duration);
      osc.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      osc.start(time + delay);
      osc.stop(time + delay + duration);
    };
    playBeep(880, 0.2, 0);
    playBeep(880, 0.2, 0.3);
    playBeep(880, 0.4, 0.6);
  } catch (e) {
    console.error("Beep error:", e);
  }
}

// ---------- 9. Main Action Handler: Retry ----------
async function retryPrompt() {
  if (!activeProject) return;
  const currentTab = await getFlowTab();
  if (!currentTab) {
    alert("Vui lòng mở trang Google ImageFX hoặc Flow!");
    return;
  }
  
  // Refresh active project details
  const res = await fetch(`${dashboardUrl}/api/active-project`);
  activeProject = await res.json();
  const projectName = activeProject.info.project_name;
  
  // Find first missing index (or let the user select)
  // For simplicity, we trigger deletion of the current prompt or next pending prompt
  const pendingRes = await fetch(`${dashboardUrl}/api/projects/${projectName}/next-pending-prompt`);
  if (!pendingRes.ok) return;
  const task = await pendingRes.json();
  
  if (task.status === "success") {
    log(`[Thử Lại] Đang xóa ảnh cũ của prompt #${task.index} để sinh lại...`, "warning");
    
    // Delete old image
    await fetch(`${dashboardUrl}/api/projects/${projectName}/delete-image/${task.index}`, {
      method: "POST"
    });
    
    // Start automation loop starting at this prompt
    startAutomation();
  } else {
    // If no pending, delete the last prompt's image to retry it
    const prompts = activeProject.prompts;
    if (prompts.length > 0) {
      const lastIndex = prompts.length - 1;
      log(`[Thử Lại] Đang xóa ảnh cũ của prompt cuối #${lastIndex} để sinh lại...`, "warning");
      await fetch(`${dashboardUrl}/api/projects/${projectName}/delete-image/${lastIndex}`, {
        method: "POST"
      });
      connectDashboard();
    }
  }
}

// ---------- 10. Event Listeners initialization ----------
els.host.addEventListener("change", saveSettings);
els.delayMin.addEventListener("change", saveSettings);
els.delayMax.addEventListener("change", saveSettings);
els.saveLocal.addEventListener("change", saveSettings);

document.querySelectorAll('input[name="expected-count"]').forEach(radio => {
  radio.addEventListener("change", updateExpectedImageCount);
});

els.connectBtn.addEventListener("click", connectDashboard);
els.startBtn.addEventListener("click", startAutomation);
els.stopBtn.addEventListener("click", stopAutomation);
els.retryBtn.addEventListener("click", retryPrompt);

// ---------- 11. Initial Startup ----------
loadSettings().then(() => {
  connectDashboard();
  periodicCheck();
  setInterval(periodicCheck, 4000);
});

// ---------- 12. Debug Log Listener ----------
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "DEBUG_LOG") {
    log(`[Tab Debug] ${msg.text}`, msg.logType || "info");
    sendResponse({ ok: true });
    return true;
  }
});
