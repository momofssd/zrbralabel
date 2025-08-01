FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y \
        libgl1 \
        poppler-utils \
        libglib2.0-0 \
        libzbar0 \
        libdmtx0b \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "main.py"]
