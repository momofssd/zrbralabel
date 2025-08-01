import requests
from flask import Flask, request, send_file, jsonify, render_template
from flask_cors import CORS
import io

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

if __name__ == '__main__':
    app.run(port=3000, debug=True)
