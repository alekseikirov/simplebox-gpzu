import os
import json
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import fitz  # PyMuPDF

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

PROMPT = """Из этого ГПЗУ извлеки данные и верни ТОЛЬКО JSON без пояснений.

Правила извлечения:
- address: ищи полный адрес с улицей и номером участка — обычно встречается в шапке или приложениях с техническими условиями в строке "Адрес земельного участка". Пример: "Московская обл., г.о. Химки, Елино д., Авторемонтная ул., з/у. 1Б"
- issue_date: дата выдачи ГПЗУ в формате DD-MM-YYYY-MM — ищи в шапке документа
- land_use_types_main: первые 10 пунктов из раздела "основные виды разрешенного использования земельного участка" — только названия без кодов
- land_use_types_conditional: первые 5 пунктов из раздела "условно разрешенные виды использования земельного участка" — только названия без кодов
- setback: минимальный отступ в метрах из таблицы предельных параметров, столбец "Минимальные отступы от границ земельного участка"
- max_coverage_percent: максимальный процент застройки из той же таблицы, null если не указано
- max_floors: максимальное количество этажей из той же таблицы, null если не указано
- restrictions: все ограничения из раздела "Информация об ограничениях использования земельного участка"

Формат ответа:
{"parcels": [{"cadastral_number": "номер", "area_sqm": 0, "coordinates": [{"x": 0, "y": 0}], "address": "полный адрес", "issue_date": "YYYY-MM-DD", "land_use_types_main": ["ВРИ 1"], "land_use_types_conditional": ["ВРИ 1"], "setback": 0, "max_coverage_percent": null, "max_floors": null, "restrictions": ["ограничение 1"]}]}"""


def pdf_to_images(doc, max_pages=15, dpi=150):
    """Конвертирует страницы PDF в base64 изображения."""
    images = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode()
        images.append(img_base64)
    return images


def analyze_with_text(text):
    """Анализ через текст."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": PROMPT + "\n\nТекст ГПЗУ:\n" + text
        }]
    )
    return response.content[0].text


def analyze_with_vision(images):
    """Анализ через изображения (Vision)."""
    content = []
    for img in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img
            }
        })
    content.append({
        "type": "text",
        "text": PROMPT
    })

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": content
        }]
    )
    return response.content[0].text


@app.route('/api/analyze-gpzu', methods=['POST'])
def analyze_gpzu():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    pdf_bytes = file.read()

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # Извлекаем текст
        text = ""
        for page in doc:
            text += page.get_text()

        text = text.strip()
        MIN_TEXT_LENGTH = 500

        if len(text) >= MIN_TEXT_LENGTH:
            # Текстовый PDF — используем текст
            print(f"Текстовый режим: {len(text)} символов")
            result_text = analyze_with_text(text)
        else:
            # Скан или CAD — используем Vision
            print(f"Vision режим: текста только {len(text)} символов")
            images = pdf_to_images(doc, max_pages=15, dpi=150)
            result_text = analyze_with_vision(images)

        doc.close()

        # Чистим ответ от markdown если есть
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        return jsonify({'extracted_json': result_text})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)