
import json
import os
import subprocess
import urllib.request

from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Получаем последние изменения проекта
commits = subprocess.check_output(
    ["git", "log", "-8", "--pretty=format:%s"],
    text=True
).strip()

if not commits:
    commits = "Нет новых сведений об изменениях."

# Генерируем пост
response = client.responses.create(
    model="gpt-4.1-mini",
    instructions=(
        "Ты редактор Telegram-канала ChemAnalyzerDevLog. "
        "Пиши на русском языке, понятно и интересно. "
        "Рассказывай о разработке научного приложения "
        "ChemAnalyzer. Используй только предоставленные "
        "факты. Не придумывай функции, результаты "
        "исследований или успешные тесты. "
        "Если сведений недостаточно, так и скажи. "
        "Длина поста: 100–180 слов. "
        "Добавь заголовок и максимум 3 хештега."
    ),
    input=f"Последние коммиты ChemAnalyzer:\n{commits}"
)

post = response.output_text.strip()

if not post:
    raise RuntimeError("OpenAI не вернул текст поста")

# Отправляем черновик администратору
token = os.environ["TELEGRAM_BOT_TOKEN"]
admin_id = os.environ["TELEGRAM_ADMIN_ID"]

message = (
    "📝 ЧЕРНОВИК CHEMANALYZER\n\n"
    + post
    + "\n\n⏳ Ожидает проверки. "
      "Автоматическая публикация отключена."
)

url = f"https://api.telegram.org/bot{token}/sendMessage"

payload = json.dumps({
    "chat_id": admin_id,
    "text": message[:4000]
}).encode("utf-8")

request = urllib.request.Request(
    url,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

with urllib.request.urlopen(request, timeout=30) as result:
    print("Telegram status:", result.status)

print("Черновик отправлен на согласование")
