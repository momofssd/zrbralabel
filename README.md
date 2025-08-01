# Zebra Label & Barcode Reader

A powerful web application that can **read labels**, automatically **find barcodes** within them, and **decode barcode data**—all in one place.

## What It Does

- **Read and analyze label files**: Upload ZPL code, PDF, or image files containing labels.
- **Automatically detect barcodes**: The app scans your label for barcodes (1D, QR, Data Matrix, and more).
- **Read and decode barcode data**: Instantly extract and display the information encoded in each barcode found on your label.

## Key Features

- ZPL code rendering and preview
- Upload support for PDF and image files
- Automatic barcode detection and decoding
- Supports multiple barcode types (1D, QR, Data Matrix, etc.)
- Responsive web interface
- Easy deployment with Docker

## Quick Start (Docker)

1. **Build the Docker image:**
   ```bash
   docker build -t label-reader .
   ```

2. **Run locally:**
   ```bash
   docker run -p 5000:5000 label-reader
   ```

## Deploy to Azure Container Apps

1. Log in to Azure CLI:
   ```bash
   az login
   ```

2. Create a resource group (if not exists):
   ```bash
   az group create --name label-reader-rg --location eastus
   ```

3. Create Azure Container Registry (ACR):
   ```bash
   az acr create --name labelreaderacr --resource-group label-reader-rg --sku Basic --admin-enabled true
   ```

4. Log in to ACR:
   ```bash
   az acr login --name labelreaderacr
   ```

5. Tag and push the image:
   ```bash
   docker tag label-reader labelreaderacr.azurecr.io/label-reader:latest
   docker push labelreaderacr.azurecr.io/label-reader:latest
   ```

6. Create Container Apps environment:
   ```bash
   az containerapp env create \
     --name label-reader-env \
     --resource-group label-reader-rg \
     --location eastus
   ```

7. Deploy to Container Apps:
   ```bash
   az containerapp create \
     --name label-reader \
     --resource-group label-reader-rg \
     --environment label-reader-env \
     --image labelreaderacr.azurecr.io/label-reader:latest \
     --target-port 3000 \
     --ingress external \
     --registry-server labelreaderacr.azurecr.io \
     --query properties.configuration.ingress.fqdn
   ```

## Environment Variables

- `FLASK_APP`: Set to main.py
- `FLASK_ENV`: Set to production in container
- `PORT`: Default is 5000

## System Requirements

The Docker image includes all necessary dependencies:
- Python 3.9
- poppler-utils (for PDF processing)
- libzbar0 (for barcode detection)
- All Python packages listed in requirements.txt

---

**Zebra Label & Barcode Reader** makes it easy to extract barcode data from your labels—just upload and let the app do the rest!
