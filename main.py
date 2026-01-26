import requests
from flask import Flask, request, send_file, jsonify, render_template
from flask_cors import CORS
import io
from PIL import Image
import cv2
import numpy as np
from pyzbar import pyzbar
from pylibdmtx import pylibdmtx
import functools
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import threading
import pdf2image
import os
import tempfile
import base64
import hashlib
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# --- Configuration & Persistent Cache Setup ---
CACHE_DIR = "label_storage_cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

app = Flask(__name__, static_folder='public', static_url_path='', template_folder='public')
CORS(app)

# --- Resilient Session (Handles the 429 "Too Many Requests" Burst Limit) ---
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=1,  # Waits 1s, 2s, 4s between retries
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST"]
)
session.mount('http://', HTTPAdapter(max_retries=retries))
session.mount('https://', HTTPAdapter(max_retries=retries))

# --- Cache Helper Functions ---
def get_zpl_hash(zpl):
    """Creates a unique MD5 hash for the ZPL string to use as a filename."""
    return hashlib.md5(zpl.encode('utf-8')).hexdigest()

def get_cached_label(zpl_hash):
    """Returns the binary image data if it exists on disk."""
    cache_path = os.path.join(CACHE_DIR, f"{zpl_hash}.png")
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as f:
            return f.read()
    return None

def save_to_cache(zpl_hash, content):
    """Saves the binary label image to disk."""
    cache_path = os.path.join(CACHE_DIR, f"{zpl_hash}.png")
    with open(cache_path, 'wb') as f:
        f.write(content)

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-label', methods=['POST'])
def generate_label():
    zpl = request.json.get('zpl')
    if not zpl:
        return jsonify({'error': 'ZPL code is required'}), 400

    zpl_hash = get_zpl_hash(zpl)
    
    # Check disk cache first to save API quota
    cached_data = get_cached_label(zpl_hash)
    if cached_data:
        return send_file(io.BytesIO(cached_data), mimetype='image/png')

    try:
        headers = {'Accept': 'image/png'}
        response = session.post(
            'http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/',
            data=zpl,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            save_to_cache(zpl_hash, response.content)
            return send_file(io.BytesIO(response.content), mimetype='image/png')
        else:
            return jsonify({'error': f'Labelary Error: {response.text}'}), response.status_code
    except Exception as e:
        return jsonify({'error': f'Connection error: {str(e)}'}), 500

def process_image_for_barcodes(image_data):
    """Process image data and return barcodes found"""
    if isinstance(image_data, (bytes, bytearray)):
        nparr = np.frombuffer(image_data, np.uint8)
        opencv_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        opencv_image = image_data

    if opencv_image is None:
        raise ValueError('Invalid image data')
    
    gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    barcode_data = []
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        standard_future = executor.submit(process_standard_barcodes, gray)
        pil_image = Image.fromarray(cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB))
        matrix_future = executor.submit(process_datamatrix, pil_image)
        
        try:
            barcode_data.extend(standard_future.result(timeout=2))
            barcode_data.extend(matrix_future.result(timeout=2))
        except TimeoutError:
            if standard_future.done(): barcode_data.extend(standard_future.result())
            if matrix_future.done(): barcode_data.extend(matrix_future.result())
    
    return barcode_data

def process_standard_barcodes(gray):
    try:
        barcodes = pyzbar.decode(gray)
        return [{
            'data': barcode.data.decode('utf-8'),
            'type': barcode.type,
            'location': {'x': barcode.rect[0], 'y': barcode.rect[1], 'width': barcode.rect[2], 'height': barcode.rect[3]}
        } for barcode in barcodes]
    except Exception: return []

def process_datamatrix(pil_image):
    try:
        dmtx_results = pylibdmtx.decode(pil_image, timeout=1000)
        return [{
            'data': code.data.decode('utf-8'),
            'type': 'DataMatrix',
            'location': {'x': code.rect[0], 'y': code.rect[1], 'width': code.rect[2], 'height': code.rect[3]}
        } for code in dmtx_results]
    except Exception: return []

@app.route('/read-barcodes', methods=['POST'])
def read_barcodes():
    try:
        zpl = request.json.get('zpl')
        if not zpl:
            return jsonify({'error': 'ZPL code is required'}), 400

        zpl_hash = get_zpl_hash(zpl)
        label_content = get_cached_label(zpl_hash)

        if not label_content:
            response = session.post(
                'http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/',
                data=zpl, headers={'Accept': 'image/png'}, timeout=10
            )
            if response.status_code != 200:
                return jsonify({'error': 'Error generating label'}), response.status_code
            label_content = response.content
            save_to_cache(zpl_hash, label_content)

        barcode_data = process_image_for_barcodes(label_content)
        return jsonify({'message': f'Found {len(barcode_data)} barcode(s)', 'barcodes': barcode_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload-file', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        file_ext = os.path.splitext(file.filename)[1].lower()
        file_content = file.read()
        all_barcodes = []
        image_data = None

        if file_ext == '.pdf':
            with tempfile.TemporaryDirectory() as temp_dir:
                pdf_path = os.path.join(temp_dir, 'temp.pdf')
                with open(pdf_path, 'wb') as f: f.write(file_content)
                images = pdf2image.convert_from_path(pdf_path)
                first_page = images[0]
                img_byte_arr = io.BytesIO()
                first_page.save(img_byte_arr, format='PNG')
                image_data = img_byte_arr.getvalue()
                
                for i, image in enumerate(images):
                    opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                    page_barcodes = process_image_for_barcodes(opencv_image)
                    for b in page_barcodes: b['page'] = i + 1
                    all_barcodes.extend(page_barcodes)
        else:
            image_data = file_content
            all_barcodes.extend(process_image_for_barcodes(file_content))

        image_base64 = base64.b64encode(image_data).decode('utf-8') if image_data else None
        return jsonify({'barcodes': all_barcodes, 'image': image_base64})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/extract-zpl-from-pdf', methods=['POST'])
def extract_zpl_from_pdf():
    try:
        if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        file_content = file.read()
        labels = []
        
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        for page_num, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            if '^XA' in text.upper():
                zpl_code = text.strip()
                zpl_hash = get_zpl_hash(zpl_code)
                img_data = get_cached_label(zpl_hash)
                
                if not img_data:
                    resp = session.post('http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/', 
                                      data=zpl_code, headers={'Accept': 'image/png'})
                    if resp.status_code == 200:
                        img_data = resp.content
                        save_to_cache(zpl_hash, img_data)
                
                if img_data:
                    labels.append({'page': page_num + 1, 'zpl': zpl_code, 'image': base64.b64encode(img_data).decode('utf-8')})
        
        return jsonify({'labels': labels})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/read-barcodes-from-image', methods=['POST'])
def read_barcodes_from_image():
    try:
        data = request.json
        image_data = base64.b64decode(data['image'])
        barcodes = process_image_for_barcodes(image_data)
        return jsonify({'barcodes': barcodes})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/generate-pdf-from-labels', methods=['POST'])
def generate_pdf_from_labels():
    try:
        labels = request.json.get('labels', [])
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.utils import ImageReader
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_path = tmp_file.name
            c = canvas.Canvas(pdf_path, pagesize=letter)
            for label in labels:
                img_data = base64.b64decode(label['image'])
                img_reader = ImageReader(io.BytesIO(img_data))
                c.drawImage(img_reader, 50, 250, width=500, height=350)
                c.showPage()
            c.save()
        
        return send_file(pdf_path, mimetype='application/pdf', as_attachment=True, download_name='labels.pdf')
    except Exception as e: return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)