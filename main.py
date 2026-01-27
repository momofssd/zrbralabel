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
import time
import threading


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
    
    # Convert to grayscale
    gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
    
    barcode_data = []
    
    # Try multiple preprocessing techniques for better 2D barcode detection
    images_to_scan = [
        gray,  # Original grayscale
        cv2.GaussianBlur(gray, (3, 3), 0),  # Slight blur
        cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),  # Adaptive threshold
        cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],  # Otsu's threshold
    ]
    
    # Convert to PIL for DataMatrix scanning
    pil_image = Image.fromarray(cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB))
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Scan with pyzbar on multiple preprocessed images
        pyzbar_futures = [executor.submit(process_standard_barcodes, img) for img in images_to_scan]
        
        # Scan with pylibdmtx on original PIL image
        matrix_future = executor.submit(process_datamatrix, pil_image)
        
        try:
            # Collect all results
            seen_data = set()
            for future in pyzbar_futures:
                try:
                    results = future.result(timeout=2)
                    for barcode in results:
                        # Avoid duplicates
                        key = (barcode['data'], barcode['type'])
                        if key not in seen_data:
                            seen_data.add(key)
                            barcode_data.append(barcode)
                except TimeoutError:
                    pass
            
            # Add DataMatrix results
            try:
                dm_results = matrix_future.result(timeout=3)
                for barcode in dm_results:
                    key = (barcode['data'], barcode['type'])
                    if key not in seen_data:
                        seen_data.add(key)
                        barcode_data.append(barcode)
            except TimeoutError:
                pass
                
        except Exception as e:
            print(f"Error during barcode scanning: {e}")
    
    return barcode_data

def process_standard_barcodes(gray):
    try:
        # pyzbar can detect QR codes and other 1D/2D barcodes
        barcodes = pyzbar.decode(gray, symbols=[
            pyzbar.ZBarSymbol.QRCODE,
            pyzbar.ZBarSymbol.CODE128,
            pyzbar.ZBarSymbol.CODE39,
            pyzbar.ZBarSymbol.EAN13,
            pyzbar.ZBarSymbol.EAN8,
            pyzbar.ZBarSymbol.UPCA,
            pyzbar.ZBarSymbol.UPCE,
            pyzbar.ZBarSymbol.I25,
            pyzbar.ZBarSymbol.DATABAR,
            pyzbar.ZBarSymbol.DATABAR_EXP,
        ])
        return [{
            'data': barcode.data.decode('utf-8'),
            'type': barcode.type,
            'location': {'x': barcode.rect[0], 'y': barcode.rect[1], 'width': barcode.rect[2], 'height': barcode.rect[3]}
        } for barcode in barcodes]
    except Exception as e:
        print(f"Error in process_standard_barcodes: {e}")
        return []

def process_datamatrix(pil_image):
    try:
        # Increase timeout and try with different parameters
        dmtx_results = pylibdmtx.decode(pil_image, timeout=2000, max_count=10)
        results = []
        for code in dmtx_results:
            try:
                results.append({
                    'data': code.data.decode('utf-8'),
                    'type': 'DataMatrix',
                    'location': {'x': code.rect.left, 'y': code.rect.top, 'width': code.rect.width, 'height': code.rect.height}
                })
            except Exception as e:
                print(f"Error decoding DataMatrix result: {e}")
        return results
    except Exception as e:
        print(f"Error in process_datamatrix: {e}")
        return []

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
        if not labels:
            return jsonify({'error': 'No labels provided'}), 400

        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        
        # Define 4x6 inches in points (1 inch = 72 points)
        LABEL_WIDTH = 4 * 72   # 288 points
        LABEL_HEIGHT = 6 * 72  # 432 points
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_path = tmp_file.name
            # Create the canvas with the specific 4x6 page size
            c = canvas.Canvas(pdf_path, pagesize=(LABEL_WIDTH, LABEL_HEIGHT))
            
            for label in labels:
                img_data = base64.b64decode(label['image'])
                img_io = io.BytesIO(img_data)
                img_reader = ImageReader(img_io)
                
                # Get original image dimensions
                orig_w, orig_h = img_reader.getSize()
                aspect = orig_h / float(orig_w)
                
                # Calculate scaling to fit 4x6 while maintaining aspect ratio
                # We leave a tiny margin (e.g., 4 points) to prevent clipping
                margin = 4
                printable_w = LABEL_WIDTH - (margin * 2)
                printable_h = LABEL_HEIGHT - (margin * 2)
                
                draw_w = printable_w
                draw_h = draw_w * aspect
                
                # If the height exceeds the page, scale down based on height instead
                if draw_h > printable_h:
                    draw_h = printable_h
                    draw_w = draw_h / aspect
                
                # Center the image on the 4x6 page
                x_centered = (LABEL_WIDTH - draw_w) / 2
                y_centered = (LABEL_HEIGHT - draw_h) / 2
                
                c.drawImage(img_reader, x_centered, y_centered, width=draw_w, height=draw_h)
                c.showPage()
                
            c.save()
        
        return send_file(
            pdf_path, 
            mimetype='application/pdf', 
            as_attachment=True, 
            download_name='zebra_labels_4x6.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reset-cache', methods=['POST'])
def reset_cache():
    """Delete all files in the label_storage_cache directory"""
    try:
        import shutil
        deleted_count = 0
        
        if os.path.exists(CACHE_DIR):
            # Delete all files in the cache directory
            for filename in os.listdir(CACHE_DIR):
                file_path = os.path.join(CACHE_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
            
            return jsonify({
                'message': f'Cache cleared successfully. Deleted {deleted_count} file(s).',
                'deleted_count': deleted_count
            })
        else:
            return jsonify({'message': 'Cache directory does not exist.', 'deleted_count': 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
