import logging
import openpyxl
import requests
from typing import List, Optional

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
EXCEL_FILENAME = 'data.xlsx'
API_URL = "https://api.intelligence.io.solutions/api/v1/chat/completions"
API_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Bearer io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6IjRhOTkxM2I4LTVlNGQtNDkwYy04ODNiLTRiZjhiODRkMTU2NyIsImV4cCI6NDg5NjI0OTQ1N30.LxRxEszeLs1L5mLuHhvBGwhltoViMqo9SQgo3K_nrHyAtMNLJRUsgSCoRqE2LwZb6uchivSb4qa_VwjJJJpKnA"
}
EXCEL_COLUMNS = ['Время начала', 'Время окончания', 'Забой', 'Этап',
                 'Комментарий']
VALID_STAGES = {
    'кнбк', 'спо', 'бурение', 'промывка', 'проработка',
    'вспомогательные операции', 'крепление', 'оборудование устья скважины',
    'гис', 'обслуживание бу', 'управление скважиной', 'прочие работы',
    'освоение', 'збс', 'испытание', 'нпв'
}


def write_to_excel(
        start_time: str,
        end_time: str,
        footage: str,
        stage: str,
        comment: Optional[str] = None
) -> None:
    """Записывает данные в Excel-файл."""
    try:
        wb = openpyxl.load_workbook(EXCEL_FILENAME)
        sheet = wb.active
    except FileNotFoundError:
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = "Данные"
        sheet.append(EXCEL_COLUMNS)

    try:
        sheet.append([start_time, end_time, footage, stage, comment])
        wb.save(EXCEL_FILENAME)
    except PermissionError as e:
        logger.error("Файл Excel занят, закройте его перед записью: %s", e)
        raise
    except Exception as e:
        logger.error("Ошибка записи в Excel: %s", e)
        raise


def extract_data(text: str) -> List[str]:
    """Извлекает структурированные данные из текста."""
    result = []
    zaboy_value = None

    for line in text.split('\n'):
        if not line.strip():
            continue

        if line.startswith('Время начала: '):
            result.append(line.split(': ')[1])
        elif line.startswith('Время окончания: '):
            result.append(line.split(': ')[1])
        elif line.startswith('Забой: '):
            zaboy_value = line.split(': ')[1]
        elif line.startswith('Этап: '):
            stage = line.split(': ')[1].strip().lower()
            result.append(stage if stage in VALID_STAGES else 'нпв')
            if stage not in VALID_STAGES:
                result.append(stage)

    if zaboy_value:
        result.insert(2, zaboy_value)

    return result


def message_to_json(message: str) -> Optional[str]:
    """Отправляет запрос к API и возвращает обработанный текст."""
    system_template = """Из текста извлечь следующую информацию:
    1. Время начала работы(в формате HH:MM).
    2. Время окончания работы(в формате HH:MM).
    3. Забой(всегда какое-то число, БЕЗ ПРИСТАВОК).
    4. Этап работы (например, бурение, НПВ, ремонт).
    5. Комментарий (если имеется).
    
    Текст: "{user_text}"
    
    Результат:
    Время начала: {start_time}
    Время окончания: {end_time}
    Забой: {footage}
    Этап: {stage}
    Комментарий: {comment}"""

    try:
        response = requests.post(
            API_URL,
            headers=API_HEADERS,
            json={
                "model": "mistralai/Ministral-8B-Instruct-2410",
                "messages": [
                    {
                        "role": "system",
                        "content": system_template
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

    except requests.exceptions.RequestException as e:
        logger.error("Ошибка API запроса: %s", e)
        return None


def process_message(message: str) -> None:
    """Обрабатывает одно сообщение и сохраняет в Excel."""
    try:
        processed_text = message_to_json(message)
        try:
            if processed_text:
                data = extract_data(processed_text)
                write_to_excel(*data)
        except Exception as e:
            logger.error("Ошибка количества аргументов: %s", e)
            logger.error(processed_text)
    except Exception as e:
        logger.error("Ошибка обработки сообщения: %s", e)


def main(test_messages) -> None:
    """Основная функция выполнения."""

    try:
        process_message(test_messages)
    except Exception as e:
        logger.error("Ошибка в основном цикле: %s", e)


if __name__ == '__main__':
    main()
