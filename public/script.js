let currentImageUrl = null;

async function generateLabel() {
    const zplInput = document.getElementById('zplInput').value;
    const labelImage = document.getElementById('labelImage');
    const errorMessage = document.getElementById('errorMessage');
    const downloadButton = document.getElementById('downloadButton');

    // Clear previous output
    labelImage.style.display = 'none';
    errorMessage.textContent = '';
    downloadButton.style.display = 'none';
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
    } catch (error) {
        errorMessage.textContent = `Error generating label: ${error.message}`;
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
