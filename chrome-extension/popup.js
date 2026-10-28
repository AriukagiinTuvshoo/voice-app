document.addEventListener("DOMContentLoaded", () => {
  const directMicBtn = document.getElementById("directMicBtn");
  const directMicText = document.getElementById("directMicText");
  const shortcutSelect = document.getElementById("shortcutSelect");
  const langSelect = document.getElementById("lang");
  const showFloatingMic = document.getElementById("showFloatingMic");
  const serverInput = document.getElementById("server");
  const saveBtn = document.getElementById("save");
  const statusDiv = document.getElementById("status");

  // Load saved settings with auto-migration to Local
  chrome.storage?.sync?.get(
    ["shortcut", "language", "showFloatingMic", "serverURL"],
    (items) => {
      if (items?.shortcut) shortcutSelect.value = items.shortcut;
      if (items?.language) langSelect.value = items.language;
      if (items?.showFloatingMic !== undefined) showFloatingMic.checked = items.showFloatingMic;
      
      let sUrl = items?.serverURL || "http://localhost:3000";
      // Auto-migrate old render cloud URL to local
      if (sUrl.includes("onrender.com")) {
        sUrl = "http://localhost:3000";
        chrome.storage.sync.set({ serverURL: sUrl });
      }
      serverInput.value = sUrl;
    }
  );

  // Big 1-click Dictate button inside popup
  directMicBtn.addEventListener("click", async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) return;

    try {
      chrome.tabs.sendMessage(tab.id, { action: "toggle-dictation" }, (res) => {
        if (chrome.runtime.lastError) {
          // If script not loaded yet, inject it on the fly
          chrome.scripting.executeScript(
            {
              target: { tabId: tab.id },
              files: ["content.js"],
            },
            () => {
              chrome.scripting.insertCSS({
                target: { tabId: tab.id },
                files: ["content.css"],
              });
              setTimeout(() => {
                chrome.tabs.sendMessage(tab.id, { action: "toggle-dictation" });
              }, 150);
            }
          );
        }
      });
      window.close(); // Close popup so user sees dictation capsule on page
    } catch {}
  });

  // Save settings
  saveBtn.addEventListener("click", () => {
    const newSettings = {
      shortcut: shortcutSelect.value,
      language: langSelect.value,
      showFloatingMic: showFloatingMic.checked,
      serverURL: serverInput.value.trim().replace(/\/$/, "") || "http://localhost:3000",
    };

    chrome.storage?.sync?.set(newSettings, () => {
      statusDiv.textContent = "Тохиргоо хадгалагдлаа (Local)!";

      // Notify active tab of updated settings
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]?.id) {
          chrome.tabs.sendMessage(tabs[0].id, {
            action: "update-settings",
            settings: newSettings,
          }).catch(() => {});
        }
      });

      setTimeout(() => { statusDiv.textContent = ""; }, 2000);
    });
  });
});
