import os
import json
import requests
from datetime import datetime

FUNC_RESPONSE = {
    'statusCode': 200,
    'body': ''
}

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
API_KEY = os.environ.get("API_KEY")
AUTH_HEADER = f"Api-Key {API_KEY}"
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
SPEECH_API_KEY = os.environ.get("SPEECH_API_KEY")

def handle_start_help_command(message):
    text = "Я сообщу вам о погоде в том месте, которое сообщите мне.\n" \
           "Я могу ответить на:\n" \
           "- Текстовое сообщение с названием населенного пункта.\n" \
           "- Голосовое сообщение с названием населенного пункта.\n" \
           "- Сообщение с точкой на карте."
    send_message(text, message)

def handle_other_message(message):
    text = "Я не могу ответить на такой тип сообщения.\n" \
           "Но могу ответить на:\n" \
           "- Текстовое сообщение с названием населенного пункта.\n" \
           "- Голосовое сообщение с названием населенного пункта.\n" \
           "- Сообщение с точкой на карте."
    send_message(text, message)

def send_message(text, message):
    message_id = message['message_id']
    chat_id = message['chat']['id']
    reply_message = {'chat_id': chat_id,
                     'text': text,
                     'reply_to_message_id': message_id}
    requests.post(url=f'{TELEGRAM_API_URL}/sendMessage', json=reply_message)

def send_audio(audio, message):
    message_id = message['message_id']
    chat_id = message['chat']['id']
    files = {'audio': ('audio.ogg', audio)}
    reply_audio = {'chat_id': chat_id,
                   'reply_to_message_id': message_id}
    requests.post(url=f'{TELEGRAM_API_URL}/sendVoice', data=reply_audio, files=files)

def get_weather(city):
    if city.startswith('/'):
        return ""

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    response = requests.get(url)
    if response.ok:
        weather_data = response.json()
        temperature = round(weather_data['main']['temp'])
        feels_like = round(weather_data['main']['feels_like'])
        pressure = round(weather_data['main']['pressure'])
        humidity = round(weather_data['main']['humidity'])
        visibility = round(weather_data['visibility'])
        wind_speed = round(weather_data['wind']['speed'])
        wind_direction = weather_data['wind']['deg']
        sunrise = datetime.fromtimestamp(weather_data['sys']['sunrise']).strftime('%H:%M')
        sunset = datetime.fromtimestamp(weather_data['sys']['sunset']).strftime('%H:%M')
        description = weather_data['weather'][0]['description']
        wind_direction_text = get_wind_direction_text(wind_direction)
        return f"Описание погоды: {description}\nТемпература: {temperature}°C, ощущается как: {feels_like}°C\n" \
               f"Атмосферное давление: {pressure} мм рт. ст.\nВлажность: {humidity}%\n" \
               f"Видимость: {visibility} метров\nВетер: {wind_speed} м/с {wind_direction_text}\n" \
               f"Восход солнца: {sunrise} МСК. Закат: {sunset} МСК."
    else:
        return f"Я не нашел населенный пункт {city}"

def get_wind_direction_text(degrees):
    directions = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    index = round(degrees / 45) % 8
    return directions[index]

def recognize_speech(audio):
    url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    headers = {'Authorization': AUTH_HEADER}
    response = requests.post(url, headers=headers, data=audio)
    if response.ok:
        result = response.json()
        if 'result' in result:
            recognized_text = result['result']
            return recognized_text
    return None

def generate_speech(text):
    url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
    headers = {
        'Authorization': AUTH_HEADER,
        'Content-Type': 'application/json'
    }
    data = {
        'text': text,
        'lang': 'ru-RU',
        'folderId': SPEECH_API_KEY
    }
    response = requests.post(url, headers=headers, json=data)
    if response.ok:
        audio = response.content
        return audio
    return None

def get_file(file_id):
    resp = requests.post(url=f'{TELEGRAM_API_URL}/getFile', json={'file_id': file_id})
    return resp.json()['result']

def get_location(latitude, longitude):
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={latitude}&lon={longitude}"
    response = requests.get(url)
    if response.ok:
        location_data = response.json()
        if 'address' in location_data:
            city = location_data['address'].get('city')
            if city:
                return city
    return None

def handler(event, context):
    if TELEGRAM_BOT_TOKEN is None:
        return FUNC_RESPONSE

    update = json.loads(event['body'])

    if 'message' not in update:
        return FUNC_RESPONSE

    message_in = update['message']

    if 'text' in message_in:
        command = message_in['text']
        if command == '/start' or command == '/help':
            handle_start_help_command(message_in)
        elif command.startswith('/'):
            return FUNC_RESPONSE
        else:
            city = message_in['text']
            weather_data = get_weather(city)
            if weather_data:
                send_message(weather_data, message_in)
            # else:
            #     send_message("Не удалось получить информацию о погоде для города", message_in)
    elif 'voice' in message_in:
        voice = message_in['voice']
        duration = voice['duration']

        if duration > 30:
            send_message("Запись должна быть не длиннее 30 секунд", message_in)
            return FUNC_RESPONSE

        file_id = voice['file_id']
        tg_file = get_file(file_id)
        tg_file_path = tg_file['file_path']

        file_resp = requests.get(url=f'https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{tg_file_path}')
        audio = file_resp.content

        recognized_text = recognize_speech(audio)

        if recognized_text:
            city = recognized_text.strip()
            weather_data = get_weather(city)

            if weather_data:
                send_message(weather_data, message_in)
                audio_response = generate_speech(weather_data)
                if audio_response:
                    send_audio(audio_response, message_in)
        #         else:
        #             send_message('Ошибка при генерации аудио', message_in)
        #     else:
        #         send_message('Не удалось получить информацию о погоде для города', message_in)
        # else:
        #     send_message('Не удалось распознать город из голосового сообщения', message_in)
    elif 'location' in message_in:
        location = message_in['location']
        latitude = location['latitude']
        longitude = location['longitude']
        city = get_location(latitude, longitude)
        if city:
            weather_data = get_weather(city)
            if weather_data:
                send_message(weather_data, message_in)
            # else:
            #     send_message("Не удалось получить информацию о погоде для города", message_in)
        else:
            send_message("Я не знаю какая погода в этом месте.", message_in)

    else:
        handle_other_message(message_in)

    return FUNC_RESPONSE