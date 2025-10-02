from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from datetime import datetime
import secrets
import logging

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    referral_link = Column(String(50), unique=True)
    signed_agreement = Column(Boolean, default=False)
    signed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)

class Referral(Base):
    __tablename__ = 'referrals'

    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, nullable=False)
    referred_id = Column(Integer, nullable=False)
    confirmed = Column(Boolean, default=False)
    registered_at = Column(DateTime, default=datetime.now)
    confirmed_at = Column(DateTime)

class Payout(Base):
    __tablename__ = 'payouts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(20), default='pending')  # pending, approved, rejected, paid
    requested_at = Column(DateTime, default=datetime.now)
    processed_at = Column(DateTime)
    payment_method = Column(String(50))
    details = Column(Text)

class AdminMessage(Base):
    __tablename__ = 'admin_messages'

    id = Column(Integer, primary_key=True)
    message_text = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.now)
    sent_by = Column(Integer, nullable=False)
    recipients_count = Column(Integer, default=0)

class Database:
    def __init__(self, db_url='sqlite:///partner_bot.db'):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def get_user(self, user_id):
        try:
            stmt = select(User).where(User.user_id == user_id)
            return self.session.scalar(stmt)
        except Exception as e:
            logging.error(f"Error getting user {user_id}: {e}")
            return None

    def create_user(self, user_data):
        try:
            user = User(
                user_id=user_data.id,
                username=user_data.username,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                referral_link=f"ref_{user_data.id}_{secrets.token_hex(8)}"
            )
            self.session.add(user)
            self.session.commit()
            return user
        except Exception as e:
            logging.error(f"Error creating user: {e}")
            self.session.rollback()
            return None

    def sign_agreement(self, user_id):
        try:
            user = self.get_user(user_id)
            if user:
                user.signed_agreement = True
                user.signed_at = datetime.now()
                self.session.commit()
            return user
        except Exception as e:
            logging.error(f"Error signing agreement for {user_id}: {e}")
            self.session.rollback()
            return None

    def add_referral(self, referrer_id, referred_id):
        try:
            # Проверяем, нет ли уже такой записи
            existing = self.session.scalar(
                select(Referral).where(
                    Referral.referrer_id == referrer_id,
                    Referral.referred_id == referred_id
                )
            )
            if existing:
                return existing

            referral = Referral(referrer_id=referrer_id, referred_id=referred_id)
            self.session.add(referral)
            self.session.commit()
            return referral
        except Exception as e:
            logging.error(f"Error adding referral: {e}")
            self.session.rollback()
            return None

    def confirm_referral(self, referred_id):
        try:
            stmt = select(Referral).where(Referral.referred_id == referred_id)
            referral = self.session.scalar(stmt)
            if referral:
                referral.confirmed = True
                referral.confirmed_at = datetime.now()
                self.session.commit()
            return referral
        except Exception as e:
            logging.error(f"Error confirming referral {referred_id}: {e}")
            self.session.rollback()
            return None

    def get_user_stats(self, user_id):
        try:
            # Всего рефералов
            total_stmt = select(func.count(Referral.id)).where(Referral.referrer_id == user_id)
            total_referrals = self.session.scalar(total_stmt) or 0

            # Подтвержденные рефералы
            confirmed_stmt = select(func.count(Referral.id)).where(
                Referral.referrer_id == user_id,
                Referral.confirmed == True
            )
            confirmed_referrals = self.session.scalar(confirmed_stmt) or 0

            # Расчет дохода
            from config import Config
            total_income = confirmed_referrals * Config.REFERRAL_BONUS

            # Ожидающие выплаты
            pending_payouts_stmt = select(func.sum(Payout.amount)).where(
                Payout.user_id == user_id,
                Payout.status == 'pending'
            )
            pending_payouts = self.session.scalar(pending_payouts_stmt) or 0

            # Выплаченные средства
            paid_payouts_stmt = select(func.sum(Payout.amount)).where(
                Payout.user_id == user_id,
                Payout.status.in_(['approved', 'paid'])
            )
            paid_payouts = self.session.scalar(paid_payouts_stmt) or 0

            # Доступно для вывода
            available_balance = total_income - paid_payouts - pending_payouts

            return {
                'total': total_referrals,
                'confirmed': confirmed_referrals,
                'active': confirmed_referrals,  # Можно добавить логику активности
                'pending': total_referrals - confirmed_referrals,
                'total_income': total_income,
                'available_balance': max(available_balance, 0),
                'pending_payouts': pending_payouts,
                'paid_payouts': paid_payouts
            }
        except Exception as e:
            logging.error(f"Error getting stats for {user_id}: {e}")
            return {'total': 0, 'confirmed': 0, 'active': 0, 'pending': 0, 'total_income': 0, 'available_balance': 0, 'pending_payouts': 0, 'paid_payouts': 0}

    def get_user_by_referral_link(self, referral_link):
        try:
            stmt = select(User).where(User.referral_link == referral_link)
            return self.session.scalar(stmt)
        except Exception as e:
            logging.error(f"Error getting user by referral link: {e}")
            return None

    def create_payout_request(self, user_id, amount, payment_method, details=""):
        try:
            payout = Payout(
                user_id=user_id,
                amount=amount,
                payment_method=payment_method,
                details=details
            )
            self.session.add(payout)
            self.session.commit()
            return payout
        except Exception as e:
            logging.error(f"Error creating payout request: {e}")
            self.session.rollback()
            return None

    def get_user_payouts(self, user_id):
        try:
            stmt = select(Payout).where(Payout.user_id == user_id).order_by(Payout.requested_at.desc())
            return list(self.session.scalars(stmt))
        except Exception as e:
            logging.error(f"Error getting payouts for {user_id}: {e}")
            return []

    def get_pending_payouts(self):
        try:
            stmt = select(Payout).where(Payout.status == 'pending').order_by(Payout.requested_at)
            return list(self.session.scalars(stmt))
        except Exception as e:
            logging.error(f"Error getting pending payouts: {e}")
            return []

    def update_payout_status(self, payout_id, status):
        try:
            payout = self.session.get(Payout, payout_id)
            if payout:
                payout.status = status
                payout.processed_at = datetime.now()
                self.session.commit()
            return payout
        except Exception as e:
            logging.error(f"Error updating payout status: {e}")
            self.session.rollback()
            return None

    def get_all_users(self, signed_only=False):
        try:
            stmt = select(User)
            if signed_only:
                stmt = stmt.where(User.signed_agreement == True)
            return list(self.session.scalars(stmt))
        except Exception as e:
            logging.error(f"Error getting users: {e}")
            return []

    def save_admin_message(self, admin_id, message_text, recipients_count):
        try:
            message = AdminMessage(
                sent_by=admin_id,
                message_text=message_text,
                recipients_count=recipients_count
            )
            self.session.add(message)
            self.session.commit()
            return message
        except Exception as e:
            logging.error(f"Error saving admin message: {e}")
            self.session.rollback()
            return None