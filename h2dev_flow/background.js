// ============================================================
//  h2dev_flow — background service worker
//  Chỉ cấu hình mở side panel khi người dùng click vào icon extension.
// ============================================================

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((e) => console.warn("[h2dev_flow] setPanelBehavior:", e));
});
