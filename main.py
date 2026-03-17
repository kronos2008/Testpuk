import os
import sys
import subprocess
import zipfile
import shutil
import asyncio
import time
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==================== АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ ====================
# Этот код выполнится при первом запуске бота

BOT_DIR = Path(__file__).parent
ANDROID_SDK = BOT_DIR / "android-sdk"
JAVA_CHECK = subprocess.run(["which", "java"], capture_output=True)

def setup_environment():
    """Автоматическая установка всех необходимых компонентов"""
    print("🔧 Проверка и установка окружения для сборки APK...")
    
    # Создаем нужные папки
    (BOT_DIR / "downloads").mkdir(exist_ok=True)
    (BOT_DIR / "builds").mkdir(exist_ok=True)
    
    # 1. Установка системных пакетов (если есть sudo)
    try:
        print("📦 Установка Java и системных утилит...")
        subprocess.run(["apt", "update"], check=True)
        subprocess.run(["apt", "install", "-y", "openjdk-17-jdk", "wget", "unzip"], check=True)
        print("✅ Java установлена")
    except:
        print("⚠️ Не удалось установить через apt (возможно нет sudo)")
        print("⚠️ Убедитесь что Java установлена вручную")
    
    # 2. Установка Android SDK
    if not ANDROID_SDK.exists():
        print("📱 Скачивание Android SDK...")
        try:
            # Скачиваем командные инструменты
            subprocess.run([
                "wget", 
                "https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip",
                "-O", "cmdline-tools.zip"
            ], check=True)
            
            # Распаковываем
            with zipfile.ZipFile("cmdline-tools.zip", 'r') as zip_ref:
                zip_ref.extractall("cmdline-tools-temp")
            
            # Создаем структуру папок
            ANDROID_SDK.mkdir(exist_ok=True)
            cmdline_dir = ANDROID_SDK / "cmdline-tools" / "latest"
            cmdline_dir.mkdir(parents=True, exist_ok=True)
            
            # Копируем файлы
            temp_dir = Path("cmdline-tools-temp") / "cmdline-tools"
            for item in temp_dir.iterdir():
                shutil.move(str(item), str(cmdline_dir / item.name))
            
            # Чистим временные файлы
            shutil.rmtree("cmdline-tools-temp")
            Path("cmdline-tools.zip").unlink()
            
            print("✅ Android SDK скачан")
            
            # 3. Принятие лицензий и установка платформ
            print("📝 Принятие лицензий Android...")
            sdkmanager = ANDROID_SDK / "cmdline-tools" / "latest" / "bin" / "sdkmanager"
            
            # Принимаем все лицензии
            subprocess.run(
                f"yes | {sdkmanager} --licenses",
                shell=True,
                check=True,
                capture_output=True
            )
            
            print("📲 Установка Android платформ...")
            subprocess.run(
                [str(sdkmanager), "platforms;android-33", "build-tools;33.0.0"],
                check=True,
                capture_output=True
            )
            
            print("✅ Все компоненты Android SDK установлены")
            
        except Exception as e:
            print(f"❌ Ошибка установки Android SDK: {e}")
            print("⚠️ Продолжаем, но сборка может не работать")
    else:
        print("✅ Android SDK уже установлен")
    
    # 4. Установка Python пакетов
    print("🐍 Установка Python зависимостей...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "python-telegram-bot==20.7"
        ], check=True)
        print("✅ Python зависимости установлены")
    except Exception as e:
        print(f"❌ Ошибка установки Python пакетов: {e}")
    
    print("🚀 Настройка окружения завершена!")
    return True

# Запускаем установку при импорте модуля
print("🔄 Инициализация бота...")
setup_environment()

# ==================== ОСНОВНОЙ КОД БОТА ====================

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN", "8638542957:AAGTFsBkGvEpaPWLWyamrGdrgbG9OYLMFds")  # Можно задать через переменную окружения
DOWNLOADS_DIR = BOT_DIR / "downloads"
BUILDS_DIR = BOT_DIR / "builds"

# Пути к инструментам сборки
JAVA_HOME = "/usr/lib/jvm/java-17-openjdk-amd64"  # Стандартный путь для Ubuntu/Debian
if not Path(JAVA_HOME).exists():
    # Пробуем найти Java автоматически
    java_path = subprocess.run(["which", "java"], capture_output=True, text=True)
    if java_path.returncode == 0:
        # Конвертируем /usr/bin/java в /usr/lib/jvm/...
        JAVA_HOME = str(Path(java_path.stdout.strip()).parent.parent)
    else:
        JAVA_HOME = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    # Проверяем готовность системы
    status = []
    
    if JAVA_HOME and Path(JAVA_HOME).exists():
        status.append("✅ Java: OK")
    else:
        status.append("❌ Java: не найдена")
    
    if ANDROID_SDK.exists():
        status.append("✅ Android SDK: OK")
    else:
        status.append("❌ Android SDK: не найден")
    
    status_text = "\n".join(status)
    
    await update.message.reply_text(
        f"👋 Привет! Я бот для сборки APK.\n\n"
        f"📊 Статус системы:\n{status_text}\n\n"
        f"📦 Просто отправь мне ZIP-архив с исходным кодом Android-проекта, "
        f"и я соберу его в APK.\n\n"
        f"⚠️ Сборка может занять 5-10 минут."
    )


async def handle_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик получения ZIP-файла"""
    user_id = update.effective_user.id
    
    # Проверяем готовность к сборке
    if not JAVA_HOME or not ANDROID_SDK.exists():
        await update.message.reply_text(
            "❌ Система не готова к сборке. Попробуйте перезапустить бота."
        )
        return
    
    # Проверяем, что это ZIP
    document = update.message.document
    if not document.file_name.endswith('.zip'):
        await update.message.reply_text("❌ Пожалуйста, отправьте ZIP-архив")
        return
    
    # Сообщаем о начале
    msg = await update.message.reply_text("📥 Получил архив. Начинаю обработку...")
    
    # Создаем уникальную папку для этого пользователя
    user_dir = DOWNLOADS_DIR / str(user_id) / str(int(time.time()))
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Скачиваем файл
    file_path = user_dir / document.file_name
    await document.get_file().download_to_drive(file_path)
    
    await msg.edit_text("📦 Распаковываю архив...")
    
    # Распаковываем
    extract_dir = user_dir / "source"
    extract_dir.mkdir()
    
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка распаковки: {str(e)}")
        return
    
    await msg.edit_text("🔨 Запускаю сборку. Это займет несколько минут...")
    
    # Запускаем сборку в фоне
    asyncio.create_task(build_apk(update, context, extract_dir, msg.message_id, user_dir))


async def build_apk(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                    source_dir: Path, status_msg_id: int, work_dir: Path):
    """Сборка APK (выполняется в фоне)"""
    
    # Определяем тип проекта
    is_gradle = (source_dir / "gradlew").exists() or (source_dir / "build.gradle").exists()
    is_flutter = (source_dir / "pubspec.yaml").exists()
    
    if not (is_gradle or is_flutter):
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg_id,
            text="❌ Не могу определить тип проекта. Нужен Gradle или Flutter проект."
        )
        shutil.rmtree(work_dir, ignore_errors=True)
        return
    
    try:
        # Устанавливаем переменные окружения
        env = os.environ.copy()
        if JAVA_HOME:
            env["JAVA_HOME"] = JAVA_HOME
        
        # Добавляем Android SDK в PATH
        sdk_tools = ANDROID_SDK / "cmdline-tools" / "latest" / "bin"
        sdk_platform_tools = ANDROID_SDK / "platform-tools"
        env["PATH"] = f"{sdk_tools}:{sdk_platform_tools}:{env['PATH']}"
        env["ANDROID_HOME"] = str(ANDROID_SDK)
        
        # Переходим в папку с проектом
        os.chdir(source_dir)
        
        if is_gradle:
            # Делаем gradlew исполняемым
            if (source_dir / "gradlew").exists():
                (source_dir / "gradlew").chmod(0o755)
            
            # Запускаем сборку
            result = subprocess.run(
                ["./gradlew", "assembleRelease"],
                env=env,
                capture_output=True,
                text=True,
                timeout=600  # 10 минут максимум
            )
        elif is_flutter:
            # Для Flutter нужен сам Flutter SDK
            result = subprocess.run(
                ["flutter", "build", "apk", "--release"],
                env=env,
                capture_output=True,
                text=True,
                timeout=600
            )
        
        # Ищем готовый APK
        apk_files = list(source_dir.glob("**/*.apk"))
        if apk_files and result.returncode == 0:
            apk_path = apk_files[0]
            
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg_id,
                text="✅ Сборка завершена! Отправляю файл..."
            )
            
            # Отправляем APK
            with open(apk_path, 'rb') as apk_file:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=apk_file,
                    filename=apk_path.name
                )
        else:
            # Ошибка сборки - показываем последние 1000 символов лога
            error_log = result.stderr[-1000:] if result.stderr else "Неизвестная ошибка"
            if result.stdout:
                error_log = result.stdout[-500:] + "\n\n" + error_log
            
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg_id,
                text=f"❌ Ошибка сборки:\n{error_log}"
            )
    
    except subprocess.TimeoutExpired:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg_id,
            text="❌ Сборка заняла слишком много времени (>10 минут)"
        )
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg_id,
            text=f"❌ Критическая ошибка: {str(e)}"
        )
    finally:
        # Чистим временные файлы (опционально)
        # shutil.rmtree(work_dir, ignore_errors=True)
        pass


def main():
    """Запуск бота"""
    # Проверяем токен
    if TOKEN == "ВАШ_ТОКЕН_БОТА":
        print("⚠️ ВНИМАНИЕ: Замените TOKEN на реальный токен от @BotFather")
        print("Можно задать через переменную окружения BOT_TOKEN")
        return
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_zip))
    
    # Запускаем
    print(f"🤖 Бот запущен в {BOT_DIR}")
    print(f"📁 Локальная папка: {BOT_DIR}")
    print(f"📱 Android SDK: {ANDROID_SDK}")
    app.run_polling()


if __name__ == "__main__":
    main()