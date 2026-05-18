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
                "content": """Из этого текста ГПЗУ извлеки данные и верни ТОЛЬКО JSON без пояснений.

                Правила извлечения:
                - address: ищи полный адрес с улицей и номером участка — обычно встречается в приложениях с техническими условиями в строке "Адрес земельного участка". Пример: "Московская обл., г.о. Химки, Елино д., Авторемонтная ул., з/у. 1Б"
                - land_use_types_main: первые 10 пунктов из раздела "основные виды разрешенного использования земельного участка" — только названия без кодов
                - land_use_types_conditional: первые 5 пунктов из раздела "условно разрешенные виды использования земельного участка" — только названия без кодов
                - setback: минимальный отступ в метрах из таблицы предельных параметров, столбец "Минимальные отступы от границ земельного участка"
                - max_coverage_percent: максимальный процент застройки из той же таблицы, null если не указано
                - max_floors: максимальное количество этажей из той же таблицы, null если не указано
                - restrictions: все ограничения из раздела "Информация об ограничениях использования земельного участка"

                Формат ответа:
                {"parcels": [{"cadastral_number": "номер", "area_sqm": 0, "coordinates": [{"x": 0, "y": 0}], "address": "полный адрес", "land_use_types_main": ["ВРИ 1"], "land_use_types_conditional": ["ВРИ 1"], "setback": 0, "max_coverage_percent": null, "max_floors": null, "restrictions": ["ограничение 1"]}]}

                Текст ГПЗУ:
                """ + text[:15000]
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