import asyncio
import logging
import re
import os
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import speech_recognition as sr
from pydub import AudioSegment

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- DATABASE SOZLAMALARI ---
def init_db():
    conn = sqlite3.connect("hisob_kitob.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS operatsiyalar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tur TEXT, 
        summa INTEGER,
        izoh TEXT,
        sana TEXT,
        holat TEXT DEFAULT 'faol'  -- 'faol' yoki 'arxiv' (hisobotdan keyin arxivlanadi)
    )
    """)
    conn.commit()
    conn.close()

init_db()

def info_saqlash(user_id, tur, summa, izoh):
    conn = sqlite3.connect("hisob_kitob.db")
    cursor = conn.cursor()
    sana = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO operatsiyalar (user_id, tur, summa, izoh, sana)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, tur, summa, izoh, sana))
    conn.commit()
    conn.close()

def hisobot_va_arxivlash(user_id):
    conn = sqlite3.connect("hisob_kitob.db")
    cursor = conn.cursor()
    
    # Faqat hisobot berilmagan (faol) pullarni hisoblash
    cursor.execute("SELECT SUM(summa) FROM operatsiyalar WHERE user_id = ? AND tur = 'daromat' AND holat = 'faol'", (user_id,))
    daromat = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(summa) FROM operatsiyalar WHERE user_id = ? AND tur = 'xarajat' AND holat = 'faol'", (user_id,))
    xarajat = cursor.fetchone()[0] or 0
    
    # Hisobot so'ralgan zahoti ularni 'arxiv' holatiga o'tkazamiz (keyingi safar qo'shilmaydi)
    cursor.execute("UPDATE operatsiyalar SET holat = 'arxiv' WHERE user_id = ? AND holat = 'faol'", (user_id,))
    
    conn.commit()
    conn.close()
    return daromat, xarajat

def vaqtli_statistika(user_id, kunlar):
    conn = sqlite3.connect("hisob_kitob.db")
    cursor = conn.cursor()
    
    # Berilgan kundan boshlab hozirgacha bo'lgan vaqt oralig'i
    sana_chegarasi = (datetime.now() - timedelta(days=kunlar)).strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("SELECT SUM(summa) FROM operatsiyalar WHERE user_id = ? AND tur = 'daromat' AND sana >= ?", (user_id, sana_chegarasi))
    daromat = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(summa) FROM operatsiyalar WHERE user_id = ? AND tur = 'xarajat' AND sana >= ?", (user_id, sana_chegarasi))
    xarajat = cursor.fetchone()[0] or 0
    
    conn.close()
    return daromat, xarajat
# -----------------------------

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(
        "Salom! Men sizning aqlli hisobchingizman. ✨\n\n"
        "Menga xarajatlarni yozishingiz yoki **ovozli xabar** yuborishingiz mumkin!\n"
        "**Masalan:** '5000 so'm yo'lga ketdi' yoki '100000 oylik oldim'\n\n"
        "📜 **Buyruqlar:**\n"
        "• `hisobot` - oxirgi hisobotdan keyingi pullarni hisoblab, hisobni yangilaydi (nol qiladi).\n"
        "• `1 kunlik`, `1 haftalik`, `1 oylik` - umumiy arxivni vaqt bo'yicha chiqaradi."
    )

async def matnni_tahlil_qilish(message: types.Message, text: str):
    text = text.lower()
    
    # 1. Hisobot so'ralgan holat
    if "hisobot" in text or "hisobod" in text:
        daromat, xarajat = hisobot_va_arxivlash(message.from_user.id)
        balans = daromat - xarajat
        await message.answer(
            f"📊 **Yangi hisobot tayyorlandi (Hisob nollindi):**\n\n"
            f"💰 Daromad: `{daromat} so'm`\n"
            f"💸 Xarajat: `{xarajat} so'm`\n"
            f"💳 Balans: `{balans} so'm`"
        )
        return

    # 2. Vaqtli statistika so'ralgan holat
    kunlar = None
    if "1 kunlik" in text or "bugungi" in text:
        kunlar = 1
    elif "1 haftalik" in text or "hafta" in text:
        kunlar = 7
    elif "1 oylik" in text or "oylik harajat" in text:
        kunlar = 30
        
    if kunlar is tracking_period := kunlar:
        daromat, xarajat = vaqtli_statistika(message.from_user.id, tracking_period)
        await message.answer(
            f"📅 **{tracking_period} kunlik umumiy statistika:**\n\n"
            f"💰 Daromad: `{daromat} so'm`\n"
            f"💸 Xarajat: `{xarajat} so'm`\n"
            f"💳 Umumiy sof foyda: `{daromat - xarajat} so'm`"
        )
        return

    # 3. Oddiy xarajat yoki daromad kiritish
    sonlar = re.findall(r'\d+', text)
    if not sonlar:
        await message.answer("Tushunmadim. Iltimos, xabarda summa ko'rsating (Masalan: 4000 taksi).")
        return
        
    summa = int(sonlar[0])
    daromat_sozlar = ['oldim', 'daromat', 'oylik', 'foyda', 'maosh', 'pul tushdi', 'daromad']
    izoh = text.replace(str(summa), "").replace("so'm", "").replace("som", "").strip()
    if not izoh: izoh = "Izohsiz"

    tur = "xarajat"
    for soz in daromat_sozlar:
        if soz in text:
            tur = "daromat"
            break
            
    info_saqlash(message.from_user.id, tur, summa, izoh)
    
    if tur == "daromat":
        await message.answer(f"✅ Daromad yozildi: +{summa} so'm ({izoh})")
    else:
        await message.answer(f"❌ Xarajat yozildi: -{summa} so'm ({izoh})")

# MATNLI XABARLAR UCHUN
@dp.message(lambda message: message.text is not None)
async def handle_text(message: types.Message):
    await matnni_tahlil_qilish(message, message.text)

# OVOZLI XABARLAR UCHUN (Voice Message)
@dp.message(lambda message: message.voice is not None)
async def handle_voice(message: types.Message):
    await message.answer("🎙 Ovozli xabaringiz qabul qilindi, tahlil qilinmoqda...")
    
    # Telegramdan ovozli faylni yuklab olish
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path
    
    # Ovozli faylni vaqtincha serverga saqlaymiz
    local_filename = f"voice_{message.from_user.id}.ogg"
    await bot.download_file(file_path, local_filename)
    
    # Hozircha tekin serverda ovozni matnga o'g'irish murakkab bo'lgani uchun,
    # bot ovoz kelganini tasdiqlaydi. To'liq ovozni tushunish (Speech-to-Text) uchun
    # keyingi bosqichda bitta tekin kutubxona qo'shamiz.
    await message.answer("💡 Ovozli xabarlarni matnga o'giruvchi modul tekshirilmoqda. Hozircha xarajatlarni matn ko'rinishida yozib turishingizni tavsiya qilaman!")
    
    # Faylni o'chirib tashlaymiz (server to'lib ketmasligi uchun)
    if os.path.exists(local_filename):
        os.remove(local_filename)

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
