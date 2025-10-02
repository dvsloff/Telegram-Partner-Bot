import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from sqlalchemy import select, func
import os
from config import Config
from database import Database, User, Referral, Payout
from keyboards import (
    get_main_menu_keyboard, get_agreement_keyboard, get_admin_keyboard,
    get_payouts_keyboard, get_payment_methods_keyboard, get_broadcast_keyboard,
    get_back_keyboard, get_payout_management_keyboard, get_recipients_keyboard,
    get_broadcast_confirmation_keyboard
)
from messages import Messages

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Глобальные переменные для хранения состояния рассылки
broadcast_data = {
    'text': None,
    'recipients': 'all',  # all, signed, unsigned
    'users_count': 0
}

class PartnerBot:
    def __init__(self, token):
        self.application = Application.builder().token(token).build()
        self.db = Database()
        self.broadcast_data = {
            'text': None,
            'recipients': 'all',
            'users_count': 0
        }
        self.setup_handlers()

    def setup_handlers(self):
        # Команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("stats", self.stats))
        self.application.add_handler(CommandHandler("payout", self.payout))
        self.application.add_handler(CommandHandler("admin", self.admin))
        self.application.add_handler(CommandHandler("debug", self.debug_users))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def debug_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Временная команда для отладки"""
            if update.effective_user.id == Config.ADMIN_ID:
                users_all = self.db.get_all_users()
                users_signed = self.db.get_all_users(signed_only=True)

                text = f"""🐞 *Отладочная информация*

    📊 База данных:
    • Всего пользователей: {len(users_all)}
    • Подписавших соглашение: {len(users_signed)}
    • Неподписавших: {len(users_all) - len(users_signed)}

    👥 Примеры пользователей:"""

                for i, user in enumerate(users_all[:5]):  # Покажем первых 5
                    text += f"\n{i + 1}. ID: {user.user_id}, Имя: {user.first_name}, Подписал: {user.signed_agreement}"

                await update.message.reply_text(text)

    async def safe_edit_message(self, query, text, reply_markup=None, parse_mode=None):
        try:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as e:
            logging.error(f"Ошибка редактирования сообщения: {e}")
            try:
                await query.message.reply_text(
                    text=text,
                    reply_markup=reply_markup
                )
            except Exception as e2:
                logging.error(f"Ошибка отправки нового сообщения: {e2}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        db_user = self.db.get_user(user.id)

        # Обработка реферальной ссылки
        if context.args:
            ref_link = context.args[0]
            if ref_link.startswith('ref_'):
                if not db_user:
                    db_user = self.db.create_user(user)
                    ref_owner = self.db.get_user_by_referral_link(ref_link)
                    if ref_owner and ref_owner.user_id != user.id:
                        self.db.add_referral(ref_owner.user_id, user.id)
                        if db_user and db_user.signed_agreement:
                            self.db.confirm_referral(user.id)
                        try:
                            await context.bot.send_message(
                                chat_id=ref_owner.user_id,
                                text=f"🎉 По вашей ссылке зарегистрировался новый партнёр: {user.first_name}"
                            )
                        except Exception as e:
                            logging.error(f"Ошибка уведомления реферера: {e}")

        if not db_user:
            db_user = self.db.create_user(user)
            for message in Messages.get_offer_messages():
                await update.message.reply_text(message)
                await asyncio.sleep(1)

        keyboard = get_main_menu_keyboard(db_user.signed_agreement if db_user else False)
        await update.message.reply_text(
            Messages.get_welcome_message(user.first_name),
            reply_markup=keyboard
        )

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        db_user = self.db.get_user(user.id)

        if not db_user or not db_user.signed_agreement:
            await update.message.reply_text("❌ Доступно только после подписания соглашения")
            return

        stats = self.db.get_user_stats(user.id)
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={db_user.referral_link}"

        stats_text = Messages.get_stats_text(stats, ref_link)
        await update.message.reply_text(stats_text)

    async def payout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        db_user = self.db.get_user(user.id)

        if not db_user or not db_user.signed_agreement:
            await update.message.reply_text("❌ Доступно только после подписания соглашения")
            return

        stats = self.db.get_user_stats(user.id)
        payouts_text = Messages.get_payouts_text(stats)
        await update.message.reply_text(
            payouts_text,
            reply_markup=get_payouts_keyboard()
        )

    async def admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id == Config.ADMIN_ID:
            await update.message.reply_text(
                "👨‍💻 Панель администратора",
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text("❌ У вас нет прав администратора")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        text = update.message.text

        # Проверяем, ожидаем ли мы данные для выплаты
        if hasattr(context, 'user_data') and context.user_data.get('awaiting_payout'):
            payment_method = context.user_data.get('payment_method')

            try:
                lines = text.split('\n')
                details = lines[0].strip()
                amount_text = lines[-1] if len(lines) > 1 else text
                import re
                amount_match = re.search(r'(\d+(?:[.,]\d+)?)', amount_text)

                if amount_match:
                    amount = float(amount_match.group(1).replace(',', '.'))
                else:
                    await update.message.reply_text("❌ Не удалось найти сумму. Пожалуйста, введите сумму цифрами.")
                    return

                if amount < Config.MIN_PAYOUT:
                    await update.message.reply_text(f"❌ Минимальная сумма выплаты {Config.MIN_PAYOUT} руб.")
                    return

                stats = self.db.get_user_stats(user.id)
                if amount > stats['available_balance']:
                    await update.message.reply_text("❌ Недостаточно средств для выплаты")
                    return

                payout = self.db.create_payout_request(user.id, amount, payment_method, details)
                if payout:
                    context.user_data.pop('awaiting_payout', None)
                    context.user_data.pop('payment_method', None)

                    await update.message.reply_text(
                        Messages.get_payout_success_text()
                    )

                    try:
                        await context.bot.send_message(
                            chat_id=Config.ADMIN_ID,
                            text=f"🤑 Новая заявка на выплату!\n\n"
                                 f"Пользователь: {user.first_name} (@{user.username})\n"
                                 f"Сумма: {amount} руб.\n"
                                 f"Метод: {payment_method}\n"
                                 f"Реквизиты: {details}",
                            reply_markup=get_payout_management_keyboard(payout.id)
                        )
                    except Exception as e:
                        logging.error(f"Ошибка уведомления админа: {e}")
                else:
                    await update.message.reply_text("❌ Ошибка при создании заявки")

            except ValueError:
                await update.message.reply_text("❌ Неверный формат суммы. Пожалуйста, введите число.")
            except Exception as e:
                logging.error(f"Ошибка обработки выплаты: {e}")
                await update.message.reply_text("❌ Произошла ошибка при обработке запроса")

        # Обработка текста для рассылки
        elif hasattr(context, 'user_data') and context.user_data.get('awaiting_broadcast_text'):
            text = update.message.text
            print(f"📝 Получен текст рассылки: {text[:50]}...")

            # Сохраняем текст
            self.broadcast_data['text'] = text
            context.user_data.pop('awaiting_broadcast_text', None)

            # Получаем количество пользователей
            if self.broadcast_data['recipients'] == 'all':
                users = self.db.get_all_users()
            elif self.broadcast_data['recipients'] == 'signed':
                users = self.db.get_all_users(signed_only=True)
            else:
                users = self.db.get_all_users(signed_only=False)

            self.broadcast_data['users_count'] = len(users)

            print(f"👥 Получателей: {len(users)}")

            await update.message.reply_text(
                f"✅ Текст рассылки сохранен!\n\n"
                f"Получатели: {self.broadcast_data['recipients']}\n"
                f"Количество: {len(users)} пользователей\n\n"
                f"Теперь вы можете начать рассылку.",
                reply_markup=get_broadcast_keyboard()
            )

    async def send_broadcast_message(self, context, user_id, message_text):
        """Отправка сообщения пользователю с обработкой ошибок"""
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text
            )
            print(f"✅ Сообщение отправлено пользователю {user_id}")
            return True
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка отправки пользователю {user_id}: {error_msg}")

            # Логируем разные типы ошибок
            if "Forbidden" in error_msg:
                print(f"   Пользователь {user_id} заблокировал бота")
            elif "Chat not found" in error_msg:
                print(f"   Чат с пользователем {user_id} не найден")
            elif "bot was blocked" in error_msg.lower():
                print(f"   Бот заблокирован пользователем {user_id}")

            return False

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            query = update.callback_query
            await query.answer()

            user = query.from_user
            db_user = self.db.get_user(user.id)

            try:
                if query.data == "about":
                    await self.safe_edit_message(
                        query,
                        Messages.get_about_text(),
                        get_main_menu_keyboard(db_user.signed_agreement if db_user else False)
                    )

                elif query.data == "partnership_info":
                    await self.safe_edit_message(
                        query,
                        Messages.get_partnership_info(),
                        get_main_menu_keyboard(db_user.signed_agreement if db_user else False)
                    )

                elif query.data == "sign_agreement":
                    await self.safe_edit_message(
                        query,
                        Messages.get_agreement_text(),
                        get_agreement_keyboard()
                    )

                elif query.data == "confirm_agreement":
                    if db_user:
                        self.db.sign_agreement(user.id)
                        stmt = select(Referral).where(Referral.referred_id == user.id)
                        referrals = self.db.session.scalars(stmt).all()

                        for referral in referrals:
                            self.db.confirm_referral(referral.referred_id)

                        await self.safe_edit_message(
                            query,
                            "✅ Соглашение успешно подписано! Теперь вам доступен полный функционал бота.",
                            get_main_menu_keyboard(True)
                        )
                    else:
                        await self.safe_edit_message(
                            query,
                            "❌ Ошибка: пользователь не найден",
                            get_main_menu_keyboard(False)
                        )

                elif query.data == "cancel_agreement":
                    await self.safe_edit_message(
                        query,
                        "❌ Вы отказались от подписания соглашения. Без этого доступен только ознакомительный функционал.",
                        get_main_menu_keyboard(False)
                    )

                elif query.data == "stats" and db_user and db_user.signed_agreement:
                    stats = self.db.get_user_stats(user.id)
                    bot_username = (await context.bot.get_me()).username
                    ref_link = f"https://t.me/{bot_username}?start={db_user.referral_link}"

                    stats_text = Messages.get_stats_text(stats, ref_link)
                    await self.safe_edit_message(
                        query,
                        stats_text,
                        get_main_menu_keyboard(True)
                    )

                elif query.data == "referral_link" and db_user and db_user.signed_agreement:
                    bot_username = (await context.bot.get_me()).username
                    ref_link = f"https://t.me/{bot_username}?start={db_user.referral_link}"
                    await self.safe_edit_message(
                        query,
                        f"🔗 *Ваша реферальная ссылка:*\n`{ref_link}`\n\n*Поделитесь этой ссылкой с друзьями и начинайте зарабатывать!* 💰",
                        get_main_menu_keyboard(True)
                    )

                elif query.data == "documents" and db_user and db_user.signed_agreement:
                    await self.safe_edit_message(
                        query,
                        Messages.get_documents_text(),
                        get_main_menu_keyboard(True)
                    )

                elif query.data == "payouts" and db_user and db_user.signed_agreement:
                    stats = self.db.get_user_stats(user.id)
                    payouts_text = Messages.get_payouts_text(stats)
                    await self.safe_edit_message(
                        query,
                        payouts_text,
                        get_payouts_keyboard()
                    )

                elif query.data == "support" and db_user and db_user.signed_agreement:
                    await self.safe_edit_message(
                        query,
                        Messages.get_support_text(),
                        get_main_menu_keyboard(True)
                    )

                elif query.data == "back_to_main":
                    await self.safe_edit_message(
                        query,
                        "Главное меню:",
                        get_main_menu_keyboard(db_user.signed_agreement if db_user else False)
                    )

                elif query.data == "back_to_payouts":
                    stats = self.db.get_user_stats(user.id)
                    payouts_text = Messages.get_payouts_text(stats)
                    await self.safe_edit_message(
                        query,
                        payouts_text,
                        get_payouts_keyboard()
                    )

                elif query.data == "back_to_admin":
                    await self.safe_edit_message(
                        query,
                        "👨‍💻 Панель администратора",
                        get_admin_keyboard()
                    )

                # Обработка выплат
                elif query.data == "request_payout" and db_user and db_user.signed_agreement:
                    stats = self.db.get_user_stats(user.id)
                    if stats['available_balance'] < Config.MIN_PAYOUT:
                        await self.safe_edit_message(
                            query,
                            f"❌ Недостаточно средств для выплаты. Минимальная сумма: {Config.MIN_PAYOUT} руб.\n\n"
                            f"*Доступно:* {stats['available_balance']} руб.",
                            get_payouts_keyboard()
                        )
                    else:
                        await self.safe_edit_message(
                            query,
                            Messages.get_payout_request_text(),
                            get_payment_methods_keyboard()
                        )

                elif query.data == "payout_history" and db_user and db_user.signed_agreement:
                    payouts = self.db.get_user_payouts(user.id)
                    if not payouts:
                        history_text = "*📋 История выплат*\n\nЗаявки на выплаты отсутствуют."
                    else:
                        history_text = "*📋 История выплат*\n\n"
                        for payout in payouts:
                            status_icons = {
                                'pending': '🟡',
                                'approved': '✅',
                                'rejected': '❌',
                                'paid': '💰'
                            }
                            history_text += f"{status_icons.get(payout.status, '⚪')} *{payout.amount} руб.* - {payout.status}\n"
                            history_text += f"*Дата:* {payout.requested_at.strftime('%d.%m.%Y %H:%M')}\n"
                            if payout.processed_at:
                                history_text += f"*Обработано:* {payout.processed_at.strftime('%d.%m.%Y %H:%M')}\n"
                            history_text += "\n"

                    await self.safe_edit_message(
                        query,
                        history_text,
                        get_back_keyboard("back_to_payouts")
                    )

                elif query.data.startswith("method_") and db_user and db_user.signed_agreement:
                    method = query.data.replace("method_", "")
                    context.user_data['awaiting_payout'] = True
                    context.user_data['payment_method'] = method

                    await self.safe_edit_message(
                        query,
                        Messages.get_payout_method_text(method),
                        get_back_keyboard("request_payout")
                    )

                # Админ-функции
                elif query.data == "broadcast" and user.id == Config.ADMIN_ID:
                    await self.safe_edit_message(
                        query,
                        Messages.get_broadcast_start_text(),
                        get_broadcast_keyboard()
                    )

                elif query.data == "admin_stats" and user.id == Config.ADMIN_ID:
                    total_users = self.db.session.scalar(select(func.count(User.id))) or 0
                    signed_users = self.db.session.scalar(
                        select(func.count(User.id)).where(User.signed_agreement == True)) or 0
                    total_referrals = self.db.session.scalar(select(func.count(Referral.id))) or 0

                    pending_payouts_stmt = select(func.sum(Payout.amount)).where(Payout.status == 'pending')
                    pending_payouts = self.db.session.scalar(pending_payouts_stmt) or 0

                    stats_text = Messages.get_admin_stats_text(total_users, signed_users, total_referrals,
                                                               pending_payouts)
                    await self.safe_edit_message(
                        query,
                        stats_text,
                        get_admin_keyboard()
                    )

                elif query.data == "payout_requests" and user.id == Config.ADMIN_ID:
                    pending_payouts = self.db.get_pending_payouts()
                    if not pending_payouts:
                        await self.safe_edit_message(
                            query,
                            "💰 *Заявки на выплаты*\n\nНет ожидающих заявок на выплаты.",
                            get_admin_keyboard()
                        )
                    else:
                        payout_text = "💰 *Заявки на выплаты*\n\n"
                        for payout in pending_payouts:
                            payout_user = self.db.get_user(payout.user_id)
                            username = f"@{payout_user.username}" if payout_user.username else payout_user.first_name
                            payout_text += f"*#{payout.id}* - {payout.amount} руб.\n"
                            payout_text += f"*Пользователь:* {username}\n"
                            payout_text += f"*Метод:* {payout.payment_method}\n"
                            payout_text += f"*Дата:* {payout.requested_at.strftime('%d.%m.%Y %H:%M')}\n"
                            payout_text += f"*Реквизиты:* {payout.details}\n\n"

                        await self.safe_edit_message(
                            query,
                            payout_text,
                            get_admin_keyboard()
                        )

                elif query.data.startswith("approve_") and user.id == Config.ADMIN_ID:
                    payout_id = int(query.data.replace("approve_", ""))
                    payout = self.db.update_payout_status(payout_id, "approved")
                    if payout:
                        # Уведомляем пользователя
                        try:
                            payout_user = self.db.get_user(payout.user_id)
                            await context.bot.send_message(
                                chat_id=payout_user.user_id,
                                text=f"✅ Ваша заявка на выплату #{payout.id} на сумму {payout.amount} руб. одобрена!\n\n"
                                     f"Ожидайте поступления средств в течение 1-3 рабочих дней."
                            )
                        except Exception as e:
                            logging.error(f"Ошибка уведомления пользователя: {e}")

                        await self.safe_edit_message(
                            query,
                            f"✅ Заявка #{payout_id} одобрена! Пользователь уведомлен.",
                            get_admin_keyboard()
                        )

                elif query.data.startswith("reject_") and user.id == Config.ADMIN_ID:
                    payout_id = int(query.data.replace("reject_", ""))
                    payout = self.db.update_payout_status(payout_id, "rejected")
                    if payout:
                        # Уведомляем пользователя
                        try:
                            payout_user = self.db.get_user(payout.user_id)
                            await context.bot.send_message(
                                chat_id=payout_user.user_id,
                                text=f"❌ Ваша заявка на выплату #{payout.id} на сумму {payout.amount} руб. отклонена.\n\n"
                                     f"По вопросам обращайтесь в поддержку."
                            )
                        except Exception as e:
                            logging.error(f"Ошибка уведомления пользователя: {e}")

                        await self.safe_edit_message(
                            query,
                            f"❌ Заявка #{payout_id} отклонена! Пользователь уведомлен.",
                            get_admin_keyboard()
                        )

                # Рассылка - Выбор получателей
                elif query.data == "broadcast_recipients" and user.id == Config.ADMIN_ID:
                    users_all = self.db.get_all_users()
                    users_signed = self.db.get_all_users(signed_only=True)
                    users_unsigned = self.db.get_all_users(signed_only=False)

                    recipients_text = f"""*👥 Выбор получателей*

    *Статистика аудиторий:*
    • 👥 Все пользователи: {len(users_all)} чел.
    • ✅ Подписавшие соглашение: {len(users_signed)} чел.
    • ❌ Неподписавшие: {len(users_unsigned)} чел.

    Выберите аудиторию для рассылки:"""

                    await self.safe_edit_message(
                        query,
                        recipients_text,
                        get_recipients_keyboard()
                    )

                # Выбор типа получателей
                elif query.data.startswith("recipients_") and user.id == Config.ADMIN_ID:
                    recipients_type = query.data.replace("recipients_", "")

                    # Используем атрибут класса вместо глобальной переменной
                    self.broadcast_data['recipients'] = recipients_type

                    # Получаем количество пользователей выбранного типа
                    if recipients_type == 'all':
                        users = self.db.get_all_users()
                    elif recipients_type == 'signed':
                        users = self.db.get_all_users(signed_only=True)
                    else:
                        users = self.db.get_all_users(signed_only=False)

                    self.broadcast_data['users_count'] = len(users)

                    recipients_names = {
                        'all': '👥 Все пользователи',
                        'signed': '✅ Подписавшие соглашение',
                        'unsigned': '❌ Неподписавшие'
                    }

                    await self.safe_edit_message(
                        query,
                        f"✅ Выбраны получатели: *{recipients_names[recipients_type]}*\n\n"
                        f"*Количество:* {len(users)} пользователей\n\n"
                        f"Теперь установите текст рассылки или начните отправку.",
                        get_broadcast_keyboard()
                    )

                # Предпросмотр и подтверждение рассылки
                elif query.data == "broadcast_start" and user.id == Config.ADMIN_ID:
                    # Используем атрибут класса вместо глобальной переменной
                    if not self.broadcast_data['text']:
                        await self.safe_edit_message(
                            query,
                            "❌ Сначала установите текст рассылки!",
                            get_broadcast_keyboard()
                        )
                        return

                    if self.broadcast_data['users_count'] == 0:
                        await self.safe_edit_message(
                            query,
                            "❌ Нет пользователей в выбранной аудитории!",
                            get_broadcast_keyboard()
                        )
                        return

                    preview_text = Messages.get_broadcast_preview_text(
                        self.broadcast_data['text'],
                        self.broadcast_data['recipients'],
                        self.broadcast_data['users_count']
                    )

                    await self.safe_edit_message(
                        query,
                        preview_text,
                        get_broadcast_confirmation_keyboard()
                    )

                    # Подтверждение рассылки
                elif query.data == "broadcast_confirm" and user.id == Config.ADMIN_ID:
                    print("🚀 Начало рассылки...")

                    # Получаем список пользователей
                    if self.broadcast_data['recipients'] == 'all':
                        users = self.db.get_all_users()
                    elif self.broadcast_data['recipients'] == 'signed':
                        users = self.db.get_all_users(signed_only=True)
                    else:
                        users = self.db.get_all_users(signed_only=False)

                    print(f"📊 Найдено пользователей: {len(users)}")

                    if len(users) == 0:
                        await self.safe_edit_message(
                            query,
                            "❌ Нет пользователей для рассылки!",
                            get_broadcast_keyboard()
                        )
                        return

                    sent_count = 0
                    failed_count = 0
                    total_users = len(users)

                    # Создаем сообщение о начале рассылки
                    start_message = await query.message.reply_text(
                        f"🚀 *Начинаем рассылку...*\n\n"
                        f"*Получателей:* {total_users}\n"
                        f"*Тип:* {self.broadcast_data['recipients']}\n"
                        f"*Прогресс:* 0/{total_users} (0%)"
                    )

                    # Отправляем рассылку
                    for index, user_obj in enumerate(users):
                        try:
                            print(f"📨 Отправка {index + 1}/{total_users} пользователю {user_obj.user_id}")

                            success = await self.send_broadcast_message(
                                context,
                                user_obj.user_id,
                                self.broadcast_data['text']
                            )

                            if success:
                                sent_count += 1
                                print(f"   ✅ Успешно")
                            else:
                                failed_count += 1
                                print(f"   ❌ Ошибка")

                            # Обновляем прогресс каждые 5 сообщений или для последнего
                            if (index + 1) % 5 == 0 or (index + 1) == total_users:
                                progress = (sent_count + failed_count) / total_users * 100
                                try:
                                    await context.bot.edit_message_text(
                                        chat_id=start_message.chat_id,
                                        message_id=start_message.message_id,
                                        text=f"📤 *Идет рассылка...*\n\n"
                                             f"*Получателей:* {total_users}\n"
                                             f"*Отправлено:* {sent_count + failed_count}/{total_users}\n"
                                             f"*Успешно:* {sent_count}\n"
                                             f"*Ошибок:* {failed_count}\n"
                                             f"*Прогресс:* {progress:.1f}%"
                                    )
                                except Exception as e:
                                    print(f"Ошибка обновления прогресса: {e}")

                            # Задержка
                            await asyncio.sleep(Config.BROADCAST_DELAY)

                        except Exception as e:
                            print(f"❌ Критическая ошибка при отправке пользователю {user_obj.user_id}: {e}")
                            failed_count += 1

                    # Финальный результат
                    print(f"✅ Рассылка завершена. Успешно: {sent_count}, Ошибок: {failed_count}")

                    # Сохраняем статистику
                    self.db.save_admin_message(user.id, self.broadcast_data['text'], sent_count)

                    # Показываем результат
                    result_text = f"""✅ *Рассылка завершена!*

                📊 *Результаты:*
                👥 Всего получателей: {total_users}
                ✅ Успешно отправлено: {sent_count}
                ❌ Ошибок доставки: {failed_count}
                📈 Эффективность: {(sent_count / total_users * 100) if total_users > 0 else 0:.1f}%"""

                    await context.bot.edit_message_text(
                        chat_id=start_message.chat_id,
                        message_id=start_message.message_id,
                        text=result_text
                    )

                    # Сбрасываем данные
                    self.broadcast_data = {
                        'text': None,
                        'recipients': 'all',
                        'users_count': 0
                    }

                    print("🔄 Данные рассылки сброшены")

                # Отмена рассылки
                elif query.data == "broadcast_cancel" and user.id == Config.ADMIN_ID:
                    await self.safe_edit_message(
                        query,
                        "❌ Рассылка отменена.",
                        get_broadcast_keyboard()
                    )

                # Рассылка - ввод текста
                elif query.data == "broadcast_text" and user.id == Config.ADMIN_ID:
                    context.user_data['awaiting_broadcast_text'] = True
                    await self.safe_edit_message(
                        query,
                        "📝 Введите текст рассылки:\n\nПоддерживается Markdown разметка.",
                        get_back_keyboard("broadcast")
                    )

                    # Отладочная информация о состоянии рассылки
                elif query.data == "debug_broadcast" and user.id == Config.ADMIN_ID:
                    debug_info = f"""*🐞 Отладочная информация рассылки*

                *Текст:* {self.broadcast_data['text']}
                *Получатели:* {self.broadcast_data['recipients']}
                *Количество:* {self.broadcast_data['users_count']}

                *Статистика пользователей:*
                • Всего: {len(self.db.get_all_users())}
                • Подписавшие: {len(self.db.get_all_users(signed_only=True))}
                • Неподписавшие: {len(self.db.get_all_users(signed_only=False))}"""

                    await self.safe_edit_message(
                        query,
                        debug_info,
                        get_admin_keyboard()
                    )

            except Exception as e:
                logging.error(f"Ошибка в обработчике кнопок: {e}")
                await query.message.reply_text("❌ Произошла ошибка. Пожалуйста, попробуйте снова.")

    async def handle_broadcast_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if hasattr(context, 'user_data') and context.user_data.get('awaiting_broadcast_text'):
            text = update.message.text
            print(f"📝 Получен текст рассылки: {text[:50]}...")

            self.broadcast_data['text'] = text
            context.user_data.pop('awaiting_broadcast_text', None)

            if self.broadcast_data['recipients'] == 'all':
                users = self.db.get_all_users()
            elif self.broadcast_data['recipients'] == 'signed':
                users = self.db.get_all_users(signed_only=True)
            else:
                users = self.db.get_all_users(signed_only=False)

            self.broadcast_data['users_count'] = len(users)

            print(f"👥 Получателей: {len(users)}")

            await update.message.reply_text(
                f"✅ Текст рассылки сохранен!\n\n"
                f"Получатели: {self.broadcast_data['recipients']}\n"
                f"Количество: {len(users)} пользователей\n\n"
                f"Теперь вы можете начать рассылку.",
                reply_markup=get_broadcast_keyboard()
            )

    async def send_broadcast_message(self, context, user_id, message_text):
        """Отправка сообщения пользователю с обработкой ошибок"""
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=self.broadcast_data['text'],
            )
            return True
        except Exception as e:
            logging.error(f"Ошибка отправки пользователю {user_id}: {e}")
            return False

def main():
    if not Config.BOT_TOKEN or Config.BOT_TOKEN == 'your_telegram_bot_token':
        print("❌ Ошибка: BOT_TOKEN не настроен!")
        print("Создайте .env файл с содержанием:")
        print("BOT_TOKEN=your_actual_bot_token_here")
        print("ADMIN_ID=your_telegram_id_here")
        print("\n📝 Как получить токен:")
        print("1. Напишите @BotFather в Telegram")
        print("2. Используйте команду /newbot")
        print("3. Скопируйте выданный токен в .env файл")
        return

    if Config.ADMIN_ID == 0:
        print("❌ Ошибка: ADMIN_ID не настроен!")
        print("Укажите ваш Telegram ID в .env файле")
        return

    try:
        bot = PartnerBot(Config.BOT_TOKEN)
        print("🤖 Бот инициализирован...")
        print("✅ Все функции реализованы")
        print("🔗 Запускаем бота...")

        # Простой запуск без сложных retry-механизмов
        bot.application.run_polling()

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        print("🔧 Возможные решения:")
        print("1. Проверьте интернет-соединение")
        print("2. Убедитесь, что BOT_TOKEN корректен")
        print("3. Проверьте настройки прокси (если используете)")


if __name__ == '__main__':
    main()