let currentImageUrl = null;
let selectedFile = null;
let zebraFile = null;
let generatedLabels = [];
let currentLabelIndex = 0;

function switchTab(tabName) {
  // Update tab buttons
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.remove("active");
  });
  document
    .querySelector(`.tab-button[onclick="switchTab('${tabName}')"]`)
    .classList.add("active");

  // Update tab content
  document.querySelectorAll(".tab-content").forEach((content) => {
    content.classList.remove("active");
  });
  document.getElementById(`${tabName}Tab`).classList.add("active");

  // Clear previous results
  clearBarcodeResults();
  document.getElementById("errorMessage").textContent = "";
  document.getElementById("labelImage").style.display = "none";
}

function handleFileUpload() {
  const fileInput = document.getElementById("fileInput");
  const readFileBarcodesButton = document.getElementById(
    "readFileBarcodesButton",
  );
  const errorMessage = document.getElementById("errorMessage");

  selectedFile = fileInput.files[0];
  errorMessage.textContent = "";

  if (selectedFile) {
    const validTypes = ["application/pdf", "image/png", "image/jpeg"];
    if (validTypes.includes(selectedFile.type)) {
      readFileBarcodesButton.style.display = "block";
    } else {
      errorMessage.textContent =
        "Invalid file type. Please upload a PDF or image file.";
      readFileBarcodesButton.style.display = "none";
      selectedFile = null;
      fileInput.value = "";
    }
  } else {
    readFileBarcodesButton.style.display = "none";
  }
}

async function readFileBarcodesButton() {
  if (!selectedFile) {
    document.getElementById("errorMessage").textContent =
      "Please select a file first.";
    return;
  }

  const barcodeResults = document.getElementById("barcodeResults");
  const barcodeList = document.getElementById("barcodeList");
  const barcodeError = document.getElementById("barcodeError");
  const labelImage = document.getElementById("labelImage");

  // Clear previous results
  clearBarcodeResults();
  barcodeError.textContent = "";
  labelImage.style.display = "none";

  // Show loading state
  barcodeResults.style.display = "block";
  barcodeList.innerHTML = '<div class="loading">Reading barcodes...</div>';

  try {
    const formData = new FormData();
    formData.append("file", selectedFile);

    const response = await fetch("/upload-file", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }

    // Display the image if available
    if (data.image) {
      labelImage.src = `data:image/png;base64,${data.image}`;
      labelImage.style.display = "block";
    }

    // Display results
    if (data.barcodes && data.barcodes.length > 0) {
      barcodeList.innerHTML = "";
      data.barcodes.forEach((barcode, index) => {
        const barcodeItem = document.createElement("div");
        barcodeItem.className = "barcode-item";
        barcodeItem.innerHTML = `
                    <div class="barcode-header">
                        <strong>Barcode ${index + 1}</strong>
                        <span class="barcode-type">${barcode.type}</span>
                        ${barcode.page ? `<span class="barcode-page">Page ${barcode.page}</span>` : ""}
                    </div>
                    <div class="barcode-data">${barcode.data}</div>
                    <div class="barcode-location">
                        Location: (${barcode.location.x}, ${barcode.location.y}) 
                        Size: ${barcode.location.width}×${barcode.location.height}
                    </div>
                `;
        barcodeList.appendChild(barcodeItem);
      });
    } else {
      barcodeList.innerHTML =
        '<div class="no-barcodes">No barcodes found in the file</div>';
    }
  } catch (error) {
    barcodeError.textContent = `Error reading barcodes: ${error.message}`;
    barcodeList.innerHTML = "";
  }
}

async function generateLabel() {
  const zplInput = document.getElementById("zplInput").value;
  const labelImage = document.getElementById("labelImage");
  const errorMessage = document.getElementById("errorMessage");
  const downloadButton = document.getElementById("downloadButton");
  const readBarcodesButton = document.getElementById("readBarcodesButton");

  // Clear previous output
  labelImage.style.display = "none";
  errorMessage.textContent = "";
  downloadButton.style.display = "none";
  readBarcodesButton.style.display = "none";
  clearBarcodeResults();

  if (currentImageUrl) {
    URL.revokeObjectURL(currentImageUrl);
    currentImageUrl = null;
  }

  try {
    const response = await fetch("/generate-label", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ zpl: zplInput }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(
        errorData.error || `HTTP error! status: ${response.status}`,
      );
    }

    const blob = await response.blob();
    currentImageUrl = URL.createObjectURL(blob);
    labelImage.src = currentImageUrl;
    labelImage.style.display = "block";
    downloadButton.style.display = "block";
    readBarcodesButton.style.display = "block";
  } catch (error) {
    errorMessage.textContent = `Error generating label: ${error.message}`;
  }
}

async function readBarcodes() {
  const zplInput = document.getElementById("zplInput").value;
  const barcodeResults = document.getElementById("barcodeResults");
  const barcodeList = document.getElementById("barcodeList");
  const barcodeError = document.getElementById("barcodeError");

  // Clear previous results
  clearBarcodeResults();
  barcodeError.textContent = "";

  // Show loading state
  barcodeResults.style.display = "block";
  barcodeList.innerHTML = '<div class="loading">Reading barcodes...</div>';

  try {
    const response = await fetch("/read-barcodes", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ zpl: zplInput }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }

    // Display results
    if (data.barcodes && data.barcodes.length > 0) {
      barcodeList.innerHTML = "";
      data.barcodes.forEach((barcode, index) => {
        const barcodeItem = document.createElement("div");
        barcodeItem.className = "barcode-item";
        barcodeItem.innerHTML = `
                    <div class="barcode-header">
                        <strong>Barcode ${index + 1}</strong>
                        <span class="barcode-type">${barcode.type}</span>
                    </div>
                    <div class="barcode-data">${barcode.data}</div>
                    <div class="barcode-location">
                        Location: (${barcode.location.x}, ${barcode.location.y}) 
                        Size: ${barcode.location.width}×${barcode.location.height}
                    </div>
                `;
        barcodeList.appendChild(barcodeItem);
      });
    } else {
      barcodeList.innerHTML =
        '<div class="no-barcodes">No barcodes found in the label</div>';
    }
  } catch (error) {
    barcodeError.textContent = `Error reading barcodes: ${error.message}`;
    barcodeList.innerHTML = "";
  }
}

function clearBarcodeResults() {
  const barcodeResults = document.getElementById("barcodeResults");
  const barcodeList = document.getElementById("barcodeList");

  if (barcodeResults) {
    barcodeResults.style.display = "none";
  }
  if (barcodeList) {
    barcodeList.innerHTML = "";
  }
}

function downloadLabel() {
  if (currentImageUrl) {
    const link = document.createElement("a");
    link.href = currentImageUrl;
    link.download = "label.png";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}

// Zebra File Upload Tab Functions
function handleZebraFileUpload() {
  const fileInput = document.getElementById("zebraFileInput");
  const generateButton = document.getElementById("generateFromPdfButton");
  const errorMessage = document.getElementById("errorMessage");

  zebraFile = fileInput.files[0];
  errorMessage.textContent = "";

  if (zebraFile) {
    if (zebraFile.type === "application/pdf") {
      generateButton.style.display = "block";
    } else {
      errorMessage.textContent = "Invalid file type. Please upload a PDF file.";
      generateButton.style.display = "none";
      zebraFile = null;
      fileInput.value = "";
    }
  } else {
    generateButton.style.display = "none";
  }
}

async function generateLabelsFromPdf() {
  if (!zebraFile) {
    document.getElementById("errorMessage").textContent =
      "Please select a PDF file first.";
    return;
  }

  const errorMessage = document.getElementById("errorMessage");
  const labelImage = document.getElementById("labelImage");
  const generateButton = document.getElementById("generateFromPdfButton");
  const readBarcodesButton = document.getElementById("readZebraBarcodesButton");
  const downloadAllButton = document.getElementById("downloadAllLabelsButton");
  const labelNavigation = document.getElementById("labelNavigation");

  // Clear previous results
  errorMessage.textContent = "";
  labelImage.style.display = "none";
  clearBarcodeResults();
  generatedLabels = [];
  currentLabelIndex = 0;

  // Show loading state
  generateButton.disabled = true;
  generateButton.textContent = "Generating...";

  try {
    const formData = new FormData();
    formData.append("file", zebraFile);

    const response = await fetch("/extract-zpl-from-pdf", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }

    if (!data.labels || data.labels.length === 0) {
      throw new Error("No ZPL codes found in the PDF");
    }

    // Store generated labels
    generatedLabels = data.labels;
    currentLabelIndex = 0;

    // Display first label
    displayCurrentLabel();

    // Show controls
    readBarcodesButton.style.display = "block";
    downloadAllButton.style.display = "block";

    if (generatedLabels.length > 1) {
      labelNavigation.style.display = "flex";
      updateNavigationButtons();
    }
  } catch (error) {
    errorMessage.textContent = `Error generating labels: ${error.message}`;
  } finally {
    generateButton.disabled = false;
    generateButton.textContent = "Generate Labels";
  }
}

function displayCurrentLabel() {
  const labelImage = document.getElementById("labelImage");
  const labelCounter = document.getElementById("labelCounter");

  if (
    generatedLabels.length > 0 &&
    currentLabelIndex < generatedLabels.length
  ) {
    const currentLabel = generatedLabels[currentLabelIndex];
    labelImage.src = `data:image/png;base64,${currentLabel.image}`;
    labelImage.style.display = "block";
    labelCounter.textContent = `Label ${currentLabelIndex + 1} of ${generatedLabels.length}`;
  }
}

function previousLabel() {
  if (currentLabelIndex > 0) {
    currentLabelIndex--;
    displayCurrentLabel();
    updateNavigationButtons();
    clearBarcodeResults();
  }
}

function nextLabel() {
  if (currentLabelIndex < generatedLabels.length - 1) {
    currentLabelIndex++;
    displayCurrentLabel();
    updateNavigationButtons();
    clearBarcodeResults();
  }
}

function updateNavigationButtons() {
  const prevButton = document.getElementById("prevLabelButton");
  const nextButton = document.getElementById("nextLabelButton");

  prevButton.disabled = currentLabelIndex === 0;
  nextButton.disabled = currentLabelIndex === generatedLabels.length - 1;
}

async function readZebraBarcodes() {
  if (
    generatedLabels.length === 0 ||
    currentLabelIndex >= generatedLabels.length
  ) {
    document.getElementById("errorMessage").textContent =
      "No label to read barcodes from.";
    return;
  }

  const barcodeResults = document.getElementById("barcodeResults");
  const barcodeList = document.getElementById("barcodeList");
  const barcodeError = document.getElementById("barcodeError");

  // Clear previous results
  clearBarcodeResults();
  barcodeError.textContent = "";

  // Show loading state
  barcodeResults.style.display = "block";
  barcodeList.innerHTML = '<div class="loading">Reading barcodes...</div>';

  try {
    const currentLabel = generatedLabels[currentLabelIndex];

    const response = await fetch("/read-barcodes-from-image", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ image: currentLabel.image }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }

    // Display results
    if (data.barcodes && data.barcodes.length > 0) {
      barcodeList.innerHTML = "";
      data.barcodes.forEach((barcode, index) => {
        const barcodeItem = document.createElement("div");
        barcodeItem.className = "barcode-item";
        barcodeItem.innerHTML = `
                    <div class="barcode-header">
                        <strong>Barcode ${index + 1}</strong>
                        <span class="barcode-type">${barcode.type}</span>
                    </div>
                    <div class="barcode-data">${barcode.data}</div>
                    <div class="barcode-location">
                        Location: (${barcode.location.x}, ${barcode.location.y}) 
                        Size: ${barcode.location.width}×${barcode.location.height}
                    </div>
                `;
        barcodeList.appendChild(barcodeItem);
      });
    } else {
      barcodeList.innerHTML =
        '<div class="no-barcodes">No barcodes found in the label</div>';
    }
  } catch (error) {
    barcodeError.textContent = `Error reading barcodes: ${error.message}`;
    barcodeList.innerHTML = "";
  }
}

async function downloadAllLabels() {
  if (generatedLabels.length === 0) {
    document.getElementById("errorMessage").textContent =
      "No labels to download.";
    return;
  }

  const errorMessage = document.getElementById("errorMessage");
  const downloadButton = document.getElementById("downloadAllLabelsButton");

  // Show loading state
  downloadButton.disabled = true;
  downloadButton.textContent = "Generating PDF...";

  try {
    const response = await fetch("/generate-pdf-from-labels", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ labels: generatedLabels }),
    });

    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "zebra_labels.pdf";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  } catch (error) {
    errorMessage.textContent = `Error downloading PDF: ${error.message}`;
  } finally {
    downloadButton.disabled = false;
    downloadButton.textContent = "Download All as PDF";
  }
}
