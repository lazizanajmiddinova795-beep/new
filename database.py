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
            connect_args={"check_same_thread": False}
            if "sqlite" in database_url
            else {},
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Ma'lumotlar bazasi engine yaratildi: %s", database_url)

    async def create_tables(self) -> None:
        """Barcha jadvallarni yaratadi (agar mavjud bo'lmasa)."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Jadvallar tekshirildi / yaratildi.")

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
        async with self._session_factory() as session:
            res = await session.execute(select(Channel).where(Channel.is_active == True))
            return list(res.scalars().all())

    async def get_published_count(self) -> int:
        """Jami yuborilgan maqolalar sonini qaytaradi."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(PublishedArticle).where(PublishedArticle.is_sent == True)
            )
            return len(result.scalars().all())
