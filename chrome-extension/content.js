// VOICE Chrome Extension - Content Script
// Injects voice-to-text directly into any input field, Google search, Facebook, YouTube, etc.

let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let indicator = null;

const DEFAULT_SERVER = "https://voice-app.onrender.com";

function getActiveEditable() {
  const el = document.activeElement;
  if (!el) return null;
  if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") return el;
  if (el.isContentEditable) return el;
  return null;
}

function insertTextAtCursor(text) {
  if (!text) return;
  const target = getActiveEditable();

  if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) {
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

  // ContentEditable or fallback
  if (document.queryCommandSupported && document.queryCommandSupported("insertText")) {
    document.execCommand("insertText", false, text + " ");
  } else {
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

function createIndicator() {
  if (indicator) return indicator;
  const div = document.createElement("div");
  div.id = "voice-extension-indicator";
  div.innerHTML = `
    <div class="voice-ext-pill">
      <span class="voice-ext-dot"></span>
      <span class="voice-ext-text">Сонсож байна... (Alt+Shift+V дарж дуусгах)</span>
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
}

function hideIndicator(delay = 1800) {
  setTimeout(() => {
    if (indicator) {
      indicator.remove();
      indicator = null;
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
      if (audioBlob.size < 1000) {
        updateIndicator("Яриа сонсогдсонгүй", "error");
        hideIndicator();
        return;
      }

      try {
        const server = (await chrome.storage?.sync?.get("serverURL"))?.serverURL || DEFAULT_SERVER;
        const lang = (await chrome.storage?.sync?.get("language"))?.language || "mn";

        const formData = new FormData();
        formData.append("audio", audioBlob, "speech.webm");
        formData.append("language", lang);

        const res = await fetch(`${server}/api/chimege/transcribe`, {
          method: "POST",
          body: formData,
        });

        if (res.ok) {
          const data = await res.json();
          if (data.text && data.text.trim()) {
            insertTextAtCursor(data.text.trim());
            updateIndicator("✅ Бичигдлээ!", "success");
            hideIndicator(1400);
            return;
          }
        }
        updateIndicator("Яриа танигдсангүй", "error");
        hideIndicator();
      } catch (err) {
        updateIndicator("Сервертэй холбогдож чадсангүй", "error");
        hideIndicator();
      }
    };

    mediaRecorder.start();
    isRecording = true;
    updateIndicator("🔴 Ярьж байна... (Alt+Shift+V дарж зогсоох)", "recording");
  } catch (err) {
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

// Listen for keyboard shortcut from background script
chrome.runtime?.onMessage?.addListener((msg) => {
  if (msg.action === "toggle-dictation") {
    toggleRecording();
  }
});

// Also listen to local in-page keydown as direct fallback (Alt+Shift+V)
window.addEventListener("keydown", (e) => {
  if (e.altKey && e.shiftKey && (e.code === "KeyV" || e.key === "V" || e.key === "v")) {
    e.preventDefault();
    toggleRecording();
  }
});
