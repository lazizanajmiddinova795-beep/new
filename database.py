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
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


# -------------------------------------------------------
# ORM Modellar
# -------------------------------------------------------

class Base(DeclarativeBase):
    pass


class PublishedArticle(Base):
    """Kanalga yuborilgan maqolalar jadvali."""

    __tablename__ = "published_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # RSS maqola unikal identifikatori (entry.id yoki URL)
    article_id = Column(String(512), unique=True, nullable=False, index=True)

    # Maqola sarlavhasi (log va debug uchun)
    title = Column(String(1024), nullable=True)

    # Qaysi RSS manbadan kelganligi
    source_url = Column(String(512), nullable=True)

    # Telegram Message ID (kelajakda edit/delete uchun)
    telegram_message_id = Column(Integer, nullable=True)

    # Yuborilgan sana
    published_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Muvaffaqiyatli yuborilganligi
    is_sent = Column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<PublishedArticle id={self.id} "
            f"article_id='{self.article_id[:40]}...' "
            f"is_sent={self.is_sent}>"
        )


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

    async def is_article_published(self, article_id: str) -> bool:
        """
        Maqola allaqachon bazada bor-yo'qligini tekshiradi.
        True → bazada bor (o'tkazib yuborish kerak).
        False → yangi maqola.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(PublishedArticle).where(
                    PublishedArticle.article_id == article_id
                )
            )
            return result.scalar_one_or_none() is not None

    async def save_article(
        self,
        article_id: str,
        title: Optional[str] = None,
        source_url: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        is_sent: bool = True,
    ) -> PublishedArticle:
        """
        Yangi maqolani bazaga saqlaydi.
        Agar article_id allaqachon mavjud bo'lsa, xato chiqmaydi.
        """
        async with self._session_factory() as session:
            async with session.begin():
                # Ikki marta saqlashni oldini olish
                existing = await session.execute(
                    select(PublishedArticle).where(
                        PublishedArticle.article_id == article_id
                    )
                )
                record = existing.scalar_one_or_none()
                if record is not None:
                    logger.debug(
                        "Maqola allaqachon bazada: %s", article_id[:60]
                    )
                    return record

                new_record = PublishedArticle(
                    article_id=article_id,
                    title=title,
                    source_url=source_url,
                    telegram_message_id=telegram_message_id,
                    is_sent=is_sent,
                    published_at=datetime.now(timezone.utc),
                )
                session.add(new_record)

        logger.debug("Maqola bazaga saqlandi: %s", article_id[:60])
        return new_record

    async def get_published_count(self) -> int:
        """Jami yuborilgan maqolalar sonini qaytaradi."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(PublishedArticle).where(PublishedArticle.is_sent == True)
            )
            return len(result.scalars().all())
