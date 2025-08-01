# Zebra Printer Label Viewer

A web application for viewing and analyzing Zebra printer labels, with support for barcode detection in both ZPL code and uploaded files (PDF/images).

## Features

- ZPL code rendering
- PDF and image file upload
- Multiple barcode type detection (1D, QR, Data Matrix)
- Responsive design
- Docker containerization

## Docker Build Instructions

1. Build the Docker image:
```bash
docker build -t label-reader .
```

2. Run locally (optional):
```bash
docker run -p 3000:3000 label-reader
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

The application uses the following environment variables:
- `FLASK_APP`: Set to main.py
- `FLASK_ENV`: Set to production in container
- `PORT`: Default is 3000

## System Requirements

The Docker image includes all necessary dependencies:
- Python 3.9
- poppler-utils (for PDF processing)
- libzbar0 (for barcode detection)
- All Python packages listed in requirements.txt
