import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
import pytz
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, Document, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters, ConversationHandler, ContextTypes, CallbackQueryHandler

# Словник для збереження стану користувачів
user_states = {}

# Глобальний словник для зберігання запланованих нагадувань
scheduled_reminders = {}

# Список популярних часових поясів
AVAILABLE_TIMEZONES = [
    'Europe/Warsaw',
    'Europe/Kyiv',
    'UTC',
    'America/New_York',
    'Asia/Tokyo'
]

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Налаштування окремого логера для httpx
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)

file_handler = logging.FileHandler("bot.log")
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Стани для ConversationHandler
MAIN_MENU, TIME_RECORDING, REPORT_MENU, SETTINGS_MENU, EDIT_REPORT, WAITING_FOR_DATE, EDIT_TIME, WAITING_FOR_NEW_DATE, NEW_RECORD_TIME, SAVE_NEW_RECORD, DELETE_CONFIRM, WAITING_FOR_RATE, HISTORICAL_REPORT_MENU, SELECT_MONTH, SELECT_DAY, VIEW_SELECTED_REPORT, SET_TIMEZONE, SET_LANGUAGE = range(18)

# Словники локалізації
LANGUAGES = {
    'uk': {
        'welcome_first': '👋 Привіт! Як я можу допомогти?',
        'welcome_back': '🔙 Ви повернулися в меню. Що далі?',
        'record_time': '⏱ Записати час',
        'report': '📊 Звіт',
        'settings': '⚙️ Налаштування',
        'back': '↩️ Назад',
        'record_arrival': '🟢 Прихід',
        'record_departure': '🔴 Відхід',
        'choose_action': 'Оберіть дію:',
        'daily_report': '📅 Сьогодні',
        'monthly_report': '📈 Місяць',
        'edit_report': '✏️ Редагувати',
        'choose_report_type': '📊 Оберіть тип звіту:',
        'reset_time': '🔄 Скинути',
        'set_rate': '💰 Ставка',
        'set_timezone': '🕰 Часовий пояс',
        'history': '📊 Історія',
        'set_language': '🌐 Мова',
        'settings_title': '⚙️ Налаштування:',
        'arrival_recorded': '✅ Час приходу записано:',
        'departure_recorded': '✅ Час відходу записано:',
        'already_recorded_arrival': '❌ Ви вже записали час приходу сьогодні!',
        'already_recorded_departure': '❌ Ви вже записали час відходу сьогодні!',
        'record_arrival_first': '❌ Спочатку запишіть час приходу!',
        'expected_shift_end': '🕐 Очікуваний кінець зміни:',
        'shift_end_reminder': '⚠️ Увага! Через 15 хвилин закінчується ваша зміна ({}).\nНе забудьте відмітити час відходу!',
        'no_records_today': '❌ За сьогодні немає записів.',
        'no_records_month': '❌ За цей місяць немає записів.',
        'worked_today': '⏱ Відпрацьовано сьогодні:',
        'worked_shift': '⏱ Відпрацьовано за зміну:',
        'worked_month': '⏱ Всього відпрацьовано за місяць:',
        'earnings': '💰 Заробіток:',
        'earnings_month': '💰 Заробіток за місяць:',
        'hours': 'годин',
        'choose_language': '🌐 Оберіть мову:',
        'language_set': '✅ Мову встановлено',
        'ukrainian': '🇺🇦 Українська',
        'english': '🇬🇧 English',
        'polish': '🇵🇱 Polski',
        'enter_rate': '💰 Будь ласка, введіть вашу погодинну ставку в PLN (наприклад, 25.50):',
        'rate_set': '✅ Погодинну ставку встановлено:',
        'invalid_rate': '❌ Будь ласка, введіть коректне числове значення більше 0',
        'choose_timezone': '🕰 Оберіть часовий пояс:',
        'timezone_set': '✅ Часовий пояс встановлено:',
        'invalid_timezone': '❌ Некоректний часовий пояс. Оберіть із запропонованих.',
        'reset_today': '✅ Записи за сьогодні скинуто.',
        'no_reset_records': 'ℹ️ Немає записів за сьогодні для скидання.',
        'cancel': '❌ Скасувати',
        'new_record': '📝 Новий запис',
        'delete_record': '🗑️ Видалити запис',
        'choose_date_or_action': '📅 Оберіть дату для редагування або оберіть дію:',
        'today_date': '📅 Сьогоднішня дата',
        'enter_manually': '✍️ Ввести вручну',
        'creating_new_record': '📝 Створення нового запису\nОберіть опцію (сьогодні: {}):',
        'choose_date_to_delete': '🗑️ Оберіть дату для видалення:',
        'confirm_delete': '❓ Ви впевнені, що хочете видалити запис за {}?',
        'yes': '✅ Так',
        'no': '❌ Ні',
        'record_deleted': '✅ Запис за {} видалено',
        'delete_failed': '❌ Не вдалося видалити запис. Спробуйте пізніше.',
        'delete_cancelled': '❌ Видалення скасовано',
        'edit_what': '✏️ Що ви хочете відредагувати для {}?',
        'arrival_time': '🟢 Час приходу',
        'departure_time': '🔴 Час відходу',
        'enter_new_time': '⌚ Введіть новий час у форматі ГГ:ХХ або ГГ:ХХ:СС (наприклад, 09:00 або 09:00:00):',
        'time_updated': '✅ Час успішно оновлено!',
        'time_updated_for_date': '✅ Час за {} успішно оновлено!',
        'invalid_time_format': '❌ Неправильний формат часу. Будь ласка, використовуйте формат ГГ:ХХ або ГГ:ХХ:СС',
        'enter_date_format': 'Введіть дату у форматі РРРР-ММ-ДД (наприклад, 2025-01-09):',
        'no_future_dates': '❌ Не можна створювати записи для майбутніх дат!',
        'record_exists': '❌ Запис за цю дату вже існує!',
        'enter_arrival_time': '⌚ Введіть час приходу у форматі ГГ:ХХ або ГГ:ХХ:СС (наприклад, 09:00 або 09:00:00):',
        'arrival_time_saved': '✅ Час приходу записано!\n\n⌚ Тепер введіть час відходу у форматі ГГ:ХХ або ГГ:ХХ:СС (наприклад, 18:00 або 18:00:00):',
        'departure_time_saved': '✅ Час відходу записано!',
        'invalid_date_format': '❌ Неправильний формат дати. Використовуйте формат РРРР-ММ-ДД\nСпробуйте ще раз:',
        'stats_today': '📊 Статистика за сьогодні:',
        'arrival': '🕐 Прихід:',
        'departure': '🕐 Відхід:',
        'not_recorded_yet': 'ще не записано',
        'current_shift': '📊 Поточна зміна:',
        'yesterday': 'вчора',
        'no_time_records': '📊 За сьогодні ще немає записів часу',
        'daily_report_title': '📅 Звіт за {}:',
        'night_shift': 'Нічна зміна (з вчора):',
        'monthly_report_title': '📈 Звіт за {}:',
        'choose_month': '📅 Оберіть місяць для перегляду:',
        'select_specific_day': '📅 Обрати конкретний день',
        'back_to_month_selection': '↩️ Назад до вибору місяця',
        'choose_day_detail': '📅 Оберіть день для детального перегляду:',
        'back_to_report': '↩️ Назад до звіту',
        'detailed_report_for': '📅 Детальний звіт за {}:',
        'worked': '⏱ Відпрацьовано:',
        'no_day_records': '❌ За цей день немає записів.',
        'date_processing_error': '❌ Помилка при обробці дати. Спробуйте ще раз.',
        'invalid_language': '❌ Некоректна мова. Оберіть із запропонованих.'
    },
    'en': {
        'welcome_first': '👋 Hello! How can I help you?',
        'welcome_back': '🔙 You\'re back to the menu. What\'s next?',
        'record_time': '⏱ Record time',
        'report': '📊 Report',
        'settings': '⚙️ Settings',
        'back': '↩️ Back',
        'record_arrival': '🟢 Arrival',
        'record_departure': '🔴 Departure',
        'choose_action': 'Choose an action:',
        'daily_report': '📅 Today',
        'monthly_report': '📈 Month',
        'edit_report': '✏️ Edit',
        'choose_report_type': '📊 Choose report type:',
        'reset_time': '🔄 Reset',
        'set_rate': '💰 Rate',
        'set_timezone': '🕰 Timezone',
        'history': '📊 History',
        'set_language': '🌐 Language',
        'settings_title': '⚙️ Settings:',
        'arrival_recorded': '✅ Arrival time recorded:',
        'departure_recorded': '✅ Departure time recorded:',
        'already_recorded_arrival': '❌ You have already recorded arrival time today!',
        'already_recorded_departure': '❌ You have already recorded departure time today!',
        'record_arrival_first': '❌ Please record arrival time first!',
        'expected_shift_end': '🕐 Expected shift end:',
        'shift_end_reminder': '⚠️ Attention! Your shift ends in 15 minutes ({}).\nDon\'t forget to record departure time!',
        'no_records_today': '❌ No records for today.',
        'no_records_month': '❌ No records for this month.',
        'worked_today': '⏱ Worked today:',
        'worked_shift': '⏱ Worked this shift:',
        'worked_month': '⏱ Total worked this month:',
        'earnings': '💰 Earnings:',
        'earnings_month': '💰 Monthly earnings:',
        'hours': 'hours',
        'choose_language': '🌐 Choose language:',
        'language_set': '✅ Language set',
        'ukrainian': '🇺🇦 Українська',
        'english': '🇬🇧 English',
        'polish': '🇵🇱 Polski',
        'enter_rate': '💰 Please enter your hourly rate in PLN (e.g., 25.50):',
        'rate_set': '✅ Hourly rate set:',
        'invalid_rate': '❌ Please enter a valid number greater than 0',
        'choose_timezone': '🕰 Choose timezone:',
        'timezone_set': '✅ Timezone set:',
        'invalid_timezone': '❌ Invalid timezone. Please choose from the suggested options.',
        'reset_today': '✅ Today\'s records have been reset.',
        'no_reset_records': 'ℹ️ No records for today to reset.',
        'cancel': '❌ Cancel',
        'new_record': '📝 New record',
        'delete_record': '🗑️ Delete record',
        'choose_date_or_action': '📅 Choose a date to edit or select an action:',
        'today_date': '📅 Today\'s date',
        'enter_manually': '✍️ Enter manually',
        'creating_new_record': '📝 Creating new record\nChoose option (today: {}):',
        'choose_date_to_delete': '🗑️ Choose date to delete:',
        'confirm_delete': '❓ Are you sure you want to delete the record for {}?',
        'yes': '✅ Yes',
        'no': '❌ No',
        'record_deleted': '✅ Record for {} deleted',
        'delete_failed': '❌ Failed to delete record. Please try again later.',
        'delete_cancelled': '❌ Deletion cancelled',
        'edit_what': '✏️ What do you want to edit for {}?',
        'arrival_time': '🟢 Arrival time',
        'departure_time': '🔴 Departure time',
        'enter_new_time': '⌚ Enter new time in HH:MM or HH:MM:SS format (e.g., 09:00 or 09:00:00):',
        'time_updated': '✅ Time successfully updated!',
        'time_updated_for_date': '✅ Time for {} successfully updated!',
        'invalid_time_format': '❌ Invalid time format. Please use HH:MM or HH:MM:SS format',
        'enter_date_format': 'Enter date in YYYY-MM-DD format (e.g., 2025-01-09):',
        'no_future_dates': '❌ Cannot create records for future dates!',
        'record_exists': '❌ Record for this date already exists!',
        'enter_arrival_time': '⌚ Enter arrival time in HH:MM or HH:MM:SS format (e.g., 09:00 or 09:00:00):',
        'arrival_time_saved': '✅ Arrival time saved!\n\n⌚ Now enter departure time in HH:MM or HH:MM:SS format (e.g., 18:00 or 18:00:00):',
        'departure_time_saved': '✅ Departure time saved!',
        'invalid_date_format': '❌ Invalid date format. Use YYYY-MM-DD format\nTry again:',
        'stats_today': '📊 Today\'s statistics:',
        'arrival': '🕐 Arrival:',
        'departure': '🕐 Departure:',
        'not_recorded_yet': 'not recorded yet',
        'current_shift': '📊 Current shift:',
        'yesterday': 'yesterday',
        'no_time_records': '📊 No time records for today yet',
        'daily_report_title': '📅 Report for {}:',
        'night_shift': 'Night shift (from yesterday):',
        'monthly_report_title': '📈 Report for {}:',
        'choose_month': '📅 Choose month to view:',
        'select_specific_day': '📅 Select specific day',
        'back_to_month_selection': '↩️ Back to month selection',
        'choose_day_detail': '📅 Choose day for detailed view:',
        'back_to_report': '↩️ Back to report',
        'detailed_report_for': '📅 Detailed report for {}:',
        'worked': '⏱ Worked:',
        'no_day_records': '❌ No records for this day.',
        'date_processing_error': '❌ Error processing date. Please try again.',
        'invalid_language': '❌ Invalid language. Please choose from the suggested options.'
    },
    'pl': {
        'welcome_first': '👋 Cześć! Jak mogę Ci pomóc?',
        'welcome_back': '🔙 Wróciłeś do menu. Co dalej?',
        'record_time': '⏱ Zapisz czas',
        'report': '📊 Raport',
        'settings': '⚙️ Ustawienia',
        'back': '↩️ Wstecz',
        'record_arrival': '🟢 Przyjście',
        'record_departure': '🔴 Wyjście',
        'choose_action': 'Wybierz akcję:',
        'daily_report': '📅 Dzisiaj',
        'monthly_report': '📈 Miesiąc',
        'edit_report': '✏️ Edytuj',
        'choose_report_type': '📊 Wybierz typ raportu:',
        'reset_time': '🔄 Resetuj',
        'set_rate': '💰 Stawka',
        'set_timezone': '🕰 Strefa czasowa',
        'history': '📊 Historia',
        'set_language': '🌐 Język',
        'settings_title': '⚙️ Ustawienia:',
        'arrival_recorded': '✅ Czas przyjścia zapisany:',
        'departure_recorded': '✅ Czas wyjścia zapisany:',
        'already_recorded_arrival': '❌ Już zapisałeś czas przyjścia dzisiaj!',
        'already_recorded_departure': '❌ Już zapisałeś czas wyjścia dzisiaj!',
        'record_arrival_first': '❌ Najpierw zapisz czas przyjścia!',
        'expected_shift_end': '🕐 Oczekiwany koniec zmiany:',
        'shift_end_reminder': '⚠️ Uwaga! Za 15 minut kończy się Twoja zmiana ({}).\nNie zapomnij zapisać czasu wyjścia!',
        'no_records_today': '❌ Brak zapisów na dzisiaj.',
        'no_records_month': '❌ Brak zapisów w tym miesiącu.',
        'worked_today': '⏱ Przepracowano dzisiaj:',
        'worked_shift': '⏱ Przepracowano w tej zmianie:',
        'worked_month': '⏱ Łącznie przepracowano w miesiącu:',
        'earnings': '💰 Zarobki:',
        'earnings_month': '💰 Zarobki miesięczne:',
        'hours': 'godzin',
        'choose_language': '🌐 Wybierz język:',
        'language_set': '✅ Język ustawiony',
        'ukrainian': '🇺🇦 Українська',
        'english': '🇬🇧 English',
        'polish': '🇵🇱 Polski',
        'enter_rate': '💰 Proszę podać stawkę godzinową w PLN (np. 25.50):',
        'rate_set': '✅ Stawka godzinowa ustawiona:',
        'invalid_rate': '❌ Proszę podać prawidłową liczbę większą od 0',
        'choose_timezone': '🕰 Wybierz strefę czasową:',
        'timezone_set': '✅ Strefa czasowa ustawiona:',
        'invalid_timezone': '❌ Nieprawidłowa strefa czasowa. Wybierz z proponowanych opcji.',
        'reset_today': '✅ Dzisiejsze zapisy zostały zresetowane.',
        'no_reset_records': 'ℹ️ Brak zapisów na dzisiaj do zresetowania.',
        'cancel': '❌ Anuluj',
        'new_record': '📝 Nowy zapis',
        'delete_record': '🗑️ Usuń zapis',
        'choose_date_or_action': '📅 Wybierz datę do edycji lub wybierz akcję:',
        'today_date': '📅 Dzisiejsza data',
        'enter_manually': '✍️ Wprowadź ręcznie',
        'creating_new_record': '📝 Tworzenie nowego zapisu\nWybierz opcję (dzisiaj: {}):',
        'choose_date_to_delete': '🗑️ Wybierz datę do usunięcia:',
        'confirm_delete': '❓ Czy na pewno chcesz usunąć zapis z {}?',
        'yes': '✅ Tak',
        'no': '❌ Nie',
        'record_deleted': '✅ Zapis z {} usunięty',
        'delete_failed': '❌ Nie udało się usunąć zapisu. Spróbuj ponownie później.',
        'delete_cancelled': '❌ Usuwanie anulowane',
        'edit_what': '✏️ Co chcesz edytować dla {}?',
        'arrival_time': '🟢 Czas przyjścia',
        'departure_time': '🔴 Czas wyjścia',
        'enter_new_time': '⌚ Wprowadź nowy czas w formacie GG:MM lub GG:MM:SS (np. 09:00 lub 09:00:00):',
        'time_updated': '✅ Czas pomyślnie zaktualizowany!',
        'time_updated_for_date': '✅ Czas dla {} pomyślnie zaktualizowany!',
        'invalid_time_format': '❌ Nieprawidłowy format czasu. Użyj formatu GG:MM lub GG:MM:SS',
        'enter_date_format': 'Wprowadź datę w formacie RRRR-MM-DD (np. 2025-01-09):',
        'no_future_dates': '❌ Nie można tworzyć zapisów dla przyszłych dat!',
        'record_exists': '❌ Zapis dla tej daty już istnieje!',
        'enter_arrival_time': '⌚ Wprowadź czas przyjścia w formacie GG:MM lub GG:MM:SS (np. 09:00 lub 09:00:00):',
        'arrival_time_saved': '✅ Czas przyjścia zapisany!\n\n⌚ Teraz wprowadź czas wyjścia w formacie GG:MM lub GG:MM:SS (np. 18:00 lub 18:00:00):',
        'departure_time_saved': '✅ Czas wyjścia zapisany!',
        'invalid_date_format': '❌ Nieprawidłowy format daty. Użyj formatu RRRR-MM-DD\nSpróbuj ponownie:',
        'stats_today': '📊 Statystyki na dzisiaj:',
        'arrival': '🕐 Przyjście:',
        'departure': '🕐 Wyjście:',
        'not_recorded_yet': 'jeszcze nie zapisano',
        'current_shift': '📊 Bieżąca zmiana:',
        'yesterday': 'wczoraj',
        'no_time_records': '📊 Brak zapisów czasu na dzisiaj',
        'daily_report_title': '📅 Raport za {}:',
        'night_shift': 'Zmiana nocna (od wczoraj):',
        'monthly_report_title': '📈 Raport za {}:',
        'choose_month': '📅 Wybierz miesiąc do wyświetlenia:',
        'select_specific_day': '📅 Wybierz konkretny dzień',
        'back_to_month_selection': '↩️ Powrót do wyboru miesiąca',
        'choose_day_detail': '📅 Wybierz dzień do szczegółowego wyświetlenia:',
        'back_to_report': '↩️ Powrót do raportu',
        'detailed_report_for': '📅 Szczegółowy raport za {}:',
        'worked': '⏱ Przepracowano:',
        'no_day_records': '❌ Brak zapisów dla tego dnia.',
        'date_processing_error': '❌ Błąd przetwarzania daty. Spróbuj ponownie.',
        'invalid_language': '❌ Nieprawidłowy język. Wybierz z proponowanych opcji.'
    }
}

def setup_database():
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS time_records
        (date TEXT, 
         user_id INTEGER,
         arrival_time TEXT,
         departure_time TEXT)
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS hourly_rates
        (user_id INTEGER PRIMARY KEY,
         rate DECIMAL(10,2))
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_timezones
        (user_id INTEGER PRIMARY KEY,
         timezone TEXT)
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_languages
        (user_id INTEGER PRIMARY KEY,
         language TEXT DEFAULT 'uk')
    ''')
    conn.commit()
    conn.close()

def get_user_language(user_id: int) -> str:
    """Отримати мову користувача з бази даних або повернути українську за замовчуванням"""
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('SELECT language FROM user_languages WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 'uk'

def get_text(user_id: int, key: str) -> str:
    """Отримати локалізований текст для користувача"""
    language = get_user_language(user_id)
    return LANGUAGES.get(language, LANGUAGES['uk']).get(key, LANGUAGES['uk'].get(key, key))

def get_user_timezone(user_id: int) -> str:
    """Отримати часовий пояс користувача з бази даних або повернути Europe/Warsaw за замовчуванням"""
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('SELECT timezone FROM user_timezones WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 'Europe/Warsaw'

def get_local_time(user_id: int) -> datetime:
    """Отримати поточний час у часовому поясі користувача"""
    tz = pytz.timezone(get_user_timezone(user_id))
    return datetime.now(tz)

def parse_time_input(time_str: str) -> str:
    """Парсить введений час у форматі HH:MM або HH:MM:SS і повертає у форматі HH:MM:SS"""
    time_str = time_str.strip()
    
    # Спробуємо спочатку формат HH:MM:SS
    try:
        datetime.strptime(time_str, '%H:%M:%S')
        return time_str
    except ValueError:
        pass
    
    # Спробуємо формат HH:MM
    try:
        time_obj = datetime.strptime(time_str, '%H:%M')
        return time_obj.strftime('%H:%M:00')
    except ValueError:
        raise ValueError("Неправильний формат часу")

async def get_user_info(bot, user_id: int) -> dict:
    """Отримати інформацію про користувача з Telegram API"""
    try:
        chat_member = await bot.get_chat_member(user_id, user_id)
        user = chat_member.user
        return {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_bot': user.is_bot,
            'language_code': user.language_code
        }
    except Exception as e:
        logger.error(f"Помилка отримання інформації про користувача: {e}")
        return None

async def notify_admin_new_user(bot, user_info: dict):
    """Надсилає адміністратору сповіщення про нового користувача"""
    admin_id = 667685166
    notification = (
        f"👤 Новий користувач приєднався до бота!\n\n"
        f"ID: {user_info['id']}\n"
        f"Ім'я: {user_info['first_name']}\n"
    )
    if user_info.get('last_name'):
        notification += f"Прізвище: {user_info['last_name']}\n"
    if user_info.get('username'):
        notification += f"Username: @{user_info['username']}\n"
    if user_info.get('language_code'):
        notification += f"Мова: {user_info['language_code']}\n"
    try:
        await bot.send_message(chat_id=admin_id, text=notification)
    except Exception as e:
        logger.error(f"Помилка відправки сповіщення адміністратору: {e}")

async def infouser_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /infouser"""
    if update.effective_user.id != 667685166:
        await update.message.reply_text("❌ У вас немає прав для використання цієї команди.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Використання: /infouser <ID користувача>")
        return
    try:
        user_id = int(context.args[0])
        conn = sqlite3.connect('timekeeper.db')
        c = conn.cursor()
        c.execute('''
            SELECT COUNT(*) as records,
                   MIN(date) as first_record,
                   MAX(date) as last_record
            FROM time_records
            WHERE user_id = ?
        ''', (user_id,))
        db_stats = c.fetchone()
        c.execute('SELECT timezone FROM user_timezones WHERE user_id = ?', (user_id,))
        timezone = c.fetchone()
        conn.close()
        user_info = await get_user_info(context.bot, user_id)
        if user_info:
            message = (
                f"👤 Інформація про користувача:\n\n"
                f"ID: {user_info['id']}\n"
                f"Ім'я: {user_info['first_name']}\n"
            )
            if user_info['last_name']:
                message += f"Прізвище: {user_info['last_name']}\n"
            if user_info['username']:
                message += f"Username: @{user_info['username']}\n"
            message += f"Часовий пояс: {timezone[0] if timezone else 'Europe/Warsaw'}\n"
            message += f"\n📊 Статистика використання бота:\n"
            if db_stats[0] > 0:
                message += (
                    f"Кількість записів: {db_stats[0]}\n"
                    f"Перший запис: {db_stats[1]}\n"
                    f"Останній запис: {db_stats[2]}\n"
                )
            else:
                message += "Користувач ще не робив записів в боті."
            await update.message.reply_text(message)
        else:
            await update.message.reply_text("❌ Користувача не знайдено або виникла помилка.")
    except ValueError:
        await update.message.reply_text("❌ Некоректний ID користувача.")
    except Exception as e:
        logger.error(f"Помилка в команді infouser: {e}")
        await update.message.reply_text("❌ Виникла помилка при отриманні інформації.")

async def export_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /exportusers"""
    if update.effective_user.id != 667685166:
        await update.message.reply_text("❌ У вас немає прав для використання цієї команди.")
        return
    try:
        conn = sqlite3.connect('timekeeper.db')
        c = conn.cursor()
        c.execute('''
            SELECT DISTINCT user_id,
                   COUNT(*) as records,
                   MIN(date) as first_record,
                   MAX(date) as last_record
            FROM time_records
            GROUP BY user_id
        ''')
        users_data = c.fetchall()
        c.execute('SELECT user_id, timezone FROM user_timezones')
        timezones = {row[0]: row[1] for row in c.fetchall()}
        conn.close()
        if not users_data:
            await update.message.reply_text("❌ У базі даних немає користувачів.")
            return
        report = "📊 Звіт по користувачам бота\n\n"
        for user_data in users_data:
            user_id, records_count, first_record, last_record = user_data
            user_info = await get_user_info(context.bot, user_id)
            if user_info:
                report += (
                    f"👤 Користувач ID: {user_id}\n"
                    f"Ім'я: {user_info['first_name']}\n"
                )
                if user_info['last_name']:
                    report += f"Прізвище: {user_info['last_name']}\n"
                if user_info['username']:
                    report += f"Username: @{user_info['username']}\n"
                report += f"Часовий пояс: {timezones.get(user_id, 'Europe/Warsaw')}\n"
                report += (
                    f"Кількість записів: {records_count}\n"
                    f"Перший запис: {first_record}\n"
                    f"Останній запис: {last_record}\n"
                    f"{'=' * 30}\n\n"
                )
        with open('users_report.txt', 'w', encoding='utf-8') as f:
            f.write(report)
        with open('users_report.txt', 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename='users_report.txt',
                caption='📄 Звіт по всім користувачам бота'
            )
        import os
        os.remove('users_report.txt')
    except Exception as e:
        logger.error(f"Помилка в команді export_users: {e}")
        await update.message.reply_text("❌ Виникла помилка при створенні звіту.")

async def start(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    if user_id not in user_states:
        user_states[user_id] = {'is_first_run': True}
        user_info = await get_user_info(context.bot, user_id)
        if user_info:
            await notify_admin_new_user(context.bot, user_info)
    if user_states[user_id]['is_first_run']:
        user_states[user_id]['is_first_run'] = False
        welcome_message = get_text(user_id, 'welcome_first')
    else:
        welcome_message = get_text(user_id, 'welcome_back')
    keyboard = [
        [get_text(user_id, 'record_time'), get_text(user_id, 'report')],
        [get_text(user_id, 'settings')],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    return MAIN_MENU

async def time_recording_menu(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    keyboard = [
        [get_text(user_id, 'record_arrival'), get_text(user_id, 'record_departure')],
        [get_text(user_id, 'back')]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(get_text(user_id, 'choose_action'), reply_markup=reply_markup)
    return TIME_RECORDING

async def send_shift_end_reminder(context: CallbackContext, user_id: int, shift_end: datetime):
    """Надсилає нагадування про кінець зміни"""
    try:
        reminder_text = get_text(user_id, 'shift_end_reminder').format(shift_end.strftime('%H:%M'))
        await context.bot.send_message(
            chat_id=user_id,
            text=reminder_text
        )
    except Exception as e:
        logger.error(f"Не вдалося відправити нагадування користувачу {user_id}: {e}")
        if user_id in scheduled_reminders:
            scheduled_reminders[user_id].cancel()
            del scheduled_reminders[user_id]

def calculate_shift_end(arrival_time: datetime) -> datetime:
    """Розраховує очікуваний час закінчення зміни"""
    shift_duration = timedelta(hours=8)
    return arrival_time + shift_duration

async def schedule_shift_end_reminder(context: CallbackContext, user_id: int, arrival_time: datetime):
    """Планує нагадування про кінець зміни"""
    shift_end = calculate_shift_end(arrival_time)
    reminder_time = shift_end - timedelta(minutes=15)
    now = get_local_time(user_id)
    delay = (reminder_time - now).total_seconds()
    if delay > 0:
        async def delayed_reminder():
            try:
                await asyncio.sleep(delay)
                await send_shift_end_reminder(context, user_id, shift_end)
            except Exception as e:
                logger.error(f"Не вдалося запланувати нагадування для користувача {user_id}: {e}")
        task = asyncio.create_task(delayed_reminder())
        scheduled_reminders[user_id] = task
        logger.info(f"Нагадування для користувача {user_id} заплановано на {reminder_time}")
    else:
        logger.warning(f"Час для нагадування користувачу {user_id} вже минув.")

async def record_arrival(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    current_time = get_local_time(user_id)
    current_date = current_time.date()
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('SELECT arrival_time FROM time_records WHERE date = ? AND user_id = ?',
              (current_date.isoformat(), user_id))
    existing_record = c.fetchone()
    if existing_record:
        await update.message.reply_text(get_text(user_id, 'already_recorded_arrival'))
    else:
        c.execute('''INSERT INTO time_records (date, user_id, arrival_time)
                     VALUES (?, ?, ?)''',
                  (current_date.isoformat(), user_id, current_time.strftime('%H:%M:%S')))
        conn.commit()
        shift_end = calculate_shift_end(current_time)
        await update.message.reply_text(
            f'{get_text(user_id, "arrival_recorded")} {current_time.strftime("%H:%M:%S")}\n'
            f'{get_text(user_id, "expected_shift_end")} {shift_end.strftime("%H:%M:%S")}'
        )
        await schedule_shift_end_reminder(context, user_id, current_time)
    conn.close()
    return TIME_RECORDING

async def record_departure(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    if user_id in scheduled_reminders:
        scheduled_reminders[user_id].cancel()
        del scheduled_reminders[user_id]
    current_time = get_local_time(user_id)
    current_date = current_time.date().isoformat()
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('''SELECT arrival_time, departure_time FROM time_records 
                 WHERE date = ? AND user_id = ?''', (current_date, user_id))
    record = c.fetchone()
    if not record:
        yesterday = (current_time - timedelta(days=1)).date().isoformat()
        c.execute('''SELECT arrival_time, departure_time FROM time_records 
                     WHERE date = ? AND user_id = ? AND departure_time IS NULL''',
                  (yesterday, user_id))
        yesterday_record = c.fetchone()
        if yesterday_record:
            c.execute('''UPDATE time_records 
                         SET departure_time = ? 
                         WHERE date = ? AND user_id = ?''',
                      (current_time.strftime('%H:%M:%S'), yesterday, user_id))
            conn.commit()
            await update.message.reply_text(
                f'{get_text(user_id, "departure_recorded")} {current_time.strftime("%Y-%m-%d %H:%M:%S")}'
            )
        else:
            await update.message.reply_text(get_text(user_id, 'record_arrival_first'))
    elif record[1]:
        await update.message.reply_text(get_text(user_id, 'already_recorded_departure'))
    else:
        c.execute('''UPDATE time_records 
                     SET departure_time = ? 
                     WHERE date = ? AND user_id = ?''',
                  (current_time.strftime('%H:%M:%S'), current_date, user_id))
        conn.commit()
        await update.message.reply_text(
            f'{get_text(user_id, "departure_recorded")} {current_time.strftime("%Y-%m-%d %H:%M:%S")}'
        )
    conn.close()
    return TIME_RECORDING

async def report_menu(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    keyboard = [
        [get_text(user_id, 'daily_report'), get_text(user_id, 'monthly_report')],
        [get_text(user_id, 'edit_report'), get_text(user_id, 'back')]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(get_text(user_id, 'choose_report_type'), reply_markup=reply_markup)
    return REPORT_MENU

async def daily_report(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    current_date = get_local_time(user_id).date()
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('SELECT rate FROM hourly_rates WHERE user_id = ?', (user_id,))
    rate_record = c.fetchone()
    hourly_rate = rate_record[0] if rate_record else None
    yesterday = (current_date - timedelta(days=1)).isoformat()
    current_date_str = current_date.isoformat()
    c.execute('''SELECT date, arrival_time, departure_time FROM time_records 
                 WHERE (date = ? OR date = ?) AND user_id = ?''',
              (current_date_str, yesterday, user_id))
    records = c.fetchall()
    if records:
        report = get_text(user_id, 'daily_report_title').format(current_date.strftime('%d %B %Y')) + "\n"
        total_hours = 0
        today_hours = 0
        yesterday_hours = 0
        for record in records:
            date, arrival_time, departure_time = record
            if arrival_time and departure_time:
                arrival_dt = datetime.strptime(f"{date} {arrival_time}", '%Y-%m-%d %H:%M:%S')
                departure_dt = datetime.strptime(f"{date} {departure_time}", '%Y-%m-%d %H:%M:%S')
                arrival_dt = pytz.timezone(get_user_timezone(user_id)).localize(arrival_dt)
                departure_dt = pytz.timezone(get_user_timezone(user_id)).localize(departure_dt)
                if departure_dt < arrival_dt:
                    departure_dt += timedelta(days=1)
                time_diff = departure_dt - arrival_dt
                hours = time_diff.total_seconds() / 3600
                total_hours += hours
                if date == current_date_str:
                    today_hours += hours
                    report += f"{get_text(user_id, 'arrival')} {arrival_time}\n"
                    report += f"{get_text(user_id, 'departure')} {departure_time}\n"
                    report += f"{get_text(user_id, 'worked_today')} {hours:.2f} {get_text(user_id, 'hours')}\n"
                elif date == yesterday:
                    yesterday_hours += hours
                    report += f"{get_text(user_id, 'night_shift')}\n"
                    report += f"{get_text(user_id, 'arrival')} {arrival_time} ({get_text(user_id, 'yesterday')})\n"
                    report += f"{get_text(user_id, 'departure')} {departure_time}\n"
                    report += f"{get_text(user_id, 'worked_shift')} {hours:.2f} {get_text(user_id, 'hours')}\n"
        if hourly_rate:
            earnings = total_hours * hourly_rate
            report += f"\n{get_text(user_id, 'earnings')} {earnings:.2f} PLN"
    else:
        report = get_text(user_id, 'no_records_today')
    conn.close()
    await update.message.reply_text(report)
    return REPORT_MENU

async def monthly_report(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    current_date = get_local_time(user_id)
    current_month = current_date.strftime('%Y-%m')
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('SELECT rate FROM hourly_rates WHERE user_id = ?', (user_id,))
    rate_record = c.fetchone()
    hourly_rate = rate_record[0] if rate_record else None
    c.execute('''SELECT date, arrival_time, departure_time FROM time_records 
                 WHERE date LIKE ? AND user_id = ?
                 ORDER BY date''', (f"{current_month}%", user_id))
    records = c.fetchall()
    if records:
        report = get_text(user_id, 'monthly_report_title').format(current_date.strftime('%B')) + "\n\n"
        monthly_total = 0
        current_day = None
        day_hours = 0
        for record in records:
            date, arrival, departure = record
            if arrival and departure:
                arrival_dt = datetime.strptime(f"{date} {arrival}", '%Y-%m-%d %H:%M:%S')
                departure_dt = datetime.strptime(f"{date} {departure}", '%Y-%m-%d %H:%M:%S')
                arrival_dt = pytz.timezone(get_user_timezone(user_id)).localize(arrival_dt)
                departure_dt = pytz.timezone(get_user_timezone(user_id)).localize(departure_dt)
                if departure_dt < arrival_dt:
                    departure_dt += timedelta(days=1)
                time_diff = departure_dt - arrival_dt
                hours = time_diff.total_seconds() / 3600
                if date != current_day:
                    if current_day:
                        report += f"{current_day}: {day_hours:.2f} {get_text(user_id, 'hours')}\n"
                    current_day = date
                    day_hours = hours
                else:
                    day_hours += hours
                monthly_total += hours
        if current_day:
            report += f"{current_day}: {day_hours:.2f} {get_text(user_id, 'hours')}\n"
        report += f"\n{get_text(user_id, 'worked_month')} {monthly_total:.2f} {get_text(user_id, 'hours')}"
        if hourly_rate:
            monthly_earnings = monthly_total * hourly_rate
            report += f"\n{get_text(user_id, 'earnings_month')} {monthly_earnings:.2f} PLN"
    else:
        report = get_text(user_id, 'no_records_month')
    conn.close()
    await update.message.reply_text(report)
    return REPORT_MENU

async def edit_report_menu(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    current_date = get_local_time(user_id)
    current_month = current_date.strftime('%Y-%m')
    # Скидаємо дію, щоб уникнути автоматичного видалення
    context.user_data['action'] = None
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('''SELECT date FROM time_records 
                 WHERE date LIKE ? AND user_id = ?
                 ORDER BY date DESC''', (f"{current_month}%", user_id))
    records = c.fetchall()
    keyboard = [
        [get_text(user_id, 'back')],
        [get_text(user_id, 'new_record'), get_text(user_id, 'delete_record')]
    ]
    if records:
        keyboard.extend([[date[0]] for date in records])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        get_text(user_id, 'choose_date_or_action'),
        reply_markup=reply_markup
    )
    conn.close()
    return WAITING_FOR_DATE

async def handle_date_selection(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    selected_option = update.message.text
    
    # Перевірка на "Назад" у всіх мовах
    if selected_option in [get_text(user_id, 'back'), '↩️ Назад', '↩️ Back', '↩️ Wstecz']:
        return await report_menu(update, context)
    # Перевірка на "Новий запис" у всіх мовах
    elif selected_option in [get_text(user_id, 'new_record'), '📝 Новий запис', '📝 New record', '📝 Nowy zapis']:
        current_date = get_local_time(user_id).date().isoformat()
        keyboard = [
            [get_text(user_id, 'today_date')],
            [get_text(user_id, 'enter_manually')],
            [get_text(user_id, 'back')]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            get_text(user_id, 'creating_new_record').format(current_date),
            reply_markup=reply_markup
        )
        return WAITING_FOR_NEW_DATE
    # Перевірка на "Видалити запис" у всіх мовах
    elif selected_option in [get_text(user_id, 'delete_record'), '🗑️ Видалити запис', '🗑️ Delete record', '🗑️ Usuń zapis']:
        keyboard = [[get_text(user_id, 'back')]]
        current_month = get_local_time(user_id).strftime('%Y-%m')
        conn = sqlite3.connect('timekeeper.db')
        c = conn.cursor()
        c.execute('''SELECT date FROM time_records 
                     WHERE date LIKE ? AND user_id = ?
                     ORDER BY date DESC''', (f"{current_month}%", user_id))
        records = c.fetchall()
        if records:
            keyboard.extend([[date[0]] for date in records])
        conn.close()
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            get_text(user_id, 'choose_date_to_delete'),
            reply_markup=reply_markup
        )
        context.user_data['action'] = 'delete'
        return WAITING_FOR_DATE
    if context.user_data.get('action') == 'delete':
        context.user_data['delete_date'] = selected_option
        keyboard = [
            [InlineKeyboardButton(get_text(user_id, 'yes'), callback_data=f"delete_yes_{selected_option}"),
             InlineKeyboardButton(get_text(user_id, 'no'), callback_data="delete_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            get_text(user_id, 'confirm_delete').format(selected_option),
            reply_markup=reply_markup
        )
        return DELETE_CONFIRM
    context.user_data['edit_date'] = selected_option
    keyboard = [
        [get_text(user_id, 'arrival_time'), get_text(user_id, 'departure_time')],
        [get_text(user_id, 'back')]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        get_text(user_id, 'edit_what').format(selected_option),
        reply_markup=reply_markup
    )
    return EDIT_TIME

async def handle_delete_confirmation(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if query.data.startswith("delete_yes_"):
        date_to_delete = query.data.replace("delete_yes_", "")
        try:
            conn = sqlite3.connect('timekeeper.db')
            c = conn.cursor()
            c.execute('PRAGMA busy_timeout = 10000')
            c.execute('DELETE FROM time_records WHERE date = ? AND user_id = ?',
                      (date_to_delete, user_id))
            conn.commit()
            await query.edit_message_text(get_text(user_id, 'record_deleted').format(date_to_delete))
            conn.close()
            # Повертаємо в головне меню
            keyboard = [
                [get_text(user_id, 'record_time'), get_text(user_id, 'report')],
                [get_text(user_id, 'settings')],
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await context.bot.send_message(
                chat_id=user_id,
                text=get_text(user_id, 'welcome_back'),
                reply_markup=reply_markup
            )
            return MAIN_MENU
        except sqlite3.Error:
            await query.edit_message_text(get_text(user_id, 'delete_failed'))
            return MAIN_MENU
    else:  # delete_no
        await query.edit_message_text(get_text(user_id, 'delete_cancelled'))
        # Повертаємо в меню редагування
        keyboard = [
            [get_text(user_id, 'daily_report'), get_text(user_id, 'monthly_report')],
            [get_text(user_id, 'edit_report'), get_text(user_id, 'back')]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await context.bot.send_message(
            chat_id=user_id,
            text=get_text(user_id, 'choose_report_type'),
            reply_markup=reply_markup
        )
        return REPORT_MENU

async def handle_time_edit(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    choice = update.message.text
    
    # Перевірка на "Назад" у всіх мовах
    if choice in [get_text(user_id, 'back'), '↩️ Назад', '↩️ Back', '↩️ Wstecz']:
        return await edit_report_menu(update, context)
    
    # Визначаємо тип за емодзі або текстом
    if '🟢' in choice or 'arrival' in choice.lower() or 'приход' in choice.lower() or 'przyjś' in choice.lower():
        context.user_data['edit_type'] = 'arrival_time'
    else:
        context.user_data['edit_type'] = 'departure_time'
    
    keyboard = [[get_text(user_id, 'cancel')]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        get_text(user_id, 'enter_new_time'),
        reply_markup=reply_markup
    )
    return EDIT_REPORT

async def save_edited_time(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    new_time = update.message.text
    edit_date = context.user_data['edit_date']
    current_date = get_local_time(user_id).date().isoformat()
    
    # Перевірка на скасування у всіх мовах
    if new_time in [get_text(user_id, 'cancel'), '❌ Скасувати', '❌ Cancel', '❌ Anuluj']:
        return await report_menu(update, context)
    
    try:
        parsed_time = parse_time_input(new_time)
        conn = sqlite3.connect('timekeeper.db')
        c = conn.cursor()
        c.execute(f'''UPDATE time_records 
                     SET {context.user_data['edit_type']} = ?
                     WHERE date = ? AND user_id = ?''',
                  (parsed_time, edit_date, user_id))
        conn.commit()
        conn.close()
        if edit_date == current_date:
            await update.message.reply_text(get_text(user_id, 'time_updated'))
        else:
            await update.message.reply_text(get_text(user_id, 'time_updated_for_date').format(edit_date))
        return await report_menu(update, context)
    except ValueError:
        await update.message.reply_text(get_text(user_id, 'invalid_time_format'))
        return EDIT_REPORT

async def handle_new_date(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    selected_option = update.message.text
    
    # Перевірка на "Назад" або "Скасувати" у всіх мовах
    if selected_option in [get_text(user_id, 'back'), get_text(user_id, 'cancel'), '↩️ Назад', '❌ Скасувати', '↩️ Back', '❌ Cancel', '↩️ Wstecz', '❌ Anuluj']:
        return await edit_report_menu(update, context)
    # Перевірка на "Сьогоднішня дата" у всіх мовах
    elif selected_option in [get_text(user_id, 'today_date'), '📅 Сьогоднішня дата', '📅 Today\'s date', '📅 Dzisiejsza data']:
        new_date = get_local_time(user_id).date().isoformat()
    # Перевірка на "Ввести вручну" у всіх мовах
    elif selected_option in [get_text(user_id, 'enter_manually'), '✍️ Ввести вручну', '✍️ Enter manually', '✍️ Wprowadź ręcznie']:
        keyboard = [[get_text(user_id, 'cancel')]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            get_text(user_id, 'enter_date_format'),
            reply_markup=reply_markup
        )
        return WAITING_FOR_NEW_DATE
    else:
        new_date = selected_option
    try:
        input_date = datetime.strptime(new_date, '%Y-%m-%d')
        if input_date.date() > get_local_time(user_id).date():
            await update.message.reply_text(get_text(user_id, 'no_future_dates'))
            return await edit_report_menu(update, context)
        conn = sqlite3.connect('timekeeper.db')
        c = conn.cursor()
        c.execute('''SELECT arrival_time FROM time_records 
                    WHERE date = ? AND user_id = ?''',
                  (new_date, user_id))
        existing_record = c.fetchone()
        conn.close()
        if existing_record:
            await update.message.reply_text(get_text(user_id, 'record_exists'))
            return await edit_report_menu(update, context)
        context.user_data['new_date'] = new_date
        keyboard = [[get_text(user_id, 'cancel')]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            get_text(user_id, 'enter_arrival_time'),
            reply_markup=reply_markup
        )
        context.user_data['new_record_type'] = 'arrival_time'
        return SAVE_NEW_RECORD
    except ValueError:
        await update.message.reply_text(get_text(user_id, 'invalid_date_format'))
        keyboard = [
            [get_text(user_id, 'today_date')],
            [get_text(user_id, 'enter_manually')],
            [get_text(user_id, 'back')],
            [get_text(user_id, 'cancel')]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            get_text(user_id, 'creating_new_record').format(get_local_time(user_id).date().isoformat()),
            reply_markup=reply_markup
        )
        return WAITING_FOR_NEW_DATE

async def save_new_record(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    new_time = update.message.text
    
    # Перевірка на "Назад" або "Скасувати" у всіх мовах
    if new_time in [get_text(user_id, 'back'), get_text(user_id, 'cancel'), '↩️ Назад', '❌ Скасувати', '↩️ Back', '❌ Cancel', '↩️ Wstecz', '❌ Anuluj']:
        return await edit_report_menu(update, context)
    
    try:
        parsed_time = parse_time_input(new_time)
        conn = sqlite3.connect('timekeeper.db')
        c = conn.cursor()
        
        if context.user_data['new_record_type'] == 'arrival_time':
            c.execute('''INSERT INTO time_records (date, user_id, arrival_time)
                        VALUES (?, ?, ?)''',
                      (context.user_data['new_date'], user_id, parsed_time))
            conn.commit()
            conn.close()
            keyboard = [[get_text(user_id, 'cancel')]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                get_text(user_id, 'arrival_time_saved'),
                reply_markup=reply_markup
            )
            context.user_data['new_record_type'] = 'departure_time'
            return SAVE_NEW_RECORD
        elif context.user_data['new_record_type'] == 'departure_time':
            c.execute('''UPDATE time_records 
                        SET departure_time = ?
                        WHERE date = ? AND user_id = ?''',
                      (parsed_time, context.user_data['new_date'], user_id))
            conn.commit()
            conn.close()
            await update.message.reply_text(get_text(user_id, 'departure_time_saved'))
            return await report_menu(update, context)
    except ValueError:
        await update.message.reply_text(get_text(user_id, 'invalid_time_format'))
        keyboard = [[get_text(user_id, 'cancel')]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        return SAVE_NEW_RECORD

async def show_daily_stats(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    current_date = get_local_time(user_id).date()
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('''SELECT arrival_time, departure_time 
                 FROM time_records 
                 WHERE date = ? AND user_id = ?''',
              (current_date.isoformat(), user_id))
    record = c.fetchone()
    if record:
        arrival_time, departure_time = record
        if arrival_time and departure_time:
            arrival_dt = datetime.strptime(f"{current_date} {arrival_time}", '%Y-%m-%d %H:%M:%S')
            departure_dt = datetime.strptime(f"{current_date} {departure_time}", '%Y-%m-%d %H:%M:%S')
            arrival_dt = pytz.timezone(get_user_timezone(user_id)).localize(arrival_dt)
            departure_dt = pytz.timezone(get_user_timezone(user_id)).localize(departure_dt)
            if departure_dt < arrival_dt:
                departure_dt += timedelta(days=1)
            worked_time = departure_dt - arrival_dt
            hours = worked_time.total_seconds() / 3600
            stats = (
                f"{get_text(user_id, 'stats_today')}\n\n"
                f"{get_text(user_id, 'arrival')} {arrival_time}\n"
                f"{get_text(user_id, 'departure')} {departure_time}\n"
                f"{get_text(user_id, 'worked_today')} {hours:.2f} {get_text(user_id, 'hours')}"
            )
        else:
            stats = (
                f"{get_text(user_id, 'stats_today')}\n\n"
                f"{get_text(user_id, 'arrival')} {arrival_time}\n"
                f"{get_text(user_id, 'departure')} {get_text(user_id, 'not_recorded_yet')}"
            )
    else:
        yesterday = (current_date - timedelta(days=1)).isoformat()
        c.execute('''SELECT arrival_time 
                    FROM time_records 
                    WHERE date = ? AND user_id = ? AND departure_time IS NULL''',
                  (yesterday, user_id))
        yesterday_record = c.fetchone()
        if yesterday_record:
            stats = (
                f"{get_text(user_id, 'current_shift')}\n\n"
                f"{get_text(user_id, 'arrival')} {yesterday_record[0]} ({get_text(user_id, 'yesterday')})\n"
                f"{get_text(user_id, 'departure')} {get_text(user_id, 'not_recorded_yet')}"
            )
        else:
            stats = get_text(user_id, 'no_time_records')
    conn.close()
    keyboard = [
        [get_text(user_id, 'record_time'), get_text(user_id, 'report')],
        [get_text(user_id, 'settings')],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(stats, reply_markup=reply_markup)
    return MAIN_MENU

async def settings_menu(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    keyboard = [
        [get_text(user_id, 'reset_time'), get_text(user_id, 'set_rate')],
        [get_text(user_id, 'set_timezone'), get_text(user_id, 'set_language')],
        [get_text(user_id, 'history')],
        [get_text(user_id, 'back')]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(get_text(user_id, 'settings_title'), reply_markup=reply_markup)
    return SETTINGS_MENU

async def reset_time(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    current_date = get_local_time(user_id).date().isoformat()
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('''DELETE FROM time_records 
                 WHERE date = ? AND user_id = ?''', (current_date, user_id))
    if c.rowcount > 0:
        await update.message.reply_text(get_text(user_id, 'reset_today'))
    else:
        await update.message.reply_text(get_text(user_id, 'no_reset_records'))
    conn.commit()
    conn.close()
    return await start(update, context)

async def set_hourly_rate(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    keyboard = [[get_text(user_id, 'cancel')]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(get_text(user_id, 'enter_rate'), reply_markup=reply_markup)
    return WAITING_FOR_RATE

async def save_hourly_rate(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    
    # Перевірка на скасування у всіх мовах
    if update.message.text in [get_text(user_id, 'cancel'), '❌ Скасувати', '❌ Cancel', '❌ Anuluj']:
        return await settings_menu(update, context)
    
    try:
        rate = float(update.message.text)
        if rate <= 0:
            raise ValueError(get_text(user_id, 'invalid_rate'))
        conn = sqlite3.connect('timekeeper.db')
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO hourly_rates (user_id, rate)
                    VALUES (?, ?)''', (user_id, rate))
        conn.commit()
        conn.close()
        await update.message.reply_text(f'{get_text(user_id, "rate_set")} {rate} PLN')
        return await settings_menu(update, context)
    except ValueError:
        await update.message.reply_text(get_text(user_id, 'invalid_rate'))
        return WAITING_FOR_RATE

async def set_timezone(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    keyboard = [[tz] for tz in AVAILABLE_TIMEZONES]
    keyboard.append([get_text(user_id, 'back')])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        get_text(user_id, 'choose_timezone'),
        reply_markup=reply_markup
    )
    return SET_TIMEZONE

async def save_timezone(update: Update, context: CallbackContext) -> int:
    selected_timezone = update.message.text
    user_id = update.effective_user.id
    if selected_timezone == get_text(user_id, 'back'):
        return await settings_menu(update, context)
    if selected_timezone not in AVAILABLE_TIMEZONES:
        await update.message.reply_text(get_text(user_id, 'invalid_timezone'))
        return SET_TIMEZONE
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO user_timezones (user_id, timezone)
                VALUES (?, ?)''', (user_id, selected_timezone))
    conn.commit()
    conn.close()
    await update.message.reply_text(f'{get_text(user_id, "timezone_set")} {selected_timezone}')
    return await settings_menu(update, context)

async def set_language(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    keyboard = [
        [get_text(user_id, 'ukrainian')],
        [get_text(user_id, 'english')],
        [get_text(user_id, 'polish')],
        [get_text(user_id, 'back')]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        get_text(user_id, 'choose_language'),
        reply_markup=reply_markup
    )
    return SET_LANGUAGE

async def save_language(update: Update, context: CallbackContext) -> int:
    selected_language = update.message.text
    user_id = update.effective_user.id
    
    # Перевірка на "Назад" у всіх мовах
    if selected_language in [get_text(user_id, 'back'), '↩️ Назад', '↩️ Back', '↩️ Wstecz']:
        return await settings_menu(update, context)
    
    # Визначаємо код мови
    language_code = None
    if selected_language in [LANGUAGES['uk']['ukrainian'], LANGUAGES['en']['ukrainian'], LANGUAGES['pl']['ukrainian']]:
        language_code = 'uk'
    elif selected_language in [LANGUAGES['uk']['english'], LANGUAGES['en']['english'], LANGUAGES['pl']['english']]:
        language_code = 'en'
    elif selected_language in [LANGUAGES['uk']['polish'], LANGUAGES['en']['polish'], LANGUAGES['pl']['polish']]:
        language_code = 'pl'
    
    if not language_code:
        await update.message.reply_text(get_text(user_id, 'invalid_language'))
        return SET_LANGUAGE
    
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO user_languages (user_id, language)
                VALUES (?, ?)''', (user_id, language_code))
    conn.commit()
    conn.close()
    
    # Відправляємо повідомлення новою мовою (тепер мова оновлена в БД)
    await update.message.reply_text(get_text(user_id, 'language_set'))
    return await settings_menu(update, context)

async def view_past_reports(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    conn = sqlite3.connect('timekeeper.db')
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT substr(date, 1, 7) as month
        FROM time_records
        WHERE user_id = ?
        ORDER BY month DESC
    ''', (user_id,))
    months = c.fetchall()
    conn.close()
    keyboard = [[get_text(user_id, 'back')]]
    for month in months:
        date_obj = datetime.strptime(month[0], '%Y-%m')
        formatted_month = date_obj.strftime('%B %Y')
        keyboard.append([formatted_month])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(get_text(user_id, 'choose_month'), reply_markup=reply_markup)
    return SELECT_MONTH

async def view_selected_month_report(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    selected_month = update.message.text
    
    # Перевірка на "Назад" у всіх мовах
    if selected_month in [get_text(user_id, 'back'), '↩️ Назад', '↩️ Back', '↩️ Wstecz']:
        return await settings_menu(update, context)
    try:
        date_obj = datetime.strptime(selected_month, '%B %Y')
        month_db_format = date_obj.strftime('%Y-%m')
        context.user_data['selected_month'] = month_db_format
        conn = sqlite3.connect('timekeeper.db')
        c = conn.cursor()
        c.execute('SELECT rate FROM hourly_rates WHERE user_id = ?', (user_id,))
        rate_record = c.fetchone()
        hourly_rate = rate_record[0] if rate_record else None
        c.execute('''
            SELECT date, arrival_time, departure_time 
            FROM time_records 
            WHERE date LIKE ? AND user_id = ?
            ORDER BY date
        ''', (f"{month_db_format}%", user_id))
        records = c.fetchall()
        if records:
            report = get_text(user_id, 'monthly_report_title').format(selected_month) + "\n\n"
            monthly_total = 0
            current_day = None
            day_hours = 0
            for record in records:
                date, arrival, departure = record
                if arrival and departure:
                    arrival_dt = datetime.strptime(f"{date} {arrival}", '%Y-%m-%d %H:%M:%S')
                    departure_dt = datetime.strptime(f"{date} {departure}", '%Y-%m-%d %H:%M:%S')
                    arrival_dt = pytz.timezone(get_user_timezone(user_id)).localize(arrival_dt)
                    departure_dt = pytz.timezone(get_user_timezone(user_id)).localize(departure_dt)
                    if departure_dt < arrival_dt:
                        departure_dt += timedelta(days=1)
                    time_diff = departure_dt - arrival_dt
                    hours = time_diff.total_seconds() / 3600
                    if date != current_day:
                        if current_day:
                            report += f"{current_day}: {day_hours:.2f} {get_text(user_id, 'hours')}\n"
                        current_day = date
                        day_hours = hours
                    else:
                        day_hours += hours
                    monthly_total += hours
            if current_day:
                report += f"{current_day}: {day_hours:.2f} {get_text(user_id, 'hours')}\n"
            report += f"\n{get_text(user_id, 'worked_month')} {monthly_total:.2f} {get_text(user_id, 'hours')}"
            if hourly_rate:
                monthly_earnings = monthly_total * hourly_rate
                report += f"\n{get_text(user_id, 'earnings_month')} {monthly_earnings:.2f} PLN"
            keyboard = [
                [get_text(user_id, 'select_specific_day')],
                [get_text(user_id, 'back_to_month_selection')]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(report, reply_markup=reply_markup)
            return VIEW_SELECTED_REPORT
        else:
            await update.message.reply_text(get_text(user_id, 'no_records_month'))
            return await view_past_reports(update, context)
    except ValueError:
        await update.message.reply_text(get_text(user_id, 'date_processing_error'))
        return SELECT_MONTH

async def handle_selected_report(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    choice = update.message.text
    
    # Перевірка на "Назад до вибору місяця" у всіх мовах
    if choice in [get_text(user_id, 'back_to_month_selection'), '↩️ Назад до вибору місяця', '↩️ Back to month selection', '↩️ Powrót do wyboru miesiąca']:
        return await view_past_reports(update, context)
    # Перевірка на "Обрати конкретний день" у всіх мовах
    elif choice in [get_text(user_id, 'select_specific_day'), '📅 Обрати конкретний день', '📅 Select specific day', '📅 Wybierz konkretny dzień']:
        selected_month = context.user_data.get('selected_month')
        conn = sqlite3.connect('timekeeper.db')
        c = conn.cursor()
        c.execute('''
            SELECT DISTINCT date
            FROM time_records
            WHERE date LIKE ? AND user_id = ?
            ORDER BY date DESC
        ''', (f"{selected_month}%", user_id))
        days = c.fetchall()
        conn.close()
        keyboard = [[get_text(user_id, 'back_to_report')]]
        for day in days:
            date_obj = datetime.strptime(day[0], '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d %B %Y')
            keyboard.append([formatted_date])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(get_text(user_id, 'choose_day_detail'), reply_markup=reply_markup)
        return SELECT_DAY
    return VIEW_SELECTED_REPORT

async def view_selected_day_report(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    selected_day = update.message.text
    
    # Перевірка на "Назад до звіту" у всіх мовах
    if selected_day in [get_text(user_id, 'back_to_report'), '↩️ Назад до звіту', '↩️ Back to report', '↩️ Powrót do raportu']:
        month = context.user_data.get('selected_month')
        if month:
            keyboard = [
                [get_text(user_id, 'select_specific_day')],
                [get_text(user_id, 'back_to_month_selection')]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            conn = sqlite3.connect('timekeeper.db')
            c = conn.cursor()
            c.execute('SELECT rate FROM hourly_rates WHERE user_id = ?', (user_id,))
            rate_record = c.fetchone()
            hourly_rate = rate_record[0] if rate_record else None
            c.execute('''
                SELECT date, arrival_time, departure_time 
                FROM time_records 
                WHERE date LIKE ? AND user_id = ?
                ORDER BY date
            ''', (f"{month}%", user_id))
            records = c.fetchall()
            if records:
                date_obj = datetime.strptime(month, '%Y-%m')
                formatted_month = date_obj.strftime('%B %Y')
                report = get_text(user_id, 'monthly_report_title').format(formatted_month) + "\n\n"
                monthly_total = 0
                current_day = None
                day_hours = 0
                for record in records:
                    date, arrival, departure = record
                    if arrival and departure:
                        arrival_dt = datetime.strptime(f"{date} {arrival}", '%Y-%m-%d %H:%M:%S')
                        departure_dt = datetime.strptime(f"{date} {departure}", '%Y-%m-%d %H:%M:%S')
                        arrival_dt = pytz.timezone(get_user_timezone(user_id)).localize(arrival_dt)
                        departure_dt = pytz.timezone(get_user_timezone(user_id)).localize(departure_dt)
                        if departure_dt < arrival_dt:
                            departure_dt += timedelta(days=1)
                        time_diff = departure_dt - arrival_dt
                        hours = time_diff.total_seconds() / 3600
                        if date != current_day:
                            if current_day:
                                report += f"{current_day}: {day_hours:.2f} {get_text(user_id, 'hours')}\n"
                            current_day = date
                            day_hours = hours
                        else:
                            day_hours += hours
                        monthly_total += hours
                if current_day:
                    report += f"{current_day}: {day_hours:.2f} {get_text(user_id, 'hours')}\n"
                report += f"\n{get_text(user_id, 'worked_month')} {monthly_total:.2f} {get_text(user_id, 'hours')}"
                if hourly_rate:
                    monthly_earnings = monthly_total * hourly_rate
                    report += f"\n{get_text(user_id, 'earnings_month')} {monthly_earnings:.2f} PLN"
                await update.message.reply_text(report, reply_markup=reply_markup)
                conn.close()
                return VIEW_SELECTED_REPORT
            conn.close()
        return await view_past_reports(update, context)
    try:
        date_obj = datetime.strptime(selected_day, '%d %B %Y')
        date_db_format = date_obj.strftime('%Y-%m-%d')
        conn = sqlite3.connect('timekeeper.db')
        c = conn.cursor()
        c.execute('SELECT rate FROM hourly_rates WHERE user_id = ?', (user_id,))
        rate_record = c.fetchone()
        hourly_rate = rate_record[0] if rate_record else None
        c.execute('''
            SELECT arrival_time, departure_time 
            FROM time_records 
            WHERE date = ? AND user_id = ?
        ''', (date_db_format, user_id))
        record = c.fetchone()
        if record:
            arrival_time, departure_time = record
            report = get_text(user_id, 'detailed_report_for').format(selected_day) + "\n\n"
            if arrival_time and departure_time:
                arrival_dt = datetime.strptime(f"{date_db_format} {arrival_time}", '%Y-%m-%d %H:%M:%S')
                departure_dt = datetime.strptime(f"{date_db_format} {departure_time}", '%Y-%m-%d %H:%M:%S')
                arrival_dt = pytz.timezone(get_user_timezone(user_id)).localize(arrival_dt)
                departure_dt = pytz.timezone(get_user_timezone(user_id)).localize(departure_dt)
                if departure_dt < arrival_dt:
                    departure_dt += timedelta(days=1)
                worked_time = departure_dt - arrival_dt
                hours = worked_time.total_seconds() / 3600
                report += (
                    f"{get_text(user_id, 'arrival')} {arrival_time}\n"
                    f"{get_text(user_id, 'departure')} {departure_time}\n"
                    f"{get_text(user_id, 'worked')} {hours:.2f} {get_text(user_id, 'hours')}"
                )
                if hourly_rate:
                    earnings = hours * hourly_rate
                    report += f"\n{get_text(user_id, 'earnings')} {earnings:.2f} PLN"
            else:
                report += (
                    f"{get_text(user_id, 'arrival')} {arrival_time}\n"
                    f"{get_text(user_id, 'departure')} {get_text(user_id, 'not_recorded_yet')}"
                )
            keyboard = [[get_text(user_id, 'back_to_report')]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(report, reply_markup=reply_markup)
        else:
            await update.message.reply_text(get_text(user_id, 'no_day_records'))
        conn.close()
        return SELECT_DAY
    except ValueError:
        await update.message.reply_text(get_text(user_id, 'date_processing_error'))
        return SELECT_DAY

def main() -> None:
    setup_database()
    logging.getLogger('telegram.ext').setLevel(logging.WARNING)
    application = Application.builder().token("7631269439:AAGPjfze-xKaMbQZtJNXiTUXxN3JN0E_LmI").build()
    application.add_handler(CommandHandler('infouser', infouser_command))
    application.add_handler(CommandHandler('exportusers', export_users_command))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex('^⏱'), time_recording_menu),
                MessageHandler(filters.Regex('^📊'), report_menu),
                MessageHandler(filters.Regex('^⚙️'), settings_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, show_daily_stats),
            ],
            TIME_RECORDING: [
                MessageHandler(filters.Regex('^🟢|^👋.*приходу|^👋.*arrival|^👋.*przyjścia'), record_arrival),
                MessageHandler(filters.Regex('^🔴|^👋.*відходу|^👋.*departure|^👋.*wyjścia'), record_departure),
                MessageHandler(filters.Regex('^↩️'), start),
            ],
            REPORT_MENU: [
                MessageHandler(filters.Regex('^📅'), daily_report),
                MessageHandler(filters.Regex('^📈'), monthly_report),
                MessageHandler(filters.Regex('^✏️'), edit_report_menu),
                MessageHandler(filters.Regex('^↩️'), start),
            ],
            SETTINGS_MENU: [
                MessageHandler(filters.Regex('^🔄'), reset_time),
                MessageHandler(filters.Regex('^💰'), set_hourly_rate),
                MessageHandler(filters.Regex('^🕰'), set_timezone),
                MessageHandler(filters.Regex('^🌐'), set_language),
                MessageHandler(filters.Regex('^📊'), view_past_reports),
                MessageHandler(filters.Regex('^↩️'), start),
            ],
            SET_TIMEZONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_timezone),
            ],
            SET_LANGUAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_language),
            ],
            WAITING_FOR_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_selection),
            ],
            EDIT_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_edit),
            ],
            EDIT_REPORT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_edited_time),
            ],
            WAITING_FOR_NEW_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_date),
            ],
            SAVE_NEW_RECORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_record),
            ],
            DELETE_CONFIRM: [
                CallbackQueryHandler(handle_delete_confirmation, pattern='^delete_'),
            ],
            WAITING_FOR_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_hourly_rate),
            ],
            SELECT_MONTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, view_selected_month_report),
            ],
            SELECT_DAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, view_selected_day_report),
            ],
            VIEW_SELECTED_REPORT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_selected_report),
            ],
        },
        fallbacks=[CommandHandler('start', start)],
        per_message=False,
    )
    print("\033[5;32m🎉 Бот успішно запущений та готовий до роботи! 🟢\033[0m")
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
