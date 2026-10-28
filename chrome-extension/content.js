// VOICE Chrome Extension - Content Script (100% Local First)
// Injects voice-to-text directly into Facebook, Google, YouTube, Messenger, Word Online, etc.

(function () {
  if (window.__voiceExtensionLoaded) return;
  window.__voiceExtensionLoaded = true;

  let isRecording = false;
  let mediaRecorder = null;
  let audioChunks = [];
  let indicator = null;
  let floatingMicBtn = null;
  let lastFocusedInput = null;

  let currentSettings = {
    shortcut: "F8",
    language: "mn",
    showFloatingMic: true,
    serverURL: "http://localhost:3000",
  };

  // Load settings with auto-migration to Local
  if (typeof chrome !== "undefined" && chrome.storage?.sync) {
    chrome.storage.sync.get(
      ["shortcut", "language", "showFloatingMic", "serverURL"],
      (items) => {
        if (items) {
          currentSettings = { ...currentSettings, ...items };
          if (currentSettings.serverURL && currentSettings.serverURL.includes("onrender.com")) {
            currentSettings.serverURL = "http://localhost:3000";
            chrome.storage.sync.set({ serverURL: "http://localhost:3000" });
          }
        }
        renderFloatingMic();
      }
    );
  }

  // Keep track of the active text field (inputs, textareas, and contenteditable like Facebook)
  document.addEventListener("focusin", (e) => {
    if (isEditable(e.target)) {
      lastFocusedInput = e.target;
    }
  });

  function isEditable(el) {
    if (!el) return false;
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") return true;
    if (el.isContentEditable) return true;
    if (el.getAttribute && el.getAttribute("role") === "textbox") return true;
    return false;
  }

  function getTargetElement() {
    const active = document.activeElement;
    if (isEditable(active)) return active;
    if (lastFocusedInput && document.body.contains(lastFocusedInput)) {
      return lastFocusedInput;
    }
    return null;
  }

  function insertTextAtCursor(text) {
    if (!text) return;
    const target = getTargetElement();

    if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) {
      target.focus();
      const start = target.selectionStart ?? target.value.length;
      const end = target.selectionEnd ?? target.value.length;
      const val = target.value;
      const insert = (start > 0 && !/\s$/.test(val.slice(0, start)) ? " " : "") + text + " ";
      target.value = val.slice(0, start) + insert + val.slice(end);
      target.selectionStart = target.selectionEnd = start + insert.length;
      target.dispatchEvent(new Event("input", { bubbles: true }));
      target.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }

    // Facebook / Messenger / Gmail / Docs contenteditable support
    if (target && (target.isContentEditable || target.getAttribute("role") === "textbox")) {
      target.focus();
    }

    let inserted = false;
    if (document.queryCommandSupported && document.queryCommandSupported("insertText")) {
      try {
        inserted = document.execCommand("insertText", false, text + " ");
      } catch {}
    }

    if (!inserted) {
      const sel = window.getSelection();
      if (sel && sel.rangeCount > 0) {
        const range = sel.getRangeAt(0);
        range.deleteContents();
        const node = document.createTextNode(text + " ");
        range.insertNode(node);
        range.collapse(false);
      }
    }
  }

  // Floating on-page Mic Button (so user can just tap it on screen!)
  function renderFloatingMic() {
    if (!currentSettings.showFloatingMic) {
      if (floatingMicBtn) floatingMicBtn.remove();
      floatingMicBtn = null;
      return;
    }
    if (floatingMicBtn) return;

    const btn = document.createElement("div");
    btn.id = "voice-floating-trigger-btn";
    btn.innerHTML = `<span style="font-size:18px;">🎤</span><span class="voice-floating-lbl">VOICE</span>`;
    btn.title = `VOICE: Дарж ярих (Товчлуур: ${currentSettings.shortcut})`;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleRecording();
    });
    document.body.appendChild(btn);
    floatingMicBtn = btn;
  }

  function createIndicator() {
    if (indicator) return indicator;
    const div = document.createElement("div");
    div.id = "voice-extension-indicator";
    div.innerHTML = `
      <div class="voice-ext-pill">
        <span class="voice-ext-dot"></span>
        <span class="voice-ext-text">Сонсож байна...</span>
      </div>
    `;
    document.body.appendChild(div);
    indicator = div;
    return div;
  }

  function updateIndicator(text, status = "recording") {
    const ind = createIndicator();
    ind.className = `voice-status-${status}`;
    const txt = ind.querySelector(".voice-ext-text");
    if (txt) txt.textContent = text;

    if (floatingMicBtn) {
      floatingMicBtn.classList.toggle("recording", status === "recording");
    }
  }

  function hideIndicator(delay = 1800) {
    setTimeout(() => {
      if (indicator) {
        indicator.remove();
        indicator = null;
      }
      if (floatingMicBtn) {
        floatingMicBtn.classList.remove("recording");
      }
    }, delay);
  }

  async function startRecording() {
    if (isRecording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        updateIndicator("Боловсруулж байна...", "processing");

        const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/webm" });
        if (audioBlob.size < 1200) {
          updateIndicator("Яриа сонсогдсонгүй", "error");
          hideIndicator();
          return;
        }

        const formData = new FormData();
        formData.append("audio", audioBlob, "speech.webm");
        formData.append("language", currentSettings.language || "mn");

        // 1. Try Local Next.js Server (http://localhost:3000)
        let successText = "";
        try {
          const sUrl = (currentSettings.serverURL || "http://localhost:3000").replace(/\/$/, "");
          const res = await fetch(`${sUrl}/api/chimege/transcribe`, {
            method: "POST",
            body: formData,
          });

          if (res.ok) {
            const data = await res.json();
            if (data.text && data.text.trim()) {
              successText = data.text.trim();
            }
          }
        } catch {
          // If port 3000 fails, try direct python backend
        }

        // 2. Fallback to Local Python STT Server directly (http://127.0.0.1:8000)
        if (!successText) {
          try {
            const pyRes = await fetch("http://127.0.0.1:8000/transcribe", {
              method: "POST",
              body: formData,
            });
            if (pyRes.ok) {
              const pyData = await pyRes.json();
              if (pyData.text && pyData.text.trim()) {
                successText = pyData.text.trim();
              }
            }
          } catch {}
        }

        if (successText) {
          insertTextAtCursor(successText);
          updateIndicator(`✅ "${successText.slice(0, 22)}..."`, "success");
          hideIndicator(1500);
        } else {
          updateIndicator("Тод ярина уу эсвэл сервер асаагаарай", "error");
          hideIndicator(2200);
        }
      };

      mediaRecorder.start();
      isRecording = true;
      updateIndicator(`🔴 Сонсож байна... (${currentSettings.shortcut} дарж дуусгах)`, "recording");
    } catch {
      updateIndicator("⚠️ Микрофоны зөвшөөрөл шалгана уу", "error");
      hideIndicator(2500);
    }
  }

  function stopRecording() {
    if (!isRecording || !mediaRecorder) return;
    isRecording = false;
    mediaRecorder.stop();
  }

  function toggleRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  // Keyboard shortcut listener
  window.addEventListener("keydown", (e) => {
    const s = currentSettings.shortcut || "F8";

    let match = false;
    if (s === "F8" && e.code === "F8") match = true;
    else if (s === "F2" && e.code === "F2") match = true;
    else if (s === "Ctrl+Space" && e.ctrlKey && e.code === "Space") match = true;
    else if (s === "Ctrl+Alt" && e.ctrlKey && e.altKey) match = true;
    else if (s === "Alt+Shift+V" && e.altKey && e.shiftKey && (e.code === "KeyV" || e.key === "V" || e.key === "v")) match = true;

    if (match) {
      e.preventDefault();
      toggleRecording();
    }
  });

  // Extension runtime listener
  if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
    chrome.runtime.onMessage.addListener((msg) => {
      if (msg.action === "toggle-dictation") {
        toggleRecording();
      } else if (msg.action === "update-settings") {
        currentSettings = { ...currentSettings, ...msg.settings };
        renderFloatingMic();
      }
    });
  }

  renderFloatingMic();
})();
