const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electron", {
  isDesktop: true,
  insertText: (text) => ipcRenderer.send("insert-transcribed-text", text),
  onRecordingStart: (callback) => {
    ipcRenderer.on("trigger-recording-start", () => callback());
  },
  onRecordingStop: (callback) => {
    ipcRenderer.on("trigger-recording-stop", () => callback());
  },
});
