import mermaid from "/static/vendor/mermaid.esm.min.mjs";

const textarea = document.getElementById("diagram-source");
const preview = document.getElementById("preview");
const errorBox = document.getElementById("preview-error");
const renderedSvgField = document.getElementById("rendered-svg");

mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });

async function renderPreview() {
  const source = textarea.value.trim();
  if (!source) {
    preview.innerHTML = "";
    errorBox.hidden = true;
    return;
  }

  try {
    const renderId = `preview-${crypto.randomUUID()}`;
    const { svg } = await mermaid.render(renderId, source);
    preview.innerHTML = svg;
    renderedSvgField.value = svg;
    errorBox.hidden = true;
  } catch (error) {
    preview.innerHTML = "";
    renderedSvgField.value = "";
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
}

textarea.addEventListener("input", () => {
  window.clearTimeout(window.previewDebounce);
  window.previewDebounce = window.setTimeout(renderPreview, 150);
});

renderPreview();
