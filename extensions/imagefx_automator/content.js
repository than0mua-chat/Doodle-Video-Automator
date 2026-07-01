// ============================================================
//  Doodle Video Automator — content.js
//  Execution Agent: Wakes prompt boxes, types prompts, triggers
//  generation, detects images, and relays data back to the sidepanel.
// ============================================================

const seenImageUrls = new Set();
let dashboardUrl = "http://127.0.0.1:8085";

// ---------- A. Helpers for ImageFX / Google Flow ----------
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function sendDebugLog(text, type = "info") {
  try {
    chrome.runtime.sendMessage({ type: "DEBUG_LOG", text: text, logType: type }, () => {
      if (chrome.runtime.lastError) {}
    });
  } catch (_) {}
  console.log(`[DVA Debug] ${text}`);
}

function isVisible(el) {
  if (!el) return false;
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return false;
  const s = getComputedStyle(el);
  return s.display !== "none" && s.visibility !== "hidden" && s.opacity !== "0";
}

function area(el) {
  const r = el.getBoundingClientRect();
  return r.width * r.height;
}

function srcKey(img) {
  return img.currentSrc || img.src || "";
}

function isShown(el) {
  if (!el) return false;
  if (isVisible(el)) return true;
  return el.getClientRects().length > 0;
}

function findPromptInput() {
  sendDebugLog("Đang quét tìm ô nhập prompt...");
  const selectors = [
    'textarea',
    '[data-slate-editor="true"]',
    '[contenteditable="true"][role="textbox"]',
    '[role="textbox"][aria-multiline="true"]',
    'div[role="textbox"]',
    '[contenteditable="true"]',
    '[contenteditable=""]'
  ];
  
  let candidates = [];
  for (const sel of selectors) {
    const elements = Array.from(document.querySelectorAll(sel));
    if (elements.length > 0) {
      sendDebugLog(`Selector "${sel}" tìm thấy ${elements.length} phần tử.`);
    }
    for (const el of elements) {
      if (el.closest('.automator-panel') || el.closest('#imagefx-automator-panel') || el.closest('#aistudio-automator-panel')) {
        continue;
      }
      if (!candidates.includes(el)) {
        candidates.push(el);
      }
    }
  }
  
  sendDebugLog(`Tổng số ứng viên nhập liệu sau khi loại trừ automator panels: ${candidates.length}`);
  
  if (candidates.length === 0) {
    sendDebugLog("❌ Không tìm thấy ứng viên nhập liệu nào!", "error");
    return null;
  }
  
  candidates.forEach((el, idx) => {
    const tag = el.tagName;
    const placeholder = el.getAttribute("placeholder") || el.dataset?.placeholder || "";
    const ariaLabel = el.getAttribute("aria-label") || "";
    const isCE = el.isContentEditable;
    sendDebugLog(`Ứng viên #${idx}: TAG=${tag}, isCE=${isCE}, placeholder="${placeholder}", aria-label="${ariaLabel}"`);
  });
  
  const hint = /prompt|imagine|describe|create|write|tạo|nhập|lời nhắc|mô tả|sinh|生成|描述/i;
  const bestMatch = candidates.find(el => {
    const attrs = [
      el.getAttribute("placeholder"),
      el.getAttribute("aria-label"),
      el.getAttribute("title"),
      el.dataset?.placeholder,
      el.innerText
    ].filter(Boolean).join(" ").toLowerCase();
    return hint.test(attrs);
  });
  if (bestMatch) {
    sendDebugLog(`✅ Khớp Ưu tiên 1 (Hint Regex): TAG=${bestMatch.tagName}, placeholder="${bestMatch.getAttribute("placeholder") || bestMatch.dataset?.placeholder || ""}"`);
    return bestMatch;
  }
  
  const visibleTextarea = candidates.find(el => el.tagName === "TEXTAREA" && isShown(el));
  if (visibleTextarea) {
    sendDebugLog("✅ Khớp Ưu tiên 2 (TEXTAREA visible)");
    return visibleTextarea;
  }
  
  const visibleEditable = candidates.find(el => (el.isContentEditable || el.getAttribute("contenteditable") !== null) && isShown(el));
  if (visibleEditable) {
    sendDebugLog("✅ Khớp Ưu tiên 3 (contenteditable visible)");
    return visibleEditable;
  }
  
  const anyTextarea = candidates.find(el => el.tagName === "TEXTAREA");
  if (anyTextarea) {
    sendDebugLog("✅ Khớp Ưu tiên 4 (textarea bất kỳ)");
    return anyTextarea;
  }
  
  candidates.sort((a, b) => area(b) - area(a));
  sendDebugLog(`✅ Khớp Ưu tiên 5 (Diện tích lớn nhất): TAG=${candidates[0].tagName}`);
  return candidates[0];
}

async function wakePromptBox() {
  let ed = findPromptInput();
  if (ed) {
    clickFully(ed);
    ed.focus?.();
    await sleep(150);
    return findPromptInput();
  }
  let arrow = [...document.querySelectorAll('button, [role="button"]')].find(
    (b) => /arrow_forward/i.test((b.getAttribute("aria-label") || "") + b.textContent)
  );
  if (!arrow) {
    arrow = findGenerateButton(null);
  }
  if (arrow) {
    const r = arrow.getBoundingClientRect();
    const points = [
      [r.left - 150, r.top + r.height / 2],
      [r.left - 300, r.top + r.height / 2],
      [r.left - 80, r.top + r.height / 2],
    ];
    for (const [x, y] of points) {
      const t = document.elementFromPoint(x, y);
      if (!t) continue;
      ["mousedown", "mouseup", "click"].forEach((type) =>
        t.dispatchEvent(
          new MouseEvent(type, {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX: x,
            clientY: y,
          })
        )
      );
      t.focus?.();
      await sleep(250);
      ed = findPromptInput();
      if (ed) return ed;
    }
  }
  return findPromptInput();
}

function setPromptText(el, text) {
  sendDebugLog(`Bắt đầu điền prompt. Độ dài text: ${text.length}`);
  
  try {
    const r = el.getBoundingClientRect();
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    sendDebugLog(`Giả lập click tọa độ trung tâm (${x.toFixed(1)}, ${y.toFixed(1)}) để Slate/React nhận diện`);
    ["mousedown", "mouseup", "click"].forEach((t) => {
      (document.elementFromPoint(x, y) || el).dispatchEvent(
        new MouseEvent(t, { bubbles: true, cancelable: true, clientX: x, clientY: y, view: window })
      );
    });
    el.focus?.();
    sendDebugLog("Đã gọi el.focus()");
  } catch (e) {
    sendDebugLog(`Lỗi click/focus: ${e.message}`, "error");
  }
  
  if (el.isContentEditable || el.getAttribute("data-slate-editor") === "true") {
    sendDebugLog("Định dạng: ContentEditable / Slate editor");
    try {
      sendDebugLog("Thử cách 1: execCommand selectAll + insertText");
      const s1 = document.execCommand('selectAll', false);
      const s2 = document.execCommand('insertText', false, text);
      sendDebugLog(`Kết quả execCommand: selectAll=${s1}, insertText=${s2}`);
    } catch (e) {
      sendDebugLog(`Lỗi execCommand: ${e.message}`, "warning");
    }
  }
  
  const textLen = inputText(el).trim().length;
  sendDebugLog(`Độ dài chữ sau cách 1: ${textLen}`);
  
  if (textLen < 3) {
    sendDebugLog("Thử cách 2: Dispatch beforeinput event");
    try {
      const e1 = el.dispatchEvent(new InputEvent("beforeinput", {
        inputType: "deleteContentBackward",
        bubbles: true,
        cancelable: true,
        composed: true,
      }));
      const e2 = el.dispatchEvent(new InputEvent("beforeinput", {
        inputType: "insertText",
        data: text,
        bubbles: true,
        cancelable: true,
        composed: true,
      }));
      sendDebugLog(`Kết quả dispatch beforeinput: delete=${e1}, insert=${e2}`);
    } catch (e) {
      sendDebugLog(`Lỗi beforeinput: ${e.message}`, "warning");
    }
  }
  
  const textLen2 = inputText(el).trim().length;
  sendDebugLog(`Độ dài chữ sau cách 2: ${textLen2}`);
  
  if (textLen2 < 3) {
    sendDebugLog("Thử cách 3: Gán innerText/value trực tiếp");
    try {
      if (el.isContentEditable) {
        el.innerText = text;
      } else {
        const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
        if (setter) setter.call(el, text);
        else el.value = text;
      }
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      sendDebugLog("Đã gán trực tiếp và dispatch input/change");
    } catch (e) {
      sendDebugLog(`Lỗi gán trực tiếp: ${e.message}`, "error");
    }
  }
  
  const finalLen = inputText(el).trim().length;
  sendDebugLog(`Độ dài chữ cuối cùng trong ô prompt: ${finalLen}`);
}

function inputText(el) {
  if (el.isContentEditable) {
    if (el.querySelector("[data-slate-string], [data-slate-placeholder]")) {
      return [...el.querySelectorAll("[data-slate-string]")].map((s) => s.textContent).join("");
    }
    return el.innerText || el.textContent || "";
  }
  return el.value || "";
}

function clickFully(el) {
  const r = el.getBoundingClientRect();
  const base = {
    bubbles: true,
    cancelable: true,
    composed: true,
    view: window,
    clientX: r.left + r.width / 2,
    clientY: r.top + r.height / 2,
  };
  try {
    el.dispatchEvent(new PointerEvent("pointerdown", base));
    el.dispatchEvent(new MouseEvent("mousedown", base));
    el.dispatchEvent(new PointerEvent("pointerup", base));
    el.dispatchEvent(new MouseEvent("mouseup", base));
    el.dispatchEvent(new MouseEvent("click", base));
  } catch (_) {}
  el.click?.();
}

function findGenerateButton(input) {
  sendDebugLog("Đang quét các nút Generate/Tạo trên trang...");
  const buttons = [...document.querySelectorAll('button, [role="button"]')].filter(
    (b) => isVisible(b) && !b.disabled && b.getAttribute("aria-disabled") !== "true"
  );
  
  sendDebugLog(`Tìm thấy ${buttons.length} nút đang hiển thị và không disabled.`);
  buttons.forEach((btn, idx) => {
    const text = btn.textContent.trim() || btn.innerText.trim() || "";
    const aria = btn.getAttribute("aria-label") || "";
    sendDebugLog(`Nút #${idx}: TAG=${btn.tagName}, Text="${text}", aria-label="${aria}"`);
  });

  // 1) Ưu tiên tuyệt đối: nút mũi tên gửi của Flow (icon "arrow_forward")
  let b = buttons.find((x) => x.innerHTML.includes('arrow_forward') || x.querySelector('svg[data-icon="arrow-forward"]'));
  if (b) {
    sendDebugLog(`✅ Khớp nút (arrow_forward): TAG=${b.tagName}`);
    return b;
  }

  // 2) Tìm nút chứa chữ "Generate" (tiếng Anh) hoặc "Tạo"
  b = buttons.find((x) => {
    const txt = (x.textContent || x.innerText || "").toLowerCase();
    return txt.includes("generate");
  });
  if (b) {
    sendDebugLog(`✅ Khớp nút (chữ 'generate'): TAG=${b.tagName}`);
    return b;
  }

  // 3) Tìm nút chứa chữ "Tạo" nhưng không có icon "add"
  b = buttons.find((x) => {
    const txt = (x.textContent || x.innerText || "").toLowerCase();
    const hasTao = txt.includes("tạo");
    const hasAddIcon = x.innerHTML.includes("add") || x.innerHTML.includes("add_2");
    return hasTao && !hasAddIcon;
  });
  if (b) {
    sendDebugLog(`✅ Khớp nút (chữ 'tạo'): TAG=${b.tagName}`);
    return b;
  }

  const label = (b) =>
    (
      (b.getAttribute("aria-label") || "") +
      " " +
      (b.title || "") +
      " " +
      b.textContent
    ).toLowerCase();

  const bad = /agent|tác nhân|delete|close|xoá|xóa|trash|thùng|panel|banana|model|setting/i;
  const wanted = /submit|send|run|gửi|送信|生成|→|paper.?plane/i;
  b = buttons.find((x) => wanted.test(label(x)) && !bad.test(label(x)));
  if (b) {
    sendDebugLog(`✅ Khớp nút (từ khóa wanted): TAG=${b.tagName}`);
    return b;
  }

  if (input) {
    const ir = input.getBoundingClientRect();
    const near = buttons
      .filter((x) => !bad.test(label(x)))
      .map((x) => {
        const r = x.getBoundingClientRect();
        const dx = r.left - ir.right;
        const dy = r.top - ir.top;
        return { x, d: Math.hypot(dx, dy) };
      })
      .filter((o) => o.d < 600)
      .sort((a, b) => a.d - b.d);
    if (near[0]) {
      sendDebugLog(`✅ Khớp nút (gần ô prompt nhất): TAG=${near[0].x.tagName}`);
      return near[0].x;
    }
  }
  
  sendDebugLog("❌ Không tìm thấy nút Generate/Tạo phù hợp!", "warning");
  return null;
}

function pressEnter(el) {
  sendDebugLog("Đang giả lập nhấn Enter...");
  try { el.focus(); } catch (_) {}
  for (const type of ["keydown", "keypress", "keyup"]) {
    const ev = new KeyboardEvent(type, {
      key: "Enter",
      code: "Enter",
      bubbles: true,
      cancelable: true,
      composed: true,
    });
    Object.defineProperty(ev, "keyCode", { get: () => 13 });
    Object.defineProperty(ev, "which", { get: () => 13 });
    el.dispatchEvent(ev);
  }
}

function clickGenerateButton(input) {
  const btn = findGenerateButton(input);
  if (btn) {
    clickFully(btn);
    sendDebugLog(`Đã click nút Generate/Tạo: TAG=${btn.tagName}, Text="${btn.textContent.trim()}"`);
    return true;
  }
  return false;
}

function getCompletedImages() {
  return [...document.querySelectorAll("img")].filter((img) => {
    if (!img.src || !isVisible(img)) return false;
    const src = srcKey(img);
    if (!/^https?:|^blob:/.test(src)) return false;
    const w = img.naturalWidth || img.width;
    const h = img.naturalHeight || img.height;
    if (w < 100 && h < 100) return false;
    // Exclude avatars/logos
    const srcLower = src.toLowerCase();
    if (srcLower.includes('avatar') || srcLower.includes('profile') || srcLower.includes('logo') || srcLower.includes('icon') || srcLower.includes('sign-in')) return false;
    return true;
  });
}

function detectImageFXError() {
  const textElements = Array.from(document.querySelectorAll('div, span, p, h1, h2, h3, li'));
  for (const el of textElements) {
    if (!el.textContent) continue;
    const text = el.textContent.trim().toLowerCase();
    if (text.includes("can't generate") || text.includes("say something else") || text.includes("try a different prompt") || text.includes("violate our safety") || text.includes("content warning") || text.includes("không thể tạo ảnh này") || text.includes("vi phạm chính sách")) {
      return { type: 'safety', message: el.textContent.trim() };
    }
    if (text.includes("reached your limit") || text.includes("quota exceeded") || text.includes("try again tomorrow") || text.includes("too many requests") || text.includes("đạt giới hạn") || text.includes("vượt quá hạn mức")) {
      return { type: 'limit', message: el.textContent.trim() };
    }
  }
  return null;
}

async function toDataUrl(url) {
  const res = await fetch(url);
  const blob = await res.blob();
  return await new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result);
    fr.onerror = reject;
    fr.readAsDataURL(blob);
  });
}

// ---------- B. Messaging Event Listener (Connects with Side Panel) ----------
if (!window.__DVA_LISTENER_REGISTERED__) {
  window.__DVA_LISTENER_REGISTERED__ = true;
  
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (!msg || !msg.type) return;
    
    if (msg.type === "PING") {
      let hasInput = false;
      try {
        hasInput = !!findPromptInput();
      } catch (_) {}
      sendResponse({ ok: true, hasInput });
      return;
    }
    
    if (msg.type === "SUBMIT_PROMPT") {
      (async () => {
        try {
          // 1. Chụp baseline ảnh cũ trước khi gửi prompt mới
          window.__imagefx_baseline = new Set(getCompletedImages().map(srcKey));
          console.log(`[Task #${msg.index}] Chụp baseline cũ. Số lượng: ${window.__imagefx_baseline.size} ảnh.`);
          
          // 2. Tìm và đánh thức ô nhập liệu
          let input = await wakePromptBox();
          if (!input) {
            sendResponse({ ok: false, error: "Không tìm thấy ô prompt trên trang." });
            return;
          }
          
          // 3. Focus và điền prompt
          clickFully(input);
          input.focus();
          await sleep(250);
          
          setPromptText(input, msg.prompt);
          await sleep(1000); // Chờ React đồng bộ hóa trạng thái
          
          // Kiểm tra xem chữ đã thực sự được gõ vào chưa
          const got = inputText(input).trim();
          console.log(`[Task #${msg.index}] Nội dung ô prompt sau khi gõ: "${got.slice(0, 60)}..." (Độ dài: ${got.length})`);
          
          if (got.length < 3) {
            sendResponse({ ok: false, error: "Lỗi: Không thể điền văn bản vào ô prompt (Slate Editor không nhận ký tự)." });
            return;
          }
          
          // 4. Bấm nút Tạo / Gửi
          const clicked = clickGenerateButton(input);
          if (clicked) {
            // Chờ một chút xem ô prompt có được xóa trống không (dấu hiệu submit thành công)
            await sleep(800);
            const afterClickText = inputText(input).trim();
            if (afterClickText.length < 3) {
              sendResponse({ ok: true, note: "Click nút Generate thành công." });
              return;
            }
          }
          
          // Nếu click nút không được hoặc không xóa trống, thử Enter dự phòng
          console.log(`[Task #${msg.index}] Nút click thất bại hoặc không gửi được. Thử gửi bằng phím Enter...`);
          pressEnter(input);
          await sleep(1000);
          
          const afterEnterText = inputText(input).trim();
          if (afterEnterText.length < 3) {
            sendResponse({ ok: true, note: "Submit bằng phím Enter dự phòng thành công." });
          } else {
            sendResponse({ 
              ok: false, 
              error: "Không thể gửi prompt. Đã click nút Tạo và nhấn Enter nhưng nội dung văn bản vẫn còn trong ô nhập liệu." 
            });
          }
        } catch (e) {
          sendResponse({ ok: false, error: "Lỗi ngoại lệ trong content script: " + String(e) });
        }
      })();
      return true; // asynchronous response
    }
    
    if (msg.type === "WAIT_IMAGE") {
      const baseline = window.__imagefx_baseline || new Set();
      const expectedCount = msg.expectedCount || 2;
      const start = Date.now();
      const maxWaitMs = 60000; // 60s timeout
      
      (async () => {
        while (Date.now() - start < maxWaitMs) {
          // Check safety or quota errors first
          const err = detectImageFXError();
          if (err) {
            sendResponse({ ok: false, error: err.type, message: err.message });
            return;
          }
          
          // Scan for new images
          const all = getCompletedImages();
          const fresh = all.filter(i => !baseline.has(srcKey(i)));
          
          if (fresh.length >= expectedCount) {
            await sleep(1500); // Wait to stabilize
            // Recalculate
            const finalAll = getCompletedImages();
            const finalFresh = finalAll.filter(i => !baseline.has(srcKey(i)));
            
            // Return new image srcs
            sendResponse({ ok: true, images: finalFresh.map(srcKey) });
            return;
          }
          
          await sleep(1000);
        }
        
        // Timeout: Return any available new images
        const finalAll = getCompletedImages();
        const finalFresh = finalAll.filter(i => !baseline.has(srcKey(i)));
        if (finalFresh.length > 0) {
          sendResponse({ ok: true, images: finalFresh.map(srcKey) });
        } else {
          sendResponse({ ok: false, error: 'timeout', message: 'Quá thời gian chờ (60s) không thấy ảnh mới' });
        }
      })();
      return true;
    }
    
    if (msg.type === "TODATAURL") {
      toDataUrl(msg.src)
        .then((d) => sendResponse({ dataUrl: d }))
        .catch((e) => sendResponse({ error: String(e) }));
      return true;
    }
  });
}

function getValidatedHost() {
    let host = localStorage.getItem('imagefx_automator_host');
    if (!host || (!host.startsWith('http://') && !host.startsWith('https://'))) {
        host = "http://127.0.0.1:8085";
    }
    return host;
}

// =============================================================
//  GOOGLE AI STUDIO AUTOMATION LOGIC (For Web Gemini)
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
    const buttons = Array.from(document.querySelectorAll('button'));
    const runBtn = buttons.find(b => {
        const txt = b.textContent.trim().toLowerCase().replace(/\s+/g, '');
        return (txt === 'run' || txt === 'runctrl+enter' || txt === 'runctrl' || txt === 'runprompt');
    });
    if (runBtn) return runBtn;

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
    const maxWaitMs = 10 * 60 * 1000;
    const startWait = Date.now();
    
    let lastTextLength = -1;
    let stableCount = 0;
    
    await new Promise(r => setTimeout(r, 2000));
    
    while (Date.now() - startWait < maxWaitMs) {
        const stopBtn = findAIStudioStopButton();
        const text = getAIStudioResponseText();
        
        if (Date.now() - startWait > 15000 && !stopBtn && text.length === 0) {
            throw new Error("Không khởi động được tiến trình sinh (nút Run hoặc phím tắt Ctrl+Enter không phản hồi).");
        }
        
        if (!stopBtn) {
            if (text.length > 0) {
                logAIStudio("Sinh hoàn tất (không thấy nút Stop và đã có text).");
                break;
            }
        }
        
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

// Khởi chạy tự động
setTimeout(async () => {
    const isAIStudio = window.location.hostname.includes('aistudio.google.com') || window.location.hostname.includes('gemini.google.com');
    if (isAIStudio) {
        createAIStudioUI();
    } else {
        // Quét sạch các ảnh trên màn hình khi tải trang lần đầu để làm sạch baseline
        Array.from(document.querySelectorAll('img')).forEach(img => {
            if (img.src) seenImageUrls.add(img.src);
        });
    }
}, 2000);
