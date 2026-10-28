const { app, BrowserWindow, globalShortcut, Tray, Menu, ipcMain, clipboard, screen } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let mainWindow = null;
let flowBarWindow = null;
let tray = null;
let isRecording = false;

// Ensure single instance like DuudlagaFlow
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.whenReady().then(initApp);
}

function initApp() {
  createTray();
  createFlowBarWindow();
  createMainWindow();
  registerGlobalHotkey();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: "VOICE — Multilingual Voice & Spellcheck",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });

  const url = process.env.VOICE_URL || "http://localhost:3000";
  mainWindow.loadURL(url);

  mainWindow.on("close", (e) => {
    // Hide to tray instead of quitting if user closes window
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

function createFlowBarWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;

  const barWidth = 240;
  const barHeight = 48;
  const x = Math.round((width - barWidth) / 2);
  const y = height - barHeight - 24; // 24px above taskbar

  flowBarWindow = new BrowserWindow({
    width: barWidth,
    height: barHeight,
    x: x,
    y: y,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    focusable: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });

  const flowBarUrl = (process.env.VOICE_URL || "http://localhost:3000") + "/flowbar";
  flowBarWindow.loadURL(flowBarUrl);
  flowBarWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
}

function createTray() {
  // Use default or simple tray icon
  const iconPath = path.join(__dirname, "..", "public", "icon.svg");
  tray = new Tray(iconPath);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "VOICE нээх",
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    {
      label: "FlowBar харуулах / нуух",
      click: () => {
        if (flowBarWindow) {
          if (flowBarWindow.isVisible()) flowBarWindow.hide();
          else flowBarWindow.show();
        }
      },
    },
    { type: "separator" },
    {
      label: "Гарах (Quit)",
      click: () => {
        app.isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setToolTip("VOICE — Duudlaga Flow горим");
  tray.setContextMenu(contextMenu);

  tray.on("double-click", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

function registerGlobalHotkey(hotkey = "CommandOrControl+Alt") {
  globalShortcut.unregisterAll();

  // Register hotkey (like DuudlagaFlow Ctrl+Alt)
  const ret = globalShortcut.register(hotkey, () => {
    handleGlobalTrigger();
  });

  if (!ret) {
    console.warn(`Global shortcut ${hotkey} registration failed.`);
  }
}

function handleGlobalTrigger() {
  if (!isRecording) {
    isRecording = true;
    // Tell flowBarWindow to start recording
    if (flowBarWindow && flowBarWindow.webContents) {
      flowBarWindow.webContents.send("trigger-recording-start");
    }
  } else {
    isRecording = false;
    // Tell flowBarWindow to stop and transcribe
    if (flowBarWindow && flowBarWindow.webContents) {
      flowBarWindow.webContents.send("trigger-recording-stop");
    }
  }
}

// IPC: Insert text into active window
ipcMain.on("insert-transcribed-text", (event, text) => {
  if (!text) return;
  clipboard.writeText(text);

  // Paste text into active window on Windows using PowerShell SendKeys
  if (process.platform === "win32") {
    setTimeout(() => {
      const ps = spawn("powershell", [
        "-NoProfile",
        "-Command",
        `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('^v')`,
      ]);
      ps.on("close", () => {
        console.log("Pasted text into active window:", text);
      });
    }, 150);
  }
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});
