import requests
from flask import Flask, request, send_file, jsonify, render_template
from flask_cors import CORS
import io
from PIL import Image
import cv2
import numpy as np
from pyzbar import pyzbar
from pylibdmtx import pylibdmtx  # NEW: for Data Matrix

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

@app.route('/read-barcodes', methods=['POST'])
def read_barcodes():
    try:
        zpl = request.json.get('zpl')
        if not zpl:
            return jsonify({'error': 'ZPL code is required'}), 400

        headers = {'Accept': 'image/png'}
        response = requests.post(
            'http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/',
            data=zpl,
            headers=headers
        )

        if response.status_code != 200:
            return jsonify({'error': 'Error generating label for barcode reading'}), response.status_code

        image_data = response.content
        image = Image.open(io.BytesIO(image_data)).convert("RGB")

        # --- Decode with pyzbar (1D and QR) ---
        opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
        barcodes = pyzbar.decode(gray)

        barcode_data = []
        for barcode in barcodes:
            (x, y, w, h) = barcode.rect
            barcode_info = {
                'data': barcode.data.decode('utf-8'),
                'type': barcode.type,
                'location': {
                    'x': x,
                    'y': y,
                    'width': w,
                    'height': h
                }
            }
            barcode_data.append(barcode_info)

        # --- Decode Data Matrix with pylibdmtx ---
        dmtx_results = pylibdmtx.decode(image)
        for code in dmtx_results:
            x, y, w, h = code.rect
            barcode_info = {
                'data': code.data.decode('utf-8'),
                'type': 'DataMatrix',
                'location': {
                    'x': x,
                    'y': y,
                    'width': w,
                    'height': h
                }
            }
            barcode_data.append(barcode_info)

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

if __name__ == '__main__':
    app.run(port=3000, debug=True)
