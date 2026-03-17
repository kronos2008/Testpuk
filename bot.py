import logging
import re
import dns.resolver
from datetime import datetime
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = '8638542957:AAGTFsBkGvEpaPWLWyamrGdrgbG9OYLMFds'

class ReportLogger:
    """Класс для логирования отчетов в txt файл"""
    
    def __init__(self, filename="email_reports.txt"):
        self.filename = filename
        if not os.path.exists(filename):
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=== ОТЧЕТЫ ПРОВЕРКИ EMAIL ===\n")
                f.write("="*60 + "\n\n")
    
    def log_report(self, username, user_id, first_name, last_name, email, is_valid, details=None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_name = f"{first_name} {last_name}" if last_name else first_name
        
        if is_valid:
            status = "прошел проверку на валид"
            status_symbol = "✅"
        else:
            status = "НЕ ПРОШЕЛ проверку на валид, почта не валид"
            status_symbol = "❌"
        
        report_line = (f"[{timestamp}] {status_symbol} (юз: @{username} | имя: {full_name}) "
                      f"(айди: {user_id}) проверил почту - {email} - {status}")
        
        if details:
            report_line += f" | Детали: {details}"
        
        try:
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write(report_line + "\n")
                f.flush()
            return True
        except Exception as e:
            logger.error(f"Ошибка записи в файл отчета: {e}")
            return False
    
    def get_stats(self):
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
        except:
            return {'total': 0, 'valid': 0, 'invalid': 0, 'unique_users': 0}

report_logger = ReportLogger()

class EmailValidator:
    def __init__(self):
        self.email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        try:
            self.dns_resolver = dns.resolver.Resolver(configure=False)
            self.dns_resolver.nameservers = ['8.8.8.8', '8.8.4.4', '1.1.1.1']
            self.dns_resolver.timeout = 5
            self.dns_resolver.lifetime = 5
        except Exception as e:
            logger.error(f"Ошибка создания DNS резолвера: {e}")
            self.dns_resolver = None
    
    def validate_format(self, email):
        try:
            if not self.email_pattern.match(email):
                return False, "❌ Неверный формат email"
            return True, "✅ Формат корректный"
        except Exception as e:
            return False, f"❌ Ошибка: {str(e)}"
    
    def validate_domain(self, email):
        if not self.dns_resolver:
            return False, "❌ DNS не работает"
        
        try:
            domain = email.split('@')[1]
            record_types = ['MX', 'A', 'AAAA']
            
            for record_type in record_types:
                try:
                    records = self.dns_resolver.resolve(domain, record_type)
                    if records:
                        return True, f"✅ Домен существует"
                except:
                    continue
            
            return False, "❌ Домен не существует"
        except:
            return False, "❌ Ошибка проверки домена"
    
    def validate_email(self, email):
        format_valid, format_msg = self.validate_format(email)
        
        if not format_valid:
            return {
                'valid': False,
                'checks': [{'name': 'Формат', 'status': False, 'message': format_msg}],
                'details': format_msg
            }
        
        domain_valid, domain_msg = self.validate_domain(email)
        
        checks = [
            {'name': 'Формат', 'status': format_valid, 'message': format_msg},
            {'name': 'Домен', 'status': domain_valid, 'message': domain_msg}
        ]
        
        return {
            'valid': format_valid and domain_valid,
            'checks': checks,
            'details': f"Формат: {format_msg} | Домен: {domain_msg}"
        }

validator = EmailValidator()

# Клавиатура
def get_keyboard():
    keyboard = [
        [KeyboardButton("🔍 Проверить email")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 *Добро пожаловать в Email Validator Bot!*\n\n"
        "Я помогу вам проверить валидность email адресов.\n\n"
        "📧 *Команды:*\n"
        "• Отправьте email для проверки\n"
        "• /stats - статистика\n"
        "• /help - помощь"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=get_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📧 *Как пользоваться:*\n\n"
        "1️⃣ Отправьте email для проверки\n"
        "2️⃣ Бот проверит формат и существование домена\n"
        "3️⃣ Результат сохраняется в отчет\n\n"
        "✅ *Бот работает!*"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = report_logger.get_stats()
    stats_text = (
        "📊 *Статистика проверок*\n\n"
        f"📧 Всего: {stats['total']}\n"
        f"✅ Валидных: {stats['valid']}\n"
        f"❌ Невалидных: {stats['invalid']}\n"
        f"👥 Пользователей: {stats['unique_users']}"
    )
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    
    # Обработка кнопок
    if text == "🔍 Проверить email":
        await update.message.reply_text("📧 Отправьте email для проверки:")
        return
    elif text == "📊 Статистика":
        await stats(update, context)
        return
    elif text == "❓ Помощь":
        await help_command(update, context)
        return
    
    # Проверка email
    email = text.strip()
    
    # Простая проверка на email
    if '@' not in email or '.' not in email.split('@')[1]:
        await update.message.reply_text("❌ Это не похоже на email. Отправьте корректный email.")
        return
    
    # Отправляем статус
    status_msg = await update.message.reply_text("🔄 Проверяю email...")
    
    try:
        # Проверяем email
        results = validator.validate_email(email)
        
        # Логируем
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
        response = f"📧 *Результат:*\n`{email}`\n\n"
        
        for check in results['checks']:
            if check['status']:
                response += f"✅ *{check['name']}:* {check['message']}\n"
            else:
                response += f"❌ *{check['name']}:* {check['message']}\n"
        
        response += f"\n📊 *Статус:* {'✅ Валидный' if results['valid'] else '❌ Невалидный'}"
        
        # Удаляем статус и отправляем результат
        await status_msg.delete()
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status_msg.delete()
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

def main():
    print("="*50)
    print("Email Validator Bot запущен!")
    print("="*50)
    print(f"Файл отчетов: {report_logger.filename}")
    print("="*50)
    print("🔄 Бот ожидает сообщения...")
    print("="*50)
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    # Запускаем бота
    app.run_polling(poll_interval=1.0)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")