from aiogram import Bot, Dispatcher, executor, types
import os

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(bot)

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply("Бот работает!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
