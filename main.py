import telebot
import google.generativeai as genai

# Вставь сюда свой токен от BotFather
TELEGRAM_TOKEN = 'ТВОЙ_TELEGRAM_TOKEN'
# Твой ключ Gemini (тот, что начинался на AIza...)
GEMINI_API_KEY = 'AIzaSyDgJsOnzIZP1GDXGIx2SCAWzyq3knUYv3Y'

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# Настраиваем агента. Системный промпт заставляет его быть умнее и проверять ошибки.
system_instruction = """
Ты — продвинутый AI-агент для vibe coding и full-stack разработки.
Твоя задача — писать безупречный код, проверять его и исправлять баги до того, как показать пользователю.

АЛГОРИТМ ТВОЕЙ РАБОТЫ (выполняй в уме):
1. Проанализируй задачу.
2. Напиши черновик решения.
3. САМОПРОВЕРКА: Найди потенциальные уязвимости, синтаксические ошибки или неоптимальную логику в черновике.
4. ИСПРАВЛЕНИЕ: Перепиши код с учетом найденных ошибок.

ПОЛЬЗОВАТЕЛЮ ВЫДАВАЙ ТОЛЬКО:
- Краткое объяснение логики.
- Финальный, исправленный и полностью рабочий код.
- Инструкцию, как это запустить.
"""

# Используем модель Pro для сложных задач кодинга и передаем системную инструкцию
model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    system_instruction=system_instruction,
    generation_config={"temperature": 0.4} # 0.4 дает баланс между креативностью и точностью
)

# Простая память для хранения контекста диалогов разных пользователей
chat_sessions = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я твой AI-агент для vibe coding. Накидывай задачи, а я напишу, проверю и выдам готовый код. Что кодим сегодня?")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_text = message.text

    # Показываем статус "печатает", пока Gemini думает
    bot.send_chat_action(chat_id, 'typing')

    try:
        # Если это новое сообщение от пользователя, создаем для него сессию с историей
        if chat_id not in chat_sessions:
            chat_sessions[chat_id] = model.start_chat(history=[])

        session = chat_sessions[chat_id]
        
        # Отправляем запрос в Gemini
        response = session.send_message(user_text)
        res_text = response.text

        # Telegram имеет лимит в 4096 символов на сообщение. 
        # Если ИИ написал много кода, разбиваем сообщение на части.
        for i in range(0, len(res_text), 4000):
            # Используем Markdown для красивой подсветки синтаксиса
            bot.send_message(chat_id, res_text[i:i+4000], parse_mode='Markdown')

    except Exception as e:
        bot.reply_to(message, f"⚠️ Произошла ошибка: {e}\nПопробуй перефразировать запрос или подождать.")

if __name__ == '__main__':
    print("AI Агент запущен и готов к работе...")
    # infinity_polling защищает бота от падений при кратковременных обрывах связи
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
