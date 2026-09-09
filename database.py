# database.py — SQLite + SQLAlchemy (async) ma'lumotlar bazasi moduli
# Yuborilgan yangiliklar ID'larini saqlaydi, takrorlanishni oldini oladi.

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    BigInteger,
    ForeignKey,
    UniqueConstraint,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

logger = logging.getLogger(__name__)


# -------------------------------------------------------
# ORM Modellar
# -------------------------------------------------------

class Base(DeclarativeBase):
    pass


class User(Base):
    """Bot foydalanuvchilari."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    
    # Gamification & Streaks
    points = Column(Integer, default=0)
    streak_days = Column(Integer, default=0)
    last_active_date = Column(DateTime(timezone=True), nullable=True)
    
    # VIP Subscription
    is_vip = Column(Boolean, default=False)
    vip_until = Column(DateTime(timezone=True), nullable=True)
    
    channels = relationship("Channel", back_populates="user", cascade="all, delete-orphan")


class Channel(Base):
    """Foydalanuvchi ulagan Telegram kanallar."""
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(String(255), unique=True, nullable=False, index=True) # @username yoki -100...
    channel_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Sozlamalar (True = yoqilgan)
    setting_news = Column(Boolean, default=True)
    setting_games = Column(Boolean, default=True)
    setting_videos = Column(Boolean, default=True)
    setting_emotional = Column(Boolean, default=True)
    setting_recommendations = Column(Boolean, default=True)
    
    added_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="channels")


class PublishedArticle(Base):
    """Kanalga yuborilgan maqolalar jadvali."""
    __tablename__ = "published_articles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(String(512), nullable=False, index=True)
    channel_id = Column(String(255), nullable=False, index=True) # Qaysi kanalga yuborildi
    title = Column(String(1024), nullable=True)
    source_url = Column(String(512), nullable=True)
    telegram_message_id = Column(Integer, nullable=True)
    published_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    is_sent = Column(Boolean, default=True, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('article_id', 'channel_id', name='uq_article_channel'),
    )

    def __repr__(self) -> str:
        return f"<PublishedArticle id={self.id} article_id='{self.article_id[:40]}...' channel_id='{self.channel_id}'>"


class QuizSession(Base):
    """Faol quiz (viktorina) sessiyasi."""
    __tablename__ = "quiz_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(String(255), nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    current_question_index = Column(Integer, default=1)
    total_questions = Column(Integer, default=5)
    current_correct_option = Column(String(10), nullable=True) # A, B, C yoki D
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    answers = relationship("QuizAnswer", back_populates="session", cascade="all, delete-orphan")


class QuizAnswer(Base):
    """Foydalanuvchilarning quizdagi javoblari."""
    __tablename__ = "quiz_answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("quiz_sessions.id"), nullable=False)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    question_index = Column(Integer, nullable=False)
    is_correct = Column(Boolean, default=False)
    answered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('session_id', 'telegram_id', 'question_index', name='uq_user_answer'),
    )

    session = relationship("QuizSession", back_populates="answers")


class AdCampaign(Base):
    """Reklama postlari va ularni avtomatik o'chirish taymerlari."""
    __tablename__ = "ad_campaigns"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(String(255), nullable=False, index=True)
    message_id = Column(Integer, nullable=False)
    delete_at = Column(DateTime(timezone=True), nullable=False)
    is_deleted = Column(Boolean, default=False)


class Database:
    """
    Asinxron ma'lumotlar bazasi boshqaruvchisi.
    Singleton pattern orqali ishlatiladi.
    """

    def __init__(self, database_url: str) -> None:
        # SQLite faylini saqlash uchun papka yaratish
        if database_url.startswith("sqlite"):
            db_path_str = database_url.replace(
                "sqlite+aiosqlite:///", ""
            ).replace("sqlite:///", "")
            db_path = Path(db_path_str)
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_async_engine(
            database_url,
            echo=False,           # SQL loglarni ko'rish uchun True qiling
            pool_pre_ping=True,
            connect_args={"check_same_thread": False, "timeout": 20}
            if "sqlite" in database_url
            else {},
        )
        
        # SQLite uchun asinxron ulash orqali WAL rejimiga o'tish SQLAlchemy eventlari orqali biroz qiyin bo'lishi mumkin.
        # Buning o'rniga biz aiosqlite parametrlariga tayanamiz va ulanishda tez-tez 'database is locked' ni oldini olish uchun timeout 20s qo'ydik.
        
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Ma'lumotlar bazasi engine yaratildi: %s", database_url)

    async def create_tables(self) -> None:
        """Barcha jadvallarni yaratadi (agar mavjud bo'lmasa)."""
        from sqlalchemy import text
        async with self._engine.begin() as conn:
            # WAL rejimini yoqish (ko'p o'qish/yozishlar tezligi va lock-larni oldini olish uchun)
            if "sqlite" in self._engine.url.drivername:
                await conn.execute(text("PRAGMA journal_mode=WAL;"))
                await conn.execute(text("PRAGMA synchronous=NORMAL;"))
                
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Jadvallar tekshirildi / yaratildi (WAL mode).")

    async def dispose(self) -> None:
        """Engine ulanishlarini yopadi."""
        await self._engine.dispose()
        logger.info("Ma'lumotlar bazasi ulanishlari yopildi.")

    def get_session(self) -> AsyncSession:
        """Yangi asinxron sessiya qaytaradi (context manager sifatida ishlating)."""
        return self._session_factory()

    # -------------------------------------------------------
    # Repository metodlari
    # -------------------------------------------------------

    async def is_article_published(self, article_id: str, channel_id: str) -> bool:
        """Maqola ushbu kanalga yuborilganligini tekshiradi."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(PublishedArticle).where(
                    PublishedArticle.article_id == article_id,
                    PublishedArticle.channel_id == channel_id
                )
            )
            return result.scalar_one_or_none() is not None

    async def save_article(
        self,
        article_id: str,
        channel_id: str,
        title: Optional[str] = None,
        source_url: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        is_sent: bool = True,
    ) -> PublishedArticle:
        """Yangi maqolani bazaga saqlaydi (kanal bo'yicha)."""
        async with self._session_factory() as session:
            async with session.begin():
                existing = await session.execute(
                    select(PublishedArticle).where(
                        PublishedArticle.article_id == article_id,
                        PublishedArticle.channel_id == channel_id
                    )
                )
                record = existing.scalar_one_or_none()
                if record is not None:
                    return record

                new_record = PublishedArticle(
                    article_id=article_id,
                    channel_id=channel_id,
                    title=title,
                    source_url=source_url,
                    telegram_message_id=telegram_message_id,
                    is_sent=is_sent,
                )
                session.add(new_record)
                return new_record

    # --- SaaS xususiyatlari ---

    async def get_or_create_user(self, telegram_id: int, username: Optional[str] = None) -> User:
        """Foydalanuvchini olish yoki yaratish."""
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(select(User).where(User.telegram_id == telegram_id))
                user = result.scalar_one_or_none()
                if not user:
                    user = User(telegram_id=telegram_id, username=username)
                    session.add(user)
                else:
                    if username:
                        user.username = username
                return user

    async def add_channel(self, telegram_id: int, channel_id: str, channel_name: str) -> bool:
        """Foydalanuvchi uchun kanal qo'shish."""
        async with self._session_factory() as session:
            async with session.begin():
                user_res = await session.execute(select(User).where(User.telegram_id == telegram_id))
                user = user_res.scalar_one_or_none()
                if not user:
                    return False
                
                chan_res = await session.execute(select(Channel).where(Channel.channel_id == channel_id))
                channel = chan_res.scalar_one_or_none()
                
                if channel:
                    channel.user_id = user.id
                    channel.channel_name = channel_name
                    channel.is_active = True
                else:
                    channel = Channel(user_id=user.id, channel_id=channel_id, channel_name=channel_name)
                    session.add(channel)
                return True

    async def get_user_channels(self, telegram_id: int) -> list[Channel]:
        """Foydalanuvchining barcha kanallarini olish."""
        async with self._session_factory() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = user_res.scalar_one_or_none()
            if not user:
                return []
            
            res = await session.execute(select(Channel).where(Channel.user_id == user.id))
            return list(res.scalars().all())

    async def update_channel_setting(self, channel_id: str, setting_name: str, value: bool) -> None:
        """Kanal sozlamasini o'zgartirish (setting_news, setting_games, etc.)."""
        async with self._session_factory() as session:
            async with session.begin():
                res = await session.execute(select(Channel).where(Channel.channel_id == channel_id))
                channel = res.scalar_one_or_none()
                if channel and hasattr(channel, setting_name):
                    setattr(channel, setting_name, value)

    async def get_active_channels(self) -> list[Channel]:
        """Tizimdagi barcha faol kanallarni olish (broadcasting uchun)."""
        from sqlalchemy.orm import selectinload
        async with self._session_factory() as session:
            res = await session.execute(select(Channel).options(selectinload(Channel.user)).where(Channel.is_active == True))
            return list(res.scalars().all())

    async def get_published_count(self) -> int:
        """Jami yuborilgan maqolalar sonini qaytaradi."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(PublishedArticle).where(PublishedArticle.is_sent == True)
            )
            return len(result.scalars().all())

    # --- Quiz (O'yin) Metodlari ---

    async def get_active_quiz_session(self, channel_id: str) -> Optional[QuizSession]:
        """Kanal uchun faol quiz sessiyasini qaytaradi."""
        async with self._session_factory() as session:
            res = await session.execute(
                select(QuizSession).where(
                    QuizSession.channel_id == channel_id,
                    QuizSession.is_active == True
                )
            )
            return res.scalar_one_or_none()

    async def create_quiz_session(self, channel_id: str, total_questions: int = 5) -> QuizSession:
        """Yangi quiz sessiyasini yaratadi va eskisini nofaol qiladi."""
        async with self._session_factory() as session:
            async with session.begin():
                # Eskilarini yopish
                await session.execute(
                    select(QuizSession).where(
                        QuizSession.channel_id == channel_id,
                        QuizSession.is_active == True
                    )
                )
                # update cannot be used easily with scalar, so let's do it ORM way
                res = await session.execute(select(QuizSession).where(QuizSession.channel_id == channel_id, QuizSession.is_active == True))
                for old_sess in res.scalars():
                    old_sess.is_active = False

                new_session = QuizSession(channel_id=channel_id, total_questions=total_questions)
                session.add(new_session)
                await session.flush()
                return new_session

    async def update_quiz_session(self, session_id: int, current_question_index: int, correct_option: str, is_active: bool = True) -> None:
        """Quiz sessiyasi holatini yangilash (yangi savolga o'tganda)."""
        async with self._session_factory() as session:
            async with session.begin():
                res = await session.execute(select(QuizSession).where(QuizSession.id == session_id))
                quiz_sess = res.scalar_one_or_none()
                if quiz_sess:
                    quiz_sess.current_question_index = current_question_index
                    quiz_sess.current_correct_option = correct_option
                    quiz_sess.is_active = is_active

    async def record_quiz_answer(self, session_id: int, telegram_id: int, username: str, question_index: int, is_correct: bool) -> bool:
        """Foydalanuvchi javobini qayd etish. Agar allaqachon javob bergan bo'lsa False qaytaradi."""
        async with self._session_factory() as session:
            async with session.begin():
                # Tekshirish
                res = await session.execute(
                    select(QuizAnswer).where(
                        QuizAnswer.session_id == session_id,
                        QuizAnswer.telegram_id == telegram_id,
                        QuizAnswer.question_index == question_index
                    )
                )
                if res.scalar_one_or_none():
                    return False # Allaqachon javob bergan

                new_answer = QuizAnswer(
                    session_id=session_id,
                    telegram_id=telegram_id,
                    username=username,
                    question_index=question_index,
                    is_correct=is_correct
                )
                session.add(new_answer)
                return True

    async def get_quiz_leaderboard(self, session_id: int) -> list[tuple[str, int]]:
        """Sessiya uchun reytingni qaytaradi: [(username, score), ...]"""
        from sqlalchemy import func
        async with self._session_factory() as session:
            # sum(is_correct) xuddi count(is_correct == True) kabi
            stmt = (
                select(QuizAnswer.username, func.sum(func.cast(QuizAnswer.is_correct, Integer)).label("score"))
                .where(QuizAnswer.session_id == session_id)
                .group_by(QuizAnswer.telegram_id, QuizAnswer.username)
                .order_by(func.sum(func.cast(QuizAnswer.is_correct, Integer)).desc())
                .limit(10)
            )
            res = await session.execute(stmt)
            
            leaderboard = []
            for row in res.all():
                username = row[0] or "Foydalanuvchi"
                score = row[1] or 0
                leaderboard.append((username, score))
            return leaderboard

    # --- SMM, Gamification, Ads, VIP Methods ---

    async def update_user_streak(self, telegram_id: int) -> int:
        """Update daily streak for a user and return the new streak."""
        from datetime import datetime, timezone, timedelta
        async with self._session_factory() as session:
            async with session.begin():
                res = await session.execute(select(User).where(User.telegram_id == telegram_id))
                user = res.scalar_one_or_none()
                if not user:
                    return 0
                now = datetime.now(timezone.utc)
                if user.last_active_date:
                    delta = now.date() - user.last_active_date.date()
                    if delta == timedelta(days=1):
                        user.streak_days += 1
                    elif delta > timedelta(days=1):
                        user.streak_days = 1
                    # if delta == 0, streak remains same
                else:
                    user.streak_days = 1
                user.last_active_date = now
                user.points += 10 # 10 points for daily activity
                return user.streak_days

    async def add_user_points(self, telegram_id: int, points: int) -> None:
        """Add gamification points to user."""
        async with self._session_factory() as session:
            async with session.begin():
                res = await session.execute(select(User).where(User.telegram_id == telegram_id))
                user = res.scalar_one_or_none()
                if user:
                    user.points += points

    async def get_global_leaderboard(self) -> list[User]:
        """Get top 10 users globally by points."""
        async with self._session_factory() as session:
            res = await session.execute(select(User).order_by(User.points.desc()).limit(10))
            return list(res.scalars().all())

    async def set_user_vip(self, telegram_id: int, days: int) -> None:
        """Grant VIP status for N days."""
        from datetime import datetime, timezone, timedelta
        async with self._session_factory() as session:
            async with session.begin():
                res = await session.execute(select(User).where(User.telegram_id == telegram_id))
                user = res.scalar_one_or_none()
                if user:
                    user.is_vip = True
                    user.vip_until = datetime.now(timezone.utc) + timedelta(days=days)

    async def check_user_vip(self, telegram_id: int) -> bool:
        """Check if user has active VIP status."""
        from datetime import datetime, timezone
        async with self._session_factory() as session:
            res = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = res.scalar_one_or_none()
            if not user or not user.is_vip:
                return False
            if user.vip_until and user.vip_until < datetime.now(timezone.utc):
                return False
            return True

    async def get_expired_vips(self) -> list[User]:
        """Get list of users whose VIP has expired."""
        from datetime import datetime, timezone
        async with self._session_factory() as session:
            res = await session.execute(
                select(User).where(User.is_vip == True, User.vip_until < datetime.now(timezone.utc))
            )
            return list(res.scalars().all())

    async def remove_vip(self, telegram_id: int) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                res = await session.execute(select(User).where(User.telegram_id == telegram_id))
                user = res.scalar_one_or_none()
                if user:
                    user.is_vip = False
                    user.vip_until = None

    async def add_ad_campaign(self, channel_id: str, message_id: int, delete_at: datetime) -> None:
        """Record an ad campaign for auto-deletion."""
        async with self._session_factory() as session:
            async with session.begin():
                new_ad = AdCampaign(channel_id=channel_id, message_id=message_id, delete_at=delete_at)
                session.add(new_ad)

    async def get_pending_ads_to_delete(self) -> list[AdCampaign]:
        """Get ads that should be deleted now."""
        from datetime import datetime, timezone
        async with self._session_factory() as session:
            res = await session.execute(
                select(AdCampaign).where(
                    AdCampaign.is_deleted == False,
                    AdCampaign.delete_at <= datetime.now(timezone.utc)
                )
            )
            return list(res.scalars().all())

    async def mark_ad_deleted(self, ad_id: int) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                res = await session.execute(select(AdCampaign).where(AdCampaign.id == ad_id))
                ad = res.scalar_one_or_none()
                if ad:
                    ad.is_deleted = True

