// Background service worker for VOICE Chrome Extension

chrome.runtime.onInstalled.addListener(() => {
  // Automatically inject into already open tabs so user doesn't even need to refresh
  chrome.tabs.query({ url: ["http://*/*", "https://*/*"] }, (tabs) => {
    for (const tab of tabs) {
      if (tab.id && tab.url && !tab.url.startsWith("chrome://")) {
        chrome.scripting?.executeScript({
          target: { tabId: tab.id },
          files: ["content.js"],
        }).catch(() => {});
        chrome.scripting?.insertCSS({
          target: { tabId: tab.id },
          files: ["content.css"],
        }).catch(() => {});
      }
    }
  });
});

chrome.commands.onCommand.addListener((command) => {
  if (command === "toggle-dictation") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { action: "toggle-dictation" }).catch(() => {});
      }
    });
  }
});
