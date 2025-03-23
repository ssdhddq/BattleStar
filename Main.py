import sounddevice as sd
import queue
import json
from vosk import Model, KaldiRecognizer
from datetime import datetime
import os
from pydub import AudioSegment
import tempfile
import time
from processingVoice import reduce_noise
import Main2

# ==== Настройки ====
model_path = "vosk-model-small-ru"  # Меняем путь к полной модели (было "vosk-model-small-ru")
output_file = "отчёт_буровая.txt"
sample_rate = 16000

# ==== Проверка модели ====
if not os.path.exists(model_path):
    print(" Модель не найдена. Убедитесь, что распаковали vosk-model-ru.")
    exit(1)

# ==== Загрузка модели ====
print(" Загружается модель речи...")
model = Model(model_path)

# ==== Очередь для аудиопотока ====
q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(" Ошибка:", status)
    q.put(bytes(indata))

def listen_for_phrase(prompt, expect_command=False, silence_timeout=1.5):
    print(prompt)
    rec = KaldiRecognizer(model, sample_rate)
    rec.SetWords(True)
    
    last_speech_time = time.time()
    accumulated_text = []  # Теперь храним список фраз
    
    with sd.RawInputStream(samplerate=sample_rate, blocksize=16000, dtype='int16',
                         channels=1, callback=callback):
        while True:
            try:
                data = q.get(timeout=0.5)
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result["text"].strip().lower()
                    if text:
                        last_speech_time = time.time()
                        accumulated_text.append(text)  # Добавляем новую часть фразы
                
                # Проверяем время с последней речи
                if time.time() - last_speech_time > silence_timeout and accumulated_text:
                    print(f" Пауза {silence_timeout} секунд - завершаем запись")
                    # Объединяем все части фразы
                    final_text = " ".join(accumulated_text)
                    return final_text
                
            except queue.Empty:
                continue

# Добавляем функцию конвертации MP3 в WAV
def convert_mp3_to_wav(mp3_path):
    """Конвертирует MP3 в WAV с нужными параметрами"""
    try:
        # Загружаем MP3
        audio = AudioSegment.from_mp3(mp3_path)
        
        # Конвертируем в нужный формат
        audio = audio.set_frame_rate(16000)  # Частота дискретизации 16кГц
        audio = audio.set_channels(1)        # Моно
        audio = audio.set_sample_width(2)    # 16 бит
        
        # Создаем временный WAV файл
        temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        audio.export(temp_wav.name, format='wav')
        return temp_wav.name
    except Exception as e:
        print(f"Ошибка конвертации: {e}")
        return None

def transcribe_audio_file(audio_path):
    """Распознавание речи из аудиофайла"""
    print(f"\n Распознавание файла: {audio_path}")
    
    # Определяем формат файла
    is_mp3 = audio_path.lower().endswith('.mp3')
    if is_mp3:
        print(" Конвертация MP3 в WAV...")
        wav_path = convert_mp3_to_wav(audio_path)
        if not wav_path:
            print(" Ошибка конвертации MP3")
            return
        audio_path = wav_path
    
    # Применяем шумоподавление
    print(" Применение шумоподавления...")
    cleaned_audio_path = "temp_cleaned.wav"
    try:
        reduce_noise(audio_path, cleaned_audio_path)
        audio_path = cleaned_audio_path
    except Exception as e:
        print(f" Ошибка шумоподавления: {e}")
        # Продолжаем с оригинальным файлом если шумоподавление не удалось
    
    # Создаем распознаватель для файла
    rec = KaldiRecognizer(model, sample_rate)
    rec.SetWords(True)
    
    accumulated_text = []
    last_result_time = time.time()
    silence_timeout = 1.5  # Время паузы для объединения фраз
    
    try:
        with open(audio_path, "rb") as audio_file:
            while True:
                data = audio_file.read(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result["text"].strip().lower()
                    if text:
                        last_result_time = time.time()
                        accumulated_text.append(text)
                
                # Записываем накопленный текст только после паузы
                if time.time() - last_result_time > silence_timeout and accumulated_text:
                    now = datetime.now().strftime("%d.%m.%Y %H:%M")
                    full_text = " ".join(accumulated_text)
                    log_entry = f'{now} "{full_text}"'
                    print(log_entry)
                    
                    with open(output_file, "a", encoding="utf-8") as f:
                        f.write(log_entry + "\n")
                    Main2.main(full_text)
                    accumulated_text = []  # Очищаем накопленный текст
        
        # Записываем оставшийся текст
        if accumulated_text:
            now = datetime.now().strftime("%d.%m.%Y %H:%M")
            full_text = " ".join(accumulated_text)
            log_entry = f'{now} "{full_text}"'
            print(log_entry)
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
            
            Main2.main(full_text)
    
    finally:
        # Удаляем временные файлы
        if os.path.exists(cleaned_audio_path):
            os.unlink(cleaned_audio_path)
        if is_mp3 and os.path.exists(audio_path) and audio_path != cleaned_audio_path:
            os.unlink(audio_path)

print("\n=== Голосовой ассистент ===")
print("Команды: 'продолжить' - новая запись, 'файл' - обработка аудио, 'выйти' - завершение")

# ==== Основной цикл ====
while True:
    command = listen_for_phrase("\nОжидание команды...")

    if "выйти" in command:
        print("Работа завершена")
        break

    elif "файл" in command:
        wav_path = "запись.wav"
        mp3_path = "Recording.mp3"
        processed_wav = "Recording.wav"  # Файл после шумоподавления
        
        
        if os.path.exists(processed_wav):
            transcribe_audio_file(processed_wav)
            print("Обработанный WAV файл транскрибирован")
        elif os.path.exists(mp3_path):
            transcribe_audio_file(mp3_path)
            print("MP3 файл обработан")
        elif os.path.exists(wav_path):
            transcribe_audio_file(wav_path)
            print("WAV файл обработан")
        else:
            print(f"Файлы не найдены")

    elif "продолжить" in command:
        phrase = listen_for_phrase("Слушаю...")

        if "выйти" in phrase:
            print("Работа завершена")
            break
        elif "продолжить" in phrase:
            continue

        # Сохраняем операцию
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        log_entry = f'{now} "{phrase}"'
        print(log_entry)

        with open(output_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
        
        Main2.main(phrase)
        
    else:
        print("Неизвестная команда")
