from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from flask import Flask
from threading import Thread
import asyncio

import os

API_TOKEN = os.getenv('API_TOKEN')
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID'))

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Flask keep_alive
app = Flask('')


@app.route('/')
def home():
    return "Бот работает!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


# Состояния FSM
class OrderHookah(StatesGroup):
    base = State()
    strength = State()
    addon = State()
    flavor = State()
    phone = State()
    comment = State()


# Главное меню
@dp.message_handler(commands=['start', 'menu'], state='*')
async def start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Заказать кальян", "Меню и цены")
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=keyboard)


# Меню
@dp.message_handler(lambda m: m.text == "Меню и цены", state='*')
async def send_menu(message: types.Message):
    with open("menu.jpg", "rb") as photo:
        await message.answer_photo(photo, caption="Наше меню и цены:")


# Заказ — шаг 1
@dp.message_handler(lambda m: m.text == "Заказать кальян", state='*')
async def order_start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("На чаше (3000₽)", "Отмена")
    await message.answer("Выберите основу:", reply_markup=keyboard)
    await OrderHookah.base.set()


@dp.message_handler(lambda m: m.text == "Отмена", state='*')
async def cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await start(message)


# Крепость
@dp.message_handler(state=OrderHookah.base)
async def choose_strength(message: types.Message, state: FSMContext):
    await state.update_data(base=message.text, price=3000)
    await message.answer("Оцените крепость от 1 до 10:")
    await OrderHookah.strength.set()


# Добавки
@dp.message_handler(state=OrderHookah.strength)
async def choose_addon(message: types.Message, state: FSMContext):
    await state.update_data(strength=message.text)

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Молоко (+200)", "Вино (+400)", "Абсент (+500)", "Без добавки", "Отмена")
    await message.answer("Выберите добавку (максимум одна):", reply_markup=keyboard)
    await OrderHookah.addon.set()


# Вкусы
@dp.message_handler(state=OrderHookah.addon)
async def choose_flavor(message: types.Message, state: FSMContext):
    addon_text = message.text
    addon_price = 0

    if "Молоко" in addon_text:
        addon_price = 200
    elif "Вино" in addon_text:
        addon_price = 400
    elif "Абсент" in addon_text:
        addon_price = 500

    await state.update_data(addon=addon_text, addon_price=addon_price)
    await message.answer("Введите вкусовые предпочтения:")
    await OrderHookah.flavor.set()


# Телефон
@dp.message_handler(state=OrderHookah.flavor)
async def ask_phone(message: types.Message, state: FSMContext):
    await state.update_data(flavor=message.text)
    await message.answer("Введите контактный номер телефона (мы свяжемся с вами через WhatsApp):")
    await OrderHookah.phone.set()


# Комментарий
@dp.message_handler(state=OrderHookah.phone)
async def ask_comment(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Комментарий (не обязательно):")
    await OrderHookah.comment.set()


# Финал
@dp.message_handler(state=OrderHookah.comment)
async def finish_order(message: types.Message, state: FSMContext):
    await state.update_data(comment=message.text)
    data = await state.get_data()

    total = data['price'] + data['addon_price']
    summary = (
        f"✅ *Ваш заказ принят!*\n\n"
        f"Основа: {data['base']}\n"
        f"Крепость: {data['strength']}/10\n"
        f"Добавка: {data['addon']}\n"
        f"Вкус: {data['flavor']}\n"
        f"Телефон (WhatsApp): {data['phone']}\n"
        f"Комментарий: {data['comment'] or '—'}\n\n"
        f"💰 *Итого: {total} ₽*\n"
        f"Способ оплаты: наличные или перевод\n"
    )

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("В главное меню")
    await message.answer(summary, parse_mode='Markdown', reply_markup=markup)

    # Отправка админу в группу
    confirm_markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_order"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_order")
    )

    username = message.from_user.username or "нет юзернейма"
    order_msg = await bot.send_message(
        ADMIN_CHAT_ID,
        f"📥 Новый заказ от @{username}:\n\n{summary}",
        parse_mode='Markdown',
        reply_markup=confirm_markup
    )

    await state.update_data(user_id=message.from_user.id, admin_msg_id=order_msg.message_id)

    # Отложенный отзыв
    await asyncio.sleep(3600)
    await bot.send_message(message.from_user.id, "📝 Как вам наш кальян? Оставьте отзыв, просто ответив на это сообщение.")


# Обработка подтверждения или отмены
@dp.callback_query_handler(lambda c: c.data in ["confirm_order", "cancel_order"])
async def handle_order_decision(callback_query: types.CallbackQuery):
    message = callback_query.message
    user_id = callback_query.from_user.id

    if callback_query.data == "confirm_order":
        await message.edit_reply_markup()
        await bot.send_message(message.chat.id, "✅ Заказ подтвержден")
        await bot.send_message(user_id, "Ваш заказ подтвержден и скоро будет готов.")
    else:
        await message.edit_reply_markup()
        await bot.send_message(message.chat.id, "❌ Заказ отменён")
        await bot.send_message(user_id, "К сожалению, заказ был отменён.")


if __name__ == '__main__':
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
