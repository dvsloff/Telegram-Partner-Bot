from config import Config


class Messages:
    @staticmethod
    def get_welcome_message(name):
        return f"""👋 Привет, {name}!

Добро пожаловать в нашу партнёрскую программу! Мы рады видеть тебя в нашей команде."""

    @staticmethod
    def get_offer_messages():
        return Config.WELCOME_MESSAGES

    @staticmethod
    def get_about_text():
        return """🏢 О нашей компании

Мы занимаемся развитием перспективных проектов в сфере digital. Наша миссия - создавать взаимовыгодные партнёрства.

• Более 1000 довольных партнёров
• 50+ успешных проектов
• 5 лет на рынке"""

    @staticmethod
    def get_partnership_info():
        return """💼 Партнёрская программа

Условия сотрудничества:
• Высокие комиссионные - до 30%
• Регулярные выплаты каждую неделю
• Поддержка 24/7
• Персональный менеджер

Стань частью нашей команды!"""

    @staticmethod
    def get_agreement_text():
        return """📝 Партнёрское соглашение

Основные условия:
1. Вы получаете вознаграждение за каждого привлеченного клиента
2. Выплаты производятся по запросу от 1000 руб.
3. Запрещено спам-рассылки и недобросовестные методы привлечения
4. Мы оставляем за собой право изменять условия с уведомлением

Нажимая "Подписать", вы соглашаетесь с условиями."""

    @staticmethod
    def get_stats_text(stats, ref_link):
        return f"""📊 Ваша статистика

👥 Всего привлечено: {stats['total']}
✅ Подтверждено: {stats['confirmed']} 
🟡 Ожидают: {stats['pending']}
🔥 Активных: {stats['active']}

💰 Финансы:
💵 Общий доход: {stats['total_income']} руб.
💳 Доступно для вывода: {stats['available_balance']} руб.
⏳ Ожидает выплаты: {stats['pending_payouts']} руб.
✅ Выплачено: {stats['paid_payouts']} руб.

💎 Ваша реферальная ссылка:
{ref_link}"""

    @staticmethod
    def get_documents_text():
        return """📄 Документы

• Партнёрское соглашение: https://example.com/agreement.pdf
• Инструкция по работе: https://example.com/guide.pdf
• Рекламные материалы: https://example.com/materials.zip

Скачайте и ознакомьтесь с документами"""

    @staticmethod
    def get_payouts_text(stats):
        return f"""💰 Выплаты

💵 Доступно для вывода: {stats['available_balance']} руб.
⏳ Ожидает выплаты: {stats['pending_payouts']} руб.

Условия выплат:
• Минимальная сумма: {Config.MIN_PAYOUT} руб.
• Выплаты: каждую пятницу
• Способы: банковская карта, Qiwi, ЮMoney"""

    @staticmethod
    def get_support_text():
        return """🆘 Поддержка

Техническая поддержка: @support_username
По вопросам выплат: @finance_username  
Общие вопросы: @manager_username

Мы всегда готовы помочь!"""

    @staticmethod
    def get_payout_request_text():
        return """💳 Запрос выплаты

Выберите способ получения выплаты:"""

    @staticmethod
    def get_payout_method_text(method):
        methods = {
            'card': 'банковскую карту',
            'qiwi': 'Qiwi кошелёк',
            'yoomoney': 'ЮMoney'
        }
        return f"""💳 Запрос выплаты

Вы выбрали: {methods[method]}

Введите реквизиты для выплаты:
Для карты: номер карты
Для Qiwi: номер телефона
Для ЮMoney: номер кошелька

И сумму для вывода (от {Config.MIN_PAYOUT} руб.):"""

    @staticmethod
    def get_payout_success_text():
        return """✅ Запрос на выплату отправлен!

Ваша заявка принята в обработку. Обычно выплаты производятся в течение 1-3 рабочих дней.

Статус выплаты можно отслеживать в разделе "История выплат" """

    @staticmethod
    def get_admin_stats_text(total_users, signed_users, total_referrals, pending_payouts):
        conversion = (signed_users / total_users * 100) if total_users > 0 else 0
        return f"""📈 Общая статистика

👥 Всего пользователей: {total_users}
✅ Подписали соглашение: {signed_users}
📊 Конверсия: {conversion:.1f}%
🔗 Всего рефералов: {total_referrals}
💰 Ожидает выплат: {pending_payouts} руб."""

    @staticmethod
    def get_broadcast_start_text():
        return """📢 Рассылка сообщений

Доступные действия:
• Текст рассылки - установить текст сообщения
• Получатели - выбрать аудиторию
• Начать рассылку - запустить рассылку

Текущие настройки сохраняются до перезапуска бота"""

    @staticmethod
    def get_recipients_selection_text():
        return """👥 Выбор получателей

Выберите аудиторию для рассылки:

Все пользователи - все кто когда-либо запускал бота
Подписавшие соглашение - только активные партнёры
Неподписавшие - пользователи которые ещё не стали партнёрами"""

    @staticmethod
    def get_broadcast_preview_text(text, recipients_type, users_count):
        recipients_names = {
            'all': 'Все пользователи',
            'signed': 'Подписавшие соглашение',
            'unsigned': 'Неподписавшие'
        }

        return f"""📢 Предпросмотр рассылки

Текст сообщения:
{text}

Получатели: {recipients_names[recipients_type]}
Количество: {users_count} пользователей

Вы уверены что хотите начать рассылку?"""

    @staticmethod
    def get_broadcast_progress_text(sent, total, failed):
        progress = (sent / total * 100) if total > 0 else 0
        return f"""📤 Идет рассылка...

📊 Прогресс: {sent}/{total} ({progress:.1f}%)
✅ Успешно: {sent}
❌ Ошибок: {failed}

Пожалуйста, подождите..."""

    @staticmethod
    def get_broadcast_result_text(sent, failed, total_users):
        effectiveness = (sent / total_users * 100) if total_users > 0 else 0
        return f"""✅ Рассылка завершена!

📊 Результаты:
👥 Всего получателей: {total_users}
✅ Успешно отправлено: {sent}
❌ Ошибок доставки: {failed}
📈 Эффективность: {effectiveness:.1f}%

Рассылка сохранена в истории администратора"""