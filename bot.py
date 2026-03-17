import telebot
import re
import dns.resolver
import dns.exception
from telebot import types
import logging
from datetime import datetime
import os
import time

# Токен бота (новый)
TOKEN = '8638542957:AAGTFsBkGvEpaPWLWyamrGdrgbG9OYLMFds'

# Создаем бота
bot = telebot.TeleBot(TOKEN)

# Настройка логирования для bothost
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReportLogger:
    """Класс для логирования отчетов в txt файл"""
    
    def __init__(self, filename="email_reports.txt"):
        self.filename = filename
        # Создаем файл с заголовком, если его нет
        if not os.path.exists(filename):
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=== ОТЧЕТЫ ПРОВЕРКИ EMAIL ===\n")
                f.write("="*70 + "\n\n")
    
    def log_report(self, username, user_id, first_name, last_name, email, is_valid, details=None):
        """
        Запись отчета в файл
        Формат: (юз) (айди) проверил почту на валид - почта - (прошел) не прошел проверку
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Формируем полное имя пользователя
        full_name = f"{first_name} {last_name}" if last_name else first_name
        
        # Формируем статус
        if is_valid:
            status = "прошел проверку на валид"
            status_symbol = "✅"
        else:
            status = "НЕ ПРОШЕЛ проверку на валид, почта не валид"
            status_symbol = "❌"
        
        # Основная строка отчета
        report_line = (f"[{timestamp}] {status_symbol} (юз: @{username} | имя: {full_name}) "
                      f"(айди: {user_id}) проверил почту - {email} - {status}")
        
        # Добавляем детали если есть
        if details:
            report_line += f" | Детали: {details}"
        
        # Записываем в файл
        try:
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write(report_line + "\n")
                f.flush()
            logger.info(f"Отчет сохранен: {email}")
            return True
        except Exception as e:
            logger.error(f"Ошибка записи в файл отчета: {e}")
            return False
    
    def get_stats(self):
        """Получение статистики из файла"""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            total_checks = 0
            valid_count = 0
            invalid_count = 0
            users = set()
            
            for line in lines:
                if "проверил почту" in line:
                    total_checks += 1
                    if "✅" in line:
                        valid_count += 1
                    elif "❌" in line:
                        invalid_count += 1
                    
                    # Извлекаем айди пользователя
                    import re
                    id_match = re.search(r'айди: (\d+)', line)
                    if id_match:
                        users.add(id_match.group(1))
            
            return {
                'total': total_checks,
                'valid': valid_count,
                'invalid': invalid_count,
                'unique_users': len(users)
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {'total': 0, 'valid': 0, 'invalid': 0, 'unique_users': 0}

# Создаем экземпляр для отчетов
report_logger = ReportLogger()

class EmailValidator:
    def __init__(self):
        # Регулярное выражение для email
        self.email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        # Создаем резолвер с явным указанием DNS серверов
        try:
            self.dns_resolver = dns.resolver.Resolver(configure=False)
            self.dns_resolver.nameservers = ['8.8.8.8', '8.8.4.4', '1.1.1.1']
            self.dns_resolver.timeout = 5
            self.dns_resolver.lifetime = 5
        except Exception as e:
            logger.error(f"Ошибка создания DNS резолвера: {e}")
            self.dns_resolver = None
    
    def validate_format(self, email):
        """Проверка формата email"""
        try:
            if not self.email_pattern.match(email):
                return False, "❌ Неверный формат email"
            return True, "✅ Формат корректный"
        except Exception as e:
            return False, f"❌ Ошибка проверки формата: {str(e)}"
    
    def validate_domain(self, email):
        """Проверка существования домена"""
        if not self.dns_resolver:
            return False, "❌ DNS резолвер не инициализирован"
        
        try:
            domain = email.split('@')[1]
            
            # Пробуем разные типы записей
            record_types = ['MX', 'A', 'AAAA']
            
            for record_type in record_types:
                try:
                    records = self.dns_resolver.resolve(domain, record_type)
                    if records:
                        if record_type == 'MX':
                            return True, f"✅ Домен существует (MX запись)"
                        else:
                            return True, f"✅ Домен существует (A запись)"
                except:
                    continue
            
            return False, "❌ Домена не существует (нет DNS записей)"
            
        except IndexError:
            return False, "❌ Неверный формат email (нет @)"
        except Exception as e:
            return False, f"❌ Ошибка при проверке домена: {str(e)[:50]}"
    
    def validate_email(self, email):
        """Проверка email"""
        results = {
            'email': email,
            'valid': False,
            'checks': [],
            'details': ''
        }
        
        # Проверка формата
        format_valid, format_msg = self.validate_format(email)
        results['checks'].append({'name': 'Формат', 'status': format_valid, 'message': format_msg})
        
        if format_valid:
            # Проверка домена
            domain_valid, domain_msg = self.validate_domain(email)
            results['checks'].append({'name': 'Домен', 'status': domain_valid, 'message': domain_msg})
            
            # Общий статус
            results['valid'] = format_valid and domain_valid
        
        # Собираем детали
        details_list = []
        for check in results['checks']:
            details_list.append(f"{check['name']}: {check['message']}")
        results['details'] = ' | '.join(details_list)
        
        return results

# Создаем экземпляр валидатора
validator = EmailValidator()

# Клавиатура
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🔍 Проверить email")
    btn2 = types.KeyboardButton("📊 Статистика")
    btn3 = types.KeyboardButton("📋 Последние проверки")
    btn4 = types.KeyboardButton("❓ Помощь")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start"""
    welcome_text = (
        "👋 *Добро пожаловать в Email Validator Bot!*\n\n"
        "Я помогу вам проверить валидность email адресов.\n\n"
        "📧 *Доступные команды:*\n"
        "/start - Показать это сообщение\n"
        "/help - Показать справку\n"
        "/stats - Статистика проверок\n"
        "/recent - Последние проверки\n\n"
        "Просто отправьте мне email для проверки!"
    )
    
    bot.send_message(
        message.chat.id, 
        welcome_text, 
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )
    
    # Логируем запуск
    logger.info(f"Пользователь @{message.from_user.username} запустил бота")

@bot.message_handler(commands=['help'])
def send_help(message):
    """Обработчик команды /help"""
    help_text = (
        "📧 *Как пользоваться ботом:*\n\n"
        "1️⃣ Отправьте мне один email для быстрой проверки\n"
        "2️⃣ Используйте кнопки меню для навигации\n"
        "3️⃣ /stats - статистика всех проверок\n"
        "4️⃣ /recent - последние проверки\n\n"
        "*Что проверяется:*\n"
        "• Формат email (синтаксис)\n"
        "• Существование домена (DNS записи)\n\n"
        "✅ *Бот работает на bothost!*"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Отправка статистики"""
    stats = report_logger.get_stats()
    
    stats_text = (
        "📊 *Статистика проверок*\n\n"
        f"📧 Всего проверок: {stats['total']}\n"
        f"✅ Валидных: {stats['valid']}\n"
        f"❌ Невалидных: {stats['invalid']}\n"
        f"👥 Уникальных пользователей: {stats['unique_users']}\n\n"
        f"📁 Файл отчетов: `{report_logger.filename}`"
    )
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['recent'])
def send_recent(message):
    """Отправка последних проверок"""
    try:
        with open(report_logger.filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        reports = [line.strip() for line in lines if line.strip() and not line.startswith('===')]
        recent = reports[-5:] if reports else []
        
        if not recent:
            bot.send_message(message.chat.id, "📭 Пока нет проверок")
            return
        
        recent_text = "📋 *Последние 5 проверок:*\n\n"
        for i, report in enumerate(recent, 1):
            recent_text += f"{i}. {report}\n\n"
        
        bot.send_message(message.chat.id, recent_text, parse_mode='Markdown')
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка чтения файла: {e}")

@bot.message_handler(func=lambda message: message.text == "🔍 Проверить email")
def check_email_button(message):
    msg = bot.send_message(message.chat.id, "📧 Отправьте email для проверки:")
    bot.register_next_step_handler(msg, process_email)

@bot.message_handler(func=lambda message: message.text == "📊 Статистика")
def stats_button(message):
    send_stats(message)

@bot.message_handler(func=lambda message: message.text == "📋 Последние проверки")
def recent_button(message):
    send_recent(message)

@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def help_button(message):
    send_help(message)

def process_email(message):
    """Обработка email"""
    email = message.text.strip()
    chat_id = message.chat.id
    user = message.from_user
    
    if not email:
        bot.send_message(chat_id, "❌ Email не может быть пустым!")
        return
    
    # Простая проверка на email
    if '@' not in email or '.' not in email.split('@')[1]:
        bot.send_message(chat_id, "❌ Это не похоже на email. Попробуйте еще раз.")
        return
    
    # Отправляем сообщение о начале проверки
    status_msg = bot.send_message(chat_id, "🔄 Проверяю email...")
    
    try:
        # Выполняем проверку
        results = validator.validate_email(email)
        
        # Логируем в файл
        report_logger.log_report(
            username=user.username or "нет_username",
            user_id=user.id,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            email=email,
            is_valid=results['valid'],
            details=results['details']
        )
        
        # Формируем ответ
        response = f"📧 *Результат проверки:*\n`{email}`\n\n"
        
        for check in results['checks']:
            if check['status']:
                response += f"✅ *{check['name']}:* {check['message']}\n"
            else:
                response += f"❌ *{check['name']}:* {check['message']}\n"
        
        response += f"\n📊 *Общий статус:* {'✅ Валидный' if results['valid'] else '❌ Невалидный'}"
        
        # Удаляем сообщение о статусе и отправляем результат
        bot.delete_message(chat_id, status_msg.message_id)
        bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=get_main_keyboard())
        
    except Exception as e:
        logger.error(f"Error validating email {email}: {str(e)}")
        
        # Логируем ошибку
        report_logger.log_report(
            username=user.username or "нет_username",
            user_id=user.id,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            email=email,
            is_valid=False,
            details=f"Ошибка: {str(e)[:100]}"
        )
        
        bot.delete_message(chat_id, status_msg.message_id)
        bot.send_message(chat_id, f"❌ Ошибка при проверке: {str(e)[:100]}", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Обработчик всех остальных сообщений"""
    email = message.text.strip()
    
    # Проверяем, похоже ли на email
    if '@' in email and '.' in email.split('@')[1]:
        process_email(message)
    else:
        bot.send_message(
            message.chat.id,
            "❌ Пожалуйста, отправьте корректный email или используйте кнопки меню.",
            reply_markup=get_main_keyboard()
        )

# Запуск бота
if __name__ == '__main__':
    print("="*50)
    print("Email Validator Bot для bothost")
    print("="*50)
    print(f"Токен: {TOKEN[:10]}...")
    print(f"Файл отчетов: {report_logger.filename}")
    print("="*50)
    print("Бот запущен и готов к работе!")
    print("="*50)
    
    # Бесконечный polling для bothost
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=30)
        except Exception as e:
            logger.error(f"Ошибка polling: {e}")
            time.sleep(5)
            continue
