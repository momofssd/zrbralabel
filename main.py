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

# Cache for storing generated labels
label_cache = {}
cache_lock = threading.Lock()

def cache_label(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        zpl = request.json.get('zpl')
        with cache_lock:
            if zpl in label_cache:
                return label_cache[zpl]
            result = func(*args, **kwargs)
            label_cache[zpl] = result
            # Keep cache size reasonable
            if len(label_cache) > 100:
                label_cache.pop(next(iter(label_cache)))
            return result
    return wrapper

app = Flask(__name__, static_folder='public', static_url_path='', template_folder='public')
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-label', methods=['POST'])
def generate_label():
    zpl = request.json.get('zpl')
    if not zpl:
        return jsonify({'error': 'ZPL code is required'}), 400

    headers = {'Accept': 'image/png'}
    response = requests.post(
        'http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/',
        data=zpl,
        headers=headers
    )

    if response.status_code == 200:
        return send_file(io.BytesIO(response.content), mimetype='image/png')
    else:
        return jsonify({'error': 'Error generating label'}), response.status_code

def process_image_for_barcodes(image_data):
    """Process image data and return barcodes found"""
    # Convert image bytes to OpenCV format
    if isinstance(image_data, (bytes, bytearray)):
        nparr = np.frombuffer(image_data, np.uint8)
        opencv_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        opencv_image = image_data

    if opencv_image is None:
        raise ValueError('Invalid image data')
    
    # Enhanced image preprocessing
    gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    barcode_data = []
    
    # Process barcodes in parallel with timeout
    with ThreadPoolExecutor(max_workers=2) as executor:
        standard_future = executor.submit(process_standard_barcodes, gray)
        pil_image = Image.fromarray(cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB))
        matrix_future = executor.submit(process_datamatrix, pil_image)
        
        try:
            standard_results = standard_future.result(timeout=2)
            matrix_results = matrix_future.result(timeout=2)
            
            barcode_data.extend(standard_results)
            barcode_data.extend(matrix_results)
        except TimeoutError:
            if standard_future.done():
                barcode_data.extend(standard_future.result())
            if matrix_future.done():
                barcode_data.extend(matrix_future.result())
    
    return barcode_data

def process_standard_barcodes(gray):
    try:
        barcodes = pyzbar.decode(gray)
        return [{
            'data': barcode.data.decode('utf-8'),
            'type': barcode.type,
            'location': {
                'x': barcode.rect[0],
                'y': barcode.rect[1],
                'width': barcode.rect[2],
                'height': barcode.rect[3]
            }
        } for barcode in barcodes]
    except Exception:
        return []

def process_datamatrix(pil_image):
    try:
        dmtx_results = pylibdmtx.decode(pil_image, timeout=1000)  # 1 second timeout
        return [{
            'data': code.data.decode('utf-8'),
            'type': 'DataMatrix',
            'location': {
                'x': code.rect[0],
                'y': code.rect[1],
                'width': code.rect[2],
                'height': code.rect[3]
            }
        } for code in dmtx_results]
    except Exception:
        return []

@app.route('/read-barcodes', methods=['POST'])
@cache_label
def read_barcodes():
    try:
        zpl = request.json.get('zpl')
        if not zpl:
            return jsonify({'error': 'ZPL code is required'}), 400

        headers = {'Accept': 'image/png'}
        response = requests.post(
            'http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/',
            data=zpl,
            headers=headers,
            timeout=5  # 5 second timeout for API request
        )

        if response.status_code != 200:
            return jsonify({'error': 'Error generating label for barcode reading'}), response.status_code

        # Convert image bytes directly to OpenCV format
        nparr = np.frombuffer(response.content, np.uint8)
        opencv_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if opencv_image is None:
            return jsonify({'error': 'Invalid image data'}), 400
        
        # Enhanced image preprocessing
        gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)  # Reduced blur kernel size
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        barcode_data = []
        
        # Process barcodes in parallel with timeout
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Start both tasks
            standard_future = executor.submit(process_standard_barcodes, gray)
            pil_image = Image.fromarray(cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB))
            matrix_future = executor.submit(process_datamatrix, pil_image)
            
            try:
                # Get results with timeout
                standard_results = standard_future.result(timeout=2)  # 2 second timeout
                matrix_results = matrix_future.result(timeout=2)  # 2 second timeout
                
                barcode_data.extend(standard_results)
                barcode_data.extend(matrix_results)
            except TimeoutError:
                # If timeout occurs, use whatever results we have
                if standard_future.done():
                    barcode_data.extend(standard_future.result())
                if matrix_future.done():
                    barcode_data.extend(matrix_future.result())

        if not barcode_data:
            return jsonify({
                'message': 'No barcodes found in the label',
                'barcodes': []
            })

        return jsonify({
            'message': f'Found {len(barcode_data)} barcode(s)',
            'barcodes': barcode_data
        })

    except Exception as e:
        return jsonify({'error': f'Error reading barcodes: {str(e)}'}), 500

@app.route('/upload-file', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Get file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        all_barcodes = []
        
        # Read file content once
        file_content = file.read()
        image_data = None

        if file_ext == '.pdf':
            # Create temporary directory for PDF processing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save PDF temporarily
                pdf_path = os.path.join(temp_dir, 'temp.pdf')
                with open(pdf_path, 'wb') as f:
                    f.write(file_content)
                
                # Convert PDF to images
                images = pdf2image.convert_from_path(pdf_path)
                
                # Use first page for display
                first_page = images[0]
                img_byte_arr = io.BytesIO()
                first_page.save(img_byte_arr, format='PNG')
                image_data = img_byte_arr.getvalue()
                
                # Process each page for barcodes
                for i, image in enumerate(images):
                    opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                    try:
                        page_barcodes = process_image_for_barcodes(opencv_image)
                        for barcode in page_barcodes:
                            barcode['page'] = i + 1
                        all_barcodes.extend(page_barcodes)
                    except Exception as e:
                        print(f"Error processing page {i+1}: {str(e)}")
                        continue
        else:  # Handle as image
            try:
                image_data = file_content
                barcodes = process_image_for_barcodes(file_content)
                all_barcodes.extend(barcodes)
            except Exception as e:
                return jsonify({'error': f'Error processing image: {str(e)}'}), 500

        # Convert image to base64 for frontend display
        image_base64 = None
        if image_data:
            image_base64 = base64.b64encode(image_data).decode('utf-8')

        return jsonify({
            'message': f'Found {len(all_barcodes)} barcode(s)',
            'barcodes': all_barcodes,
            'image': image_base64
        })

    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
