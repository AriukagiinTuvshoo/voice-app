// Background service worker for shortcut commands
chrome.commands.onCommand.addListener((command) => {
  if (command === "toggle-dictation") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { action: "toggle-dictation" }).catch(() => {});
      }
    });
  }
});
