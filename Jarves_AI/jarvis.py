import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import os
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Foydalanuvchilar ma'lumotlarini saqlash
user_data = {}

@dp.message(Command("start", "help"))
async def send_welcome(message: types.Message):
    welcome_text = (
        "Salom! Men sizning aqlli shaxsiy hisobchingizman. 💰\n\n"
        "Menga xarajat va daromadlaringizni oddiy matn ko'rinishida yozishingiz mumkin.\n"
        "**Masalan:**\n"
        "✍️ `5000 so'm taksiga ketdi` (yoki shunchaki `5000 taksiga`)\n"
        "✍️ `15000 ovqatga ishlatdim`\n"
        "✍️ `100000 pul tushdi` (daromad)\n\n"
        "📊 Kunlik xarajatlarni bilish uchun: **/hisobot** deb yozing yoki *'bugun qancha pulim ketdi'* deb so'rang!"
    )
    await message.reply(welcome_text, parse_mode="Markdown")

@dp.message(Command("hisobot"))
async def show_report_command(message: types.Message):
    await generate_report(message)

@dp.message()
async def handle_user_message(message: types.Message):
    chat_id = message.chat.id
    text = message.text.lower().strip()
    
    # 1. Hisobot so'ralganini aniqlash (Savollar uchun)
    if "qancha pul" in text or "qancha ketdi" in text or "hisobot" in text or "nimalarga" in text:
        await generate_report(message)
        return

    # 2. Matn ichidan sonni (summani) qidirib topish
    numbers = re.findall(r'\d+', text)
    if not numbers:
        await message.reply("🤖 Tushunmadim. Iltimos, gapingizda summa (son) ishlating. Masalan: `20000 tushlikka`")
        return
    
    summa = int(numbers[0]) # Birinchi topilgan sonni olamiz
    
    # 3. Daromad yoki xarajatligini aniqlash
    # Agar gap ichida 'tushdi', 'oldi', 'qo'shildi', '+' kabi so'zlar bo'lsa daromad deb oladi
    is_income = any(word in text for word in ["tushdi", "puli tushdi", "oldim", "qo'shildi", "+", "daromad"])
    
    # Izoh (nimaga ketganini) aniqlash: sonni matndan olib tashlaymiz
    izoh = text.replace(str(summa), "").replace("so'm", "").replace("som", "").replace("min", "").strip()
    if not izoh:
        izoh = "Daromad" if is_income else "Xarajat (izohsiz)"

    # Foydalanuvchi bazasini tekshirish
    if chat_id not in user_data:
        user_data[chat_id] = {'daromad': 0, 'xarajat': 0, 'tarix': []}
        
    if is_income:
        user_data[chat_id]['daromad'] += summa
        user_data[chat_id]['tarix'].append({'turi': 'daromad', 'summa': summa, 'izoh': izoh})
        await message.reply(f"✅ Daromad qo'shildi: +{summa:,} so'm. ({izoh})")
    else:
        user_data[chat_id]['xarajat'] += summa
        user_data[chat_id]['tarix'].append({'turi': 'xarajat', 'summa': summa, 'izoh': izoh})
        await message.reply(f"✅ Xarajat yozib olindi: -{summa:,} so'm. ({izoh})")

# Hisobotni shakllantirish funksiyasi
async def generate_report(message: types.Message):
    chat_id = message.chat.id
    if chat_id not in user_data or not user_data[chat_id]['tarix']:
        await message.reply("Sizda hali hech qanday xarajat yoki daromad yozilmagan.")
        return
    
    data = user_data[chat_id]
    report = "📊 **Sizning bugungi hisobotingiz:**\n\n"
    
    xarajatlar_matni = ""
    daromadlar_matni = ""
    
    for item in data['tarix']:
        if item['turi'] == 'xarajat':
            xarajatlar_matni += f"🔹 {item['izoh']}: {item['summa']:,} so'm\n"
        else:
            daromadlar_matni += f"🔸 {item['izoh']}: {item['summa']:,} so'm\n"
            
    if daromadlar_matni:
        report += f"📈 **Daromadlar:**\n{daromadlar_matni}\n"
    if xarajatlar_matni:
        report += f"📉 **Xarajatlar:**\n{xarajatlar_matni}\n"
        
    qolgan_pul = data['daromad'] - data['xarajat']
    
    report += "---------------------------------------\n"
    report += f"➕ **Jami qo'shildi (Daromad):** {data['daromad']:,} so'm\n"
    report += f"➖ **Jami ketdi (Xarajat):** {data['xarajat']:,} so'm\n"
    report += f"💰 **Hozirgi hamyon balansi:** {qolgan_pul:,} so'm"
    
    await message.reply(report, parse_mode="Markdown")

async def main():
    print("Aqlli hisobchi bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
