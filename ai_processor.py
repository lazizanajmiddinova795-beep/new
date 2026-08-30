# ai_processor.py — AI qayta ishlash moduli
# OpenAI yoki Anthropic API orqali maqolalarni O'zbek tilida rewrite qiladi.
# Telegram kanal formati uchun moslab emoji, bold tekst va xulosa qo'shadi.

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from fetcher import ArticleItem

logger = logging.getLogger(__name__)


# -------------------------------------------------------
# Prompt shabloni
# -------------------------------------------------------

SYSTEM_PROMPT = """Siz professional O'zbek tili texnologiya yangiliklari muxbirirasiz.
Sizning vazifangiz — berilgan inglizcha (yoki boshqa tildagi) yangilikni 
Telegram kanal uchun O'zbek tilida chiroyli, qiziqarli va tushunarli qilib qayta yozish.

QOIDALAR:
1. Post faqat O'zbek tilida bo'lsin.
2. Sarlavha kuchli va qiziqarli bo'lsin (emoji bilan boshlang).
3. Matn 3-5 jumladan iborat bo'lsin — qisqa, ammo informatsion.
4. Muhim so'zlarni **bold** (**matn**) formatida yozing.
5. Postni xulosa jumlasi bilan yakunlang.
6. Hech qanday HTML tegi ishlatmang, faqat Telegram Markdown (MarkdownV2 emas, oddiy Markdown).
7. Hech qanday havolani matnga qo'shmang — havola inline-button orqali beriladi.
8. Postni #xeshteg bilan tugatmang — ular alohida qo'shiladi.

CHIQISH FORMATI (faqat shu formatda, boshqa hech narsa yo'q):
<sarlavha_emoji> **[Sarlavha]**

[3-5 jumlali matn]

💡 **Xulosa:** [1 jumlali xulosa]"""

USER_PROMPT_TEMPLATE = """Quyidagi yangilikni qayta yozing:

Sarlavha: {title}

Matn: {summary}

Manba: {source_name}"""


@dataclass
class ProcessedPost:
    """AI tomonidan qayta ishlangan post."""
    text: str                    # Asosiy matn (Markdown)
    source_url: str              # Inline button uchun havola
    hashtags: list               # Xesh-teglar ro'yxati
    article_id: str              # Maqola unikal ID


def _build_final_post(ai_text: str, article: ArticleItem) -> str:
    """
    AI matniga xesh-teglarni qo'shib yakuniy post shakllantiradi.
    Telegram MarkdownV2 emas, oddiy Markdown ishlatiladi.
    """
    hashtag_line = " ".join(article.hashtags) if article.hashtags else ""

    parts = [ai_text.strip()]
    if hashtag_line:
        parts.append(f"\n{hashtag_line}")

    return "\n".join(parts)


# -------------------------------------------------------
# OpenAI Provider
# -------------------------------------------------------

class OpenAIProcessor:
    """OpenAI API orqali maqolalarni qayta ishlaydi."""

    def __init__(self, api_key: str, model: str) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai paketi o'rnatilmagan. "
                "Iltimos: pip install openai"
            )
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        logger.info("OpenAI processor tayyor. Model: %s", model)

    async def process(self, article: ArticleItem) -> Optional[str]:
        """
        Maqolani OpenAI GPT orqali O'zbek tilida rewrite qiladi.
        Muvaffaqiyatsiz bo'lsa None qaytaradi.
        """
        user_message = USER_PROMPT_TEMPLATE.format(
            title=article.title,
            summary=article.summary or "Matn mavjud emas",
            source_name=article.source_name,
        )

        for attempt in range(1, 4):  # 3 marta urinish
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=600,
                    temperature=0.7,
                )
                content = response.choices[0].message.content
                if content:
                    return content.strip()
                logger.warning(
                    "OpenAI bo'sh javob qaytardi. Urinish: %d", attempt
                )
            except Exception as e:
                logger.warning(
                    "OpenAI xato (urinish %d/3): %s", attempt, e
                )
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        logger.error(
            "OpenAI 3 marta urinishdan keyin ham muvaffaqiyatsiz: %s",
            article.title[:60],
        )
        return None

    async def generate_custom_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Custom text generation with OpenAI."""
        for attempt in range(1, 4):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=800,
                    temperature=0.7,
                )
                content = response.choices[0].message.content
                if content:
                    return content.strip()
            except Exception as e:
                logger.warning("OpenAI custom xato (urinish %d/3): %s", attempt, e)
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)
        return None


# -------------------------------------------------------
# Anthropic Provider
# -------------------------------------------------------

class AnthropicProcessor:
    """Anthropic Claude API orqali maqolalarni qayta ishlaydi."""

    def __init__(self, api_key: str, model: str) -> None:
        try:
            import anthropic as anthropic_sdk
            self._anthropic_sdk = anthropic_sdk
        except ImportError:
            raise ImportError(
                "anthropic paketi o'rnatilmagan. "
                "Iltimos: pip install anthropic"
            )
        self._client = anthropic_sdk.AsyncAnthropic(api_key=api_key)
        self._model = model
        logger.info("Anthropic processor tayyor. Model: %s", model)

    async def process(self, article: ArticleItem) -> Optional[str]:
        """
        Maqolani Anthropic Claude orqali O'zbek tilida rewrite qiladi.
        Muvaffaqiyatsiz bo'lsa None qaytaradi.
        """
        user_message = USER_PROMPT_TEMPLATE.format(
            title=article.title,
            summary=article.summary or "Matn mavjud emas",
            source_name=article.source_name,
        )

        for attempt in range(1, 4):
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=600,
                    system=SYSTEM_PROMPT,
                    messages=[
                        {"role": "user", "content": user_message},
                    ],
                )
                content = response.content[0].text if response.content else None
                if content:
                    return content.strip()
                logger.warning(
                    "Anthropic bo'sh javob qaytardi. Urinish: %d", attempt
                )
            except Exception as e:
                logger.warning(
                    "Anthropic xato (urinish %d/3): %s", attempt, e
                )
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

        logger.error(
            "Anthropic 3 marta urinishdan keyin ham muvaffaqiyatsiz: %s",
            article.title[:60],
        )
        return None

    async def generate_custom_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Custom text generation with Anthropic."""
        for attempt in range(1, 4):
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=800,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt},
                    ],
                )
                content = response.content[0].text if response.content else None
                if content:
                    return content.strip()
            except Exception as e:
                logger.warning("Anthropic custom xato (urinish %d/3): %s", attempt, e)
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)
        return None



# -------------------------------------------------------
# Gemini Provider
# -------------------------------------------------------

class GeminiProcessor:
    """Google Gemini API orqali maqolalarni qayta ishlaydi."""

    def __init__(self, api_key: str, model: str) -> None:
        try:
            import google.generativeai as genai
            self._genai = genai
        except ImportError:
            raise ImportError(
                "google-generativeai paketi o'rnatilmagan. "
                "Iltimos: pip install google-generativeai"
            )
        genai.configure(api_key=api_key)
        self._model_name = model
        self._model = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM_PROMPT,
        )
        logger.info("Gemini processor tayyor. Model: %s", model)

    async def process(self, article: ArticleItem) -> Optional[str]:
        """
        Maqolani Google Gemini orqali O'zbek tilida rewrite qiladi.
        Muvaffaqiyatsiz bo'lsa None qaytaradi.
        """
        user_message = USER_PROMPT_TEMPLATE.format(
            title=article.title,
            summary=article.summary or "Matn mavjud emas",
            source_name=article.source_name,
        )

        for attempt in range(1, 4):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._model.generate_content(user_message),
                )
                content = response.text if response.text else None
                if content:
                    return content.strip()
                logger.warning(
                    "Gemini bo'sh javob qaytardi. Urinish: %d", attempt
                )
            except Exception as e:
                logger.warning(
                    "Gemini xato (urinish %d/3): %s", attempt, e
                )
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

        logger.error(
            "Gemini 3 marta urinishdan keyin ham muvaffaqiyatsiz: %s",
            article.title[:60],
        )
        return None

    async def generate_custom_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Custom text generation with Gemini."""
        custom_model = self._genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_prompt,
        )
        for attempt in range(1, 4):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: custom_model.generate_content(user_prompt),
                )
                content = response.text if response.text else None
                if content:
                    return content.strip()
            except Exception as e:
                logger.warning("Gemini custom xato (urinish %d/3): %s", attempt, e)
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)
        return None


# -------------------------------------------------------
# Asosiy Processor (facade)
# -------------------------------------------------------

class AIProcessor:
    """
    AI provider tanlovi va post formatlashtirish uchun yagona interfeys.
    Config asosida OpenAI, Anthropic yoki Gemini ishlatadi.
    """

    def __init__(self, config) -> None:
        self._config = config

        if config.ai_provider == "openai":
            self._provider = OpenAIProcessor(
                api_key=config.openai_api_key,
                model=config.openai_model,
            )
        elif config.ai_provider == "anthropic":
            self._provider = AnthropicProcessor(
                api_key=config.anthropic_api_key,
                model=config.anthropic_model,
            )
        elif config.ai_provider == "gemini":
            self._provider = GeminiProcessor(
                api_key=config.gemini_api_key,
                model=config.gemini_model,
            )
        else:
            raise ValueError(f"Noma'lum AI provider: {config.ai_provider}")

    async def process_article(
        self, article: ArticleItem
    ) -> Optional[ProcessedPost]:
        """
        Maqolani AI orqali qayta ishlaydi va tayyor PostData qaytaradi.
        Muvaffaqiyatsiz bo'lsa None qaytaradi.
        """
        logger.info(
            "AI qayta ishlamoqda: '%s'", article.title[:70]
        )

        ai_text = await self._provider.process(article)
        if not ai_text:
            logger.error(
                "AI maqolani qayta ishlay olmadi: %s", article.title[:60]
            )
            return None

        final_text = _build_final_post(ai_text, article)

        return ProcessedPost(
            text=final_text,
            source_url=article.url,
            hashtags=article.hashtags,
            article_id=article.article_id,
        )

    async def generate_custom_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Generates custom text using the configured AI provider."""
        return await self._provider.generate_custom_text(system_prompt, user_prompt)
