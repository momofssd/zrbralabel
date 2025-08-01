let currentImageUrl = null;
let selectedFile = null;

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    document.querySelector(`.tab-button[onclick="switchTab('${tabName}')"]`).classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}Tab`).classList.add('active');

    // Clear previous results
    clearBarcodeResults();
    document.getElementById('errorMessage').textContent = '';
    document.getElementById('labelImage').style.display = 'none';
}

function handleFileUpload() {
    const fileInput = document.getElementById('fileInput');
    const readFileBarcodesButton = document.getElementById('readFileBarcodesButton');
    const errorMessage = document.getElementById('errorMessage');

    selectedFile = fileInput.files[0];
    errorMessage.textContent = '';

    if (selectedFile) {
        const validTypes = ['application/pdf', 'image/png', 'image/jpeg'];
        if (validTypes.includes(selectedFile.type)) {
            readFileBarcodesButton.style.display = 'block';
        } else {
            errorMessage.textContent = 'Invalid file type. Please upload a PDF or image file.';
            readFileBarcodesButton.style.display = 'none';
            selectedFile = null;
            fileInput.value = '';
        }
    } else {
        readFileBarcodesButton.style.display = 'none';
    }
}

async function readFileBarcodesButton() {
    if (!selectedFile) {
        document.getElementById('errorMessage').textContent = 'Please select a file first.';
        return;
    }

    const barcodeResults = document.getElementById('barcodeResults');
    const barcodeList = document.getElementById('barcodeList');
    const barcodeError = document.getElementById('barcodeError');

    // Clear previous results
    clearBarcodeResults();
    barcodeError.textContent = '';

    // Show loading state
    barcodeResults.style.display = 'block';
    barcodeList.innerHTML = '<div class="loading">Reading barcodes...</div>';

    try {
        const formData = new FormData();
        formData.append('file', selectedFile);

        const response = await fetch('/upload-file', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        // Display results
        if (data.barcodes && data.barcodes.length > 0) {
            barcodeList.innerHTML = '';
            data.barcodes.forEach((barcode, index) => {
                const barcodeItem = document.createElement('div');
                barcodeItem.className = 'barcode-item';
                barcodeItem.innerHTML = `
                    <div class="barcode-header">
                        <strong>Barcode ${index + 1}</strong>
                        <span class="barcode-type">${barcode.type}</span>
                        ${barcode.page ? `<span class="barcode-page">Page ${barcode.page}</span>` : ''}
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
            barcodeList.innerHTML = '<div class="no-barcodes">No barcodes found in the file</div>';
        }

    } catch (error) {
        barcodeError.textContent = `Error reading barcodes: ${error.message}`;
        barcodeList.innerHTML = '';
    }
}

async function generateLabel() {
    const zplInput = document.getElementById('zplInput').value;
    const labelImage = document.getElementById('labelImage');
    const errorMessage = document.getElementById('errorMessage');
    const downloadButton = document.getElementById('downloadButton');
    const readBarcodesButton = document.getElementById('readBarcodesButton');

    // Clear previous output
    labelImage.style.display = 'none';
    errorMessage.textContent = '';
    downloadButton.style.display = 'none';
    readBarcodesButton.style.display = 'none';
    clearBarcodeResults();
    
    if (currentImageUrl) {
        URL.revokeObjectURL(currentImageUrl);
        currentImageUrl = null;
    }

    try {
        const response = await fetch('/generate-label', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ zpl: zplInput })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }

        const blob = await response.blob();
        currentImageUrl = URL.createObjectURL(blob);
        labelImage.src = currentImageUrl;
        labelImage.style.display = 'block';
        downloadButton.style.display = 'block';
        readBarcodesButton.style.display = 'block';
    } catch (error) {
        errorMessage.textContent = `Error generating label: ${error.message}`;
    }
}

async function readBarcodes() {
    const zplInput = document.getElementById('zplInput').value;
    const barcodeResults = document.getElementById('barcodeResults');
    const barcodeList = document.getElementById('barcodeList');
    const barcodeError = document.getElementById('barcodeError');

    // Clear previous results
    clearBarcodeResults();
    barcodeError.textContent = '';

    // Show loading state
    barcodeResults.style.display = 'block';
    barcodeList.innerHTML = '<div class="loading">Reading barcodes...</div>';

    try {
        const response = await fetch('/read-barcodes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ zpl: zplInput })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        // Display results
        if (data.barcodes && data.barcodes.length > 0) {
            barcodeList.innerHTML = '';
            data.barcodes.forEach((barcode, index) => {
                const barcodeItem = document.createElement('div');
                barcodeItem.className = 'barcode-item';
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
            barcodeList.innerHTML = '<div class="no-barcodes">No barcodes found in the label</div>';
        }

    } catch (error) {
        barcodeError.textContent = `Error reading barcodes: ${error.message}`;
        barcodeList.innerHTML = '';
    }
}

function clearBarcodeResults() {
    const barcodeResults = document.getElementById('barcodeResults');
    const barcodeList = document.getElementById('barcodeList');
    
    if (barcodeResults) {
        barcodeResults.style.display = 'none';
    }
    if (barcodeList) {
        barcodeList.innerHTML = '';
    }
}

function downloadLabel() {
    if (currentImageUrl) {
        const link = document.createElement('a');
        link.href = currentImageUrl;
        link.download = 'label.png';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}
