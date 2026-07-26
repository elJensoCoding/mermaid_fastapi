const textarea = document.getElementById("diagram-source");
const preview = document.getElementById("preview");
const errorBox = document.getElementById("preview-error");
const renderedSvgField = document.getElementById("rendered-svg");
const downloadPngButton = document.getElementById("download-png");
const exportStatus = document.getElementById("export-status");
const mermaid = window.mermaid;

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

function setExportStatus(message, isError = false) {
  exportStatus.textContent = message;
  exportStatus.className = `status ${isError ? "error" : "muted"}`;
  exportStatus.hidden = !message;
}

function buildDownloadName() {
  const slugInput = document.querySelector('input[name="slug"]');
  const titleInput = document.querySelector('input[name="title"]');
  const keyInput = document.querySelector('input[name="key"]');

  const candidate =
    slugInput?.value?.trim() ||
    titleInput?.value?.trim() ||
    keyInput?.value?.trim() ||
    "diagramm";

  return candidate
    .toLowerCase()
    .replace(/[^a-z0-9-_]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-|-$/g, "") || "diagramm";
}

async function downloadPreviewAsPng() {
  const svgElement = preview.querySelector("svg");
  if (!svgElement) {
    setExportStatus("Kein SVG fuer den PNG-Export verfuegbar.", true);
    return;
  }

  setExportStatus("");

  const serializer = new XMLSerializer();
  const svgMarkup = serializer.serializeToString(svgElement);
  const svgBlob = new Blob([svgMarkup], { type: "image/svg+xml;charset=utf-8" });
  const svgUrl = URL.createObjectURL(svgBlob);

  try {
    const image = new Image();
    image.decoding = "async";

    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = () => reject(new Error("SVG konnte nicht in ein Bild geladen werden."));
      image.src = svgUrl;
    });

    const viewBox = svgElement.viewBox.baseVal;
    const width =
      viewBox?.width ||
      Number(svgElement.getAttribute("width")) ||
      svgElement.getBoundingClientRect().width ||
      1200;
    const height =
      viewBox?.height ||
      Number(svgElement.getAttribute("height")) ||
      svgElement.getBoundingClientRect().height ||
      800;

    const scale = 2;
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));

    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Canvas-Kontext konnte nicht erstellt werden.");
    }

    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.drawImage(image, 0, 0, width, height);

    const pngUrl = canvas.toDataURL("image/png");
    const link = document.createElement("a");
    link.href = pngUrl;
    link.download = `${buildDownloadName()}.png`;
    document.body.append(link);
    link.click();
    link.remove();
    setExportStatus("PNG wurde heruntergeladen.");
  } catch (error) {
    setExportStatus(error.message, true);
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
}

textarea.addEventListener("input", () => {
  window.clearTimeout(window.previewDebounce);
  window.previewDebounce = window.setTimeout(renderPreview, 150);
});

downloadPngButton.addEventListener("click", downloadPreviewAsPng);

renderPreview();
