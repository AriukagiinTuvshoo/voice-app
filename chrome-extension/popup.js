document.addEventListener("DOMContentLoaded", () => {
  const langSelect = document.getElementById("lang");
  const serverInput = document.getElementById("server");
  const saveBtn = document.getElementById("save");
  const statusDiv = document.getElementById("status");

  chrome.storage?.sync?.get(["language", "serverURL"], (items) => {
    if (items?.language) langSelect.value = items.language;
    if (items?.serverURL) serverInput.value = items.serverURL;
  });

  saveBtn.addEventListener("click", () => {
    chrome.storage?.sync?.set(
      {
        language: langSelect.value,
        serverURL: serverInput.value.trim().replace(/\/$/, ""),
      },
      () => {
        statusDiv.textContent = "Тохиргоо амжилттай хадгалагдлаа!";
        setTimeout(() => { statusDiv.textContent = ""; }, 2000);
      }
    );
  });
});
