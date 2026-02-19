const BUTTON_CLASS = "cc-rewrite-button";
const STATUS_CLASS = "cc-rewrite-status";

function getFieldValue(field) {
  if (field instanceof HTMLTextAreaElement || field instanceof HTMLInputElement) {
    return field.value || "";
  }
  return field.textContent || "";
}

function setFieldValue(field, value) {
  if (field instanceof HTMLTextAreaElement || field instanceof HTMLInputElement) {
    field.value = value;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
    return;
  }
  field.textContent = value;
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.dispatchEvent(new Event("blur", { bubbles: true }));
}

function findLabelText(field) {
  const container = field.closest("label, .field, .form-group, .input, .control, tr, td, div") || field.parentElement;
  const text = (container ? container.textContent : "") || "";
  return text.trim().slice(0, 120).replace(/\s+/g, " ");
}

function isLikelyCaptionField(field) {
  const attrs = `${field.id || ""} ${field.name || ""} ${field.className || ""}`.toLowerCase();
  const label = findLabelText(field).toLowerCase();
  const haystack = `${attrs} ${label}`;

  if (haystack.includes("caption")) return true;
  if (haystack.includes("cutline")) return true;
  if (haystack.includes("photo description")) return true;
  return false;
}

function buildButton(field) {
  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.gap = "8px";
  wrap.style.alignItems = "center";
  wrap.style.marginTop = "6px";

  const button = document.createElement("button");
  button.type = "button";
  button.className = BUTTON_CLASS;
  button.textContent = "Rewrite Caption";
  button.style.padding = "4px 8px";
  button.style.borderRadius = "6px";
  button.style.border = "1px solid #c8c8c8";
  button.style.background = "#f3f5f7";
  button.style.cursor = "pointer";

  const status = document.createElement("span");
  status.className = STATUS_CLASS;
  status.style.fontSize = "12px";
  status.style.color = "#4d5966";

  button.addEventListener("click", async () => {
    const original = getFieldValue(field).trim();
    if (!original) {
      status.textContent = "No caption text found.";
      return;
    }

    button.disabled = true;
    status.textContent = "Rewriting...";

    chrome.runtime.sendMessage(
      {
        type: "rewriteCaption",
        caption: original,
        pageUrl: location.href,
        fieldHint: `${field.name || ""} ${field.id || ""}`.trim()
      },
      (response) => {
        button.disabled = false;
        if (!response || !response.ok) {
          status.textContent = (response && response.error) || "Rewrite failed.";
          return;
        }

        const rewritten = (response.caption || "").trim();
        if (!rewritten) {
          status.textContent = "Empty rewrite response.";
          return;
        }

        setFieldValue(field, rewritten);
        if (response.changed) {
          status.textContent = "Caption updated.";
        } else if (response.reason) {
          status.textContent = `No change: ${response.reason}`;
        } else {
          status.textContent = "No change needed.";
        }
      }
    );
  });

  wrap.appendChild(button);
  wrap.appendChild(status);
  return wrap;
}

function injectButtons(root = document) {
  const candidates = [
    ...root.querySelectorAll("textarea"),
    ...root.querySelectorAll('input[type="text"]'),
    ...root.querySelectorAll('[contenteditable="true"]')
  ];

  for (const field of candidates) {
    if (!(field instanceof HTMLElement)) continue;
    if (field.dataset.ccInjected === "1") continue;
    if (!isLikelyCaptionField(field)) continue;

    const controls = buildButton(field);
    field.insertAdjacentElement("afterend", controls);
    field.dataset.ccInjected = "1";
  }
}

const observer = new MutationObserver(() => injectButtons());
observer.observe(document.documentElement, { childList: true, subtree: true });
injectButtons();
