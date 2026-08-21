# 🤖 NLMINI_12 Auto-Posting Bot

**t.me/NLMINI_12** kanaliga texnologiya yangilikları avtomatik ravishda yuboradigan professional Telegram boti.

## ✨ Imkoniyatlar

- 📡 **RSS Yig'ish** — BBC, Reuters, TechCrunch, The Verge va boshqa manbalardan yangiliklar
- 🤖 **AI Rewrite** — OpenAI GPT yoki Anthropic Claude orqali O'zbek tiliga tarjima + chiroyli format
- 🚫 **Dedup** — SQLite bazasi orqali takroriy postlarni oldini olish
- ⏰ **Scheduler** — Har 30 daqiqada avtomatik tekshirish
- 🔗 **Inline Button** — Manba havolasi tugmasi
- 📊 **Logging** — Konsol + aylanuvchi fayl loglari
- 🛡️ **Fail-Safe** — Rate Limit, network xatolari, AI xatolariga chidamli

---

## 🚀 O'rnatish

### 1. Repozitoriyni klonlash

```bash
git clone <repo-url>
cd bot
```

### 2. Virtual muhit yaratish

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Kutubxonalarni o'rnatish

```bash
pip install -r requirements.txt
```

### 4. Muhit o'zgaruvchilarini sozlash

```bash
# .env.example ni nusxalash
copy .env.example .env     # Windows
# yoki
cp .env.example .env       # Linux/macOS
```

`.env` faylini ochib quyidagi qiymatlarni kiriting:

```dotenv
BOT_TOKEN=1234567890:AAF...your_token
CHANNEL_ID=@NLMINI_12
OPENAI_API_KEY=sk-...your_key
AI_PROVIDER=openai
```

### 5. Botni kanalga admin sifatida qo'shish

1. Kanalga kiring → **Admins** → **Add Admin**
2. Botingizni qidiring va qo'shing
3. **"Post Messages"** ruxsatini bering

### 6. Ishga tushirish

```bash
python main.py
```

---

## 📁 Loyiha tuzilmasi

```
bot/
├── main.py           # Asosiy kirish nuqtasi
├── config.py         # Konfiguratsiya va RSS manbalar
├── database.py       # SQLite + SQLAlchemy (async)
├── fetcher.py        # RSS yangiliklar yig'uvchi
├── ai_processor.py   # OpenAI / Anthropic qayta ishlash
├── scheduler.py      # APScheduler + posting pipeline
├── requirements.txt  # Kutubxonalar
├── .env.example      # Muhit o'zgaruvchilari namunasi
├── .env              # (Siz yaratasiz, git ga kirmaydi!)
├── data/             # SQLite baza fayli (auto-yaratiladi)
└── logs/             # Log fayllar (auto-yaratiladi)
```

---

## ⚙️ Sozlamalar

| O'zgaruvchi | Default | Tavsif |
|---|---|---|
| `BOT_TOKEN` | — | **Majburiy**. @BotFather dan |
| `CHANNEL_ID` | `@NLMINI_12` | Kanal username yoki ID |
| `AI_PROVIDER` | `openai` | `openai` yoki `anthropic` |
| `OPENAI_API_KEY` | — | OpenAI API kaliti |
| `OPENAI_MODEL` | `gpt-4o-mini` | GPT modeli |
| `ANTHROPIC_API_KEY` | — | Claude API kaliti |
| `ANTHROPIC_MODEL` | `claude-3-5-haiku-20241022` | Claude modeli |
| `FETCH_INTERVAL_MINUTES` | `30` | RSS tekshirish oralig'i |
| `POST_DELAY_SECONDS` | `5` | Postlar orasidagi kechikish |
| `MAX_POSTS_PER_CYCLE` | `5` | Bir siklda max post soni |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` |

---

## 📡 RSS Manbalar Qo'shish

`config.py` faylidagi `RSS_FEEDS` ro'yxatiga qo'shing:

```python
{
    "url": "https://example.com/feed.xml",
    "category": "texnologiya",
    "hashtags": ["#texnologiya", "#yangiliklar"],
},
```

---

## 🔧 Xatolikni bartaraf etish

| Muammo | Yechim |
|---|---|
| `Bot kanalga kirishiga ruxsat yo'q` | Botni kanal admin qilib qo'shing |
| `OPENAI_API_KEY topilmadi` | `.env` faylini tekshiring |
| `Rate Limit` | `POST_DELAY_SECONDS` ni oshiring |
| `Markdown parse error` | Post plain text bilan qayta yuboriladi |

---

## 📄 Litsenziya

MIT License. Shaxsiy va tijorat maqsadlarda erkin foydalaning.
