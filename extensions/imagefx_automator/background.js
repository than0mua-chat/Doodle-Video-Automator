// ============================================================
//  Doodle Video Automator — background.js
//  Sử dụng chrome.debugger (CDP) để gõ chữ và bấm Enter thật
//  để vượt qua các lớp bảo mật, bộ lọc sự kiện của React/Slate.js
// ============================================================

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

let attachedTab = null;

// Tự động giải phóng kết nối khi bị tách rời
chrome.debugger.onDetach.addListener((source) => {
  if (source.tabId === attachedTab) {
    console.warn("[Automator] debugger bị tách khỏi tab", source.tabId);
    attachedTab = null;
  }
});

function sendCmd(tabId, method, params) {
  return new Promise((resolve, reject) => {
    chrome.debugger.sendCommand({ tabId }, method, params || {}, (res) => {
      if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
      else resolve(res);
    });
  });
}

async function ensureAttached(tabId) {
  if (attachedTab === tabId) return;
  if (attachedTab !== null) {
    try {
      await chrome.debugger.detach({ tabId: attachedTab });
    } catch (_) {}
    attachedTab = null;
  }
  await new Promise((resolve, reject) => {
    chrome.debugger.attach({ tabId }, "1.3", () => {
      if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
      else resolve();
    });
  });
  attachedTab = tabId;
}

async function detach() {
  if (attachedTab !== null) {
    try {
      await chrome.debugger.detach({ tabId: attachedTab });
    } catch (_) {}
    attachedTab = null;
  }
}

// Giả lập click chuột + gõ phím thật để điền prompt và gửi
async function debugTypeAndSubmit(tabId, x, y, prompt) {
  await ensureAttached(tabId);

  // 1) Click chuột vào tọa độ x, y để focus thật vào ô nhập liệu
  await sendCmd(tabId, "Input.dispatchMouseEvent", {
    type: "mousePressed", x, y, button: "left", clickCount: 1,
  });
  await sendCmd(tabId, "Input.dispatchMouseEvent", {
    type: "mouseReleased", x, y, button: "left", clickCount: 1,
  });
  await wait(150);

  // 2) Nhấn Ctrl + A để bôi đen toàn bộ nội dung cũ
  await sendCmd(tabId, "Input.dispatchKeyEvent", {
    type: "keyDown", modifiers: 2, key: "a", code: "KeyA", windowsVirtualKeyCode: 65,
  });
  await sendCmd(tabId, "Input.dispatchKeyEvent", {
    type: "keyUp", modifiers: 2, key: "a", code: "KeyA", windowsVirtualKeyCode: 65,
  });
  await wait(80);

  // 3) Gõ nội dung prompt mới
  await sendCmd(tabId, "Input.insertText", { text: prompt });
  await wait(300);

  // 4) Nhấn Enter để kích hoạt gửi yêu cầu
  await sendCmd(tabId, "Input.dispatchKeyEvent", {
    type: "rawKeyDown", key: "Enter", code: "Enter",
    windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13,
  });
  await sendCmd(tabId, "Input.dispatchKeyEvent", {
    type: "keyUp", key: "Enter", code: "Enter",
    windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13,
  });
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || !msg.type) return;

  const tabId = sender.tab ? sender.tab.id : null;
  if (!tabId && (msg.type === "DEBUG_SUBMIT" || msg.type === "DEBUG_DETACH")) {
    sendResponse({ ok: false, error: "Không tìm thấy thông tin tab gửi yêu cầu" });
    return;
  }

  if (msg.type === "DEBUG_SUBMIT") {
    debugTypeAndSubmit(tabId, msg.x, msg.y, msg.prompt)
      .then(() => sendResponse({ ok: true }))
      .catch((e) => sendResponse({ ok: false, error: String(e.message || e) }));
    return true; // Phản hồi bất đồng bộ
  }

  if (msg.type === "DEBUG_DETACH") {
    detach().then(() => sendResponse({ ok: true }));
    return true; // Phản hồi bất đồng bộ
  }
});
