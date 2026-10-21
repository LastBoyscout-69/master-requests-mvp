import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import aiosqlite

TOKEN = "8882010503:AAHXabj9_gXHjnMPFgsp9CEBB6q_d9TI-ao"
DB_PATH = "requests.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

async def save_request(name, phone, problem):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO requests (name, phone, problem) VALUES (?, ?, ?)",
            (name, phone, problem),
        )
        await db.commit()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот для заявок на выезд мастера.\n"
        "Отправьте сообщение в формате:\n"
        "<Имя>\n<Телефон>\n<Проблема>"
    )

@dp.message()
async def handle_text(message: types.Message):
    lines = message.text.strip().split("\n")
    if len(lines) < 3:
        await message.answer("Пожалуйста, отправьте 3 строки: имя, телефон, проблема.")
        return
    name, phone, problem = lines[0].strip(), lines[1].strip(), "\n".join(lines[2:]).strip()
    await save_request(name, phone, problem)
    await message.answer("Заявка принята! Статус можно проверить на сайте.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
