from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_menu_keyboard(signed_agreement=False):
    if not signed_agreement:
        keyboard = [
            [InlineKeyboardButton("📋 О нас", callback_data="about")],
            [InlineKeyboardButton("💼 О партнёрке", callback_data="partnership_info")],
            [InlineKeyboardButton("📝 Подписать соглашение", callback_data="sign_agreement")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="stats"),
             InlineKeyboardButton("🔗 Реферальная ссылка", callback_data="referral_link")],
            [InlineKeyboardButton("📄 Документы", callback_data="documents"),
             InlineKeyboardButton("💰 Выплаты", callback_data="payouts")],
            [InlineKeyboardButton("🆘 Поддержка", callback_data="support")]
        ]
    return InlineKeyboardMarkup(keyboard)

def get_agreement_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Подписать соглашение", callback_data="confirm_agreement")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="cancel_agreement")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton("📈 Общая статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("💰 Заявки на выплаты", callback_data="payout_requests")],
        [InlineKeyboardButton("🐞 Отладка рассылки", callback_data="debug_broadcast")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payouts_keyboard():
    keyboard = [
        [InlineKeyboardButton("💳 Запросить выплату", callback_data="request_payout")],
        [InlineKeyboardButton("📋 История выплат", callback_data="payout_history")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payment_methods_keyboard():
    keyboard = [
        [InlineKeyboardButton("💳 Банковская карта", callback_data="method_card")],
        [InlineKeyboardButton("🥝 Qiwi", callback_data="method_qiwi")],
        [InlineKeyboardButton("💰 ЮMoney", callback_data="method_yoomoney")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_payouts")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_broadcast_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Текст рассылки", callback_data="broadcast_text")],
        [InlineKeyboardButton("👥 Получатели", callback_data="broadcast_recipients")],
        [InlineKeyboardButton("🚀 Начать рассылку", callback_data="broadcast_start")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_recipients_keyboard():
    keyboard = [
        [InlineKeyboardButton("👥 Все пользователи", callback_data="recipients_all")],
        [InlineKeyboardButton("✅ Подписавшие соглашение", callback_data="recipients_signed")],
        [InlineKeyboardButton("❌ Неподписавшие", callback_data="recipients_unsigned")],
        [InlineKeyboardButton("🔙 Назад", callback_data="broadcast")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_broadcast_confirmation_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Отменить", callback_data="broadcast_cancel")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="broadcast")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard(target):
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data=target)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payout_management_keyboard(payout_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{payout_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{payout_id}")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)