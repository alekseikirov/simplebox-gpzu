import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import fitz
import json
import re

app = Flask(__name__)
CORS(app)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

@app.route('/api/analyze-gpzu', methods=['POST'])
def analyze_gpzu():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    file = request.files['file']
    pdf_bytes = file.read()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": "Из этого текста ГПЗУ извлеки данные и верни ТОЛЬКО JSON без пояснений: {\"parcels\": [{\"cadastral_number\": \"кадастровый номер\", \"area_sqm\": 0, \"coordinates\": [{\"x\": 0, \"y\": 0}], \"setback\": 0}]}\n\nТекст ГПЗУ:\n" + text[:8000]
            }
        ]
    )

    result_text = message.content[0].text
    result_text = re.sub(r'```json\s*', '', result_text)
    result_text = re.sub(r'```\s*', '', result_text)
    extracted = json.loads(result_text.strip())

    return jsonify({
        "extracted_json": json.dumps(extracted),
        "file_id": "test-file-id"
    })

if __name__ == '__main__':
   import os
port = int(os.environ.get('PORT', 5000))
app.run(debug=False, host='0.0.0.0', port=port)