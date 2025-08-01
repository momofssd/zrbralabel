import requests
from flask import Flask, request, send_file, jsonify, render_template
from flask_cors import CORS
import io
from PIL import Image
import cv2
import numpy as np
from pyzbar import pyzbar

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
        # Get the ZPL code from request
        zpl = request.json.get('zpl')
        if not zpl:
            return jsonify({'error': 'ZPL code is required'}), 400

        # Generate the label image first
        headers = {'Accept': 'image/png'}
        response = requests.post(
            'http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/',
            data=zpl,
            headers=headers
        )

        if response.status_code != 200:
            return jsonify({'error': 'Error generating label for barcode reading'}), response.status_code

        # Convert the image to format suitable for barcode reading
        image_data = response.content
        image = Image.open(io.BytesIO(image_data))
        
        # Convert PIL image to OpenCV format
        opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale for better barcode detection
        gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
        
        # Decode barcodes
        barcodes = pyzbar.decode(gray)
        
        # Extract barcode information
        barcode_data = []
        for barcode in barcodes:
            # Extract the bounding box location of the barcode
            (x, y, w, h) = barcode.rect
            
            # Convert barcode data to string
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