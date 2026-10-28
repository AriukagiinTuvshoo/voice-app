const { app, BrowserWindow, globalShortcut, Tray, Menu, ipcMain, clipboard, screen } = require("electron");
const path = require("path");
const http = require("http");

let mainWindow = null;
let flowBarWindow = null;
let tray = null;
let isRecording = false;

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
    width: 1240,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    title: "VOICE — Speak. Clean. Write.",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });

  const url = process.env.VOICE_URL || "http://localhost:3000";
  mainWindow.loadURL(url);

  mainWindow.on("close", (e) => {
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
  const barHeight = 52;
  const x = Math.round((width - barWidth) / 2);
  const y = height - barHeight - 20;

  flowBarWindow = new BrowserWindow({
    width: barWidth,
    height: barHeight,
    x,
    y,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    focusable: false,
    type: "toolbar",
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
  const iconPath = path.join(__dirname, "..", "public", "icon.svg");
  try {
    tray = new Tray(iconPath);
  } catch {
    return;
  }

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
}

function registerGlobalHotkey() {
  globalShortcut.unregisterAll();
  // Note: Ctrl+Alt is handled natively by tts_server.py's Win32 GetAsyncKeyState hook.
  // Also register Ctrl+Space and Alt+Space in Electron as extra accelerators.
  for (const accel of ["CommandOrControl+Space", "Alt+Space"]) {
    try {
      globalShortcut.register(accel, () => handleGlobalTrigger());
    } catch {}
  }
}

function handleGlobalTrigger() {
  if (!isRecording) {
    isRecording = true;
    if (flowBarWindow && flowBarWindow.webContents) {
      flowBarWindow.webContents.send("trigger-recording-start");
    }
  } else {
    isRecording = false;
    if (flowBarWindow && flowBarWindow.webContents) {
      flowBarWindow.webContents.send("trigger-recording-stop");
    }
  }
}

ipcMain.on("insert-transcribed-text", (event, text) => {
  if (!text || !text.trim()) return;
  clipboard.writeText(text);

  // Forward to tts_server.py Win32 SendInput(KEYEVENTF_UNICODE) endpoint
  const payload = Buffer.from(JSON.stringify({ text }), "utf-8");
  const req = http.request(
    {
      hostname: "127.0.0.1",
      port: 8000,
      path: "/insert-text",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": payload.length,
      },
    },
    () => {}
  );
  req.on("error", () => {});
  req.write(payload);
  req.end();
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});
