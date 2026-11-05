# language: Python, file: bot.py, target: Python 3.10+
# *Бот: Казино (подкрутка), кейсы, профиль. Админка по юзернейму @above*
# *зависимости: aiogram, aiosqlite, flask*

import asyncio
import random
import os
import aiosqlite
import logging
import threading
from flask import Flask
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "1780278979:ra-cpS_v5nVv7PFYhEbPWteUtuwsiD2t1Pr")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) # Можешь оставить 0, если работаешь только по юзернейму
ADMIN_USERNAME = "above" # Твой юзернейм для админки и связи

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Проверка на админа по юзернейму ---
def is_admin(user: types.User) -> bool:
    if not user.username:
        return False
    # Сравниваем без учета регистра
    return user.username.lower() == ADMIN_USERNAME.lower()

# --- Flask для Render (защита от сна) ---
app = Flask(__name__)
@app.route('/')
def health(): return "Casino is running", 200
def run_flask(): app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

# --- База данных ---
async def init_db():
    async with aiosqlite.connect("casino.db") as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            balance INTEGER DEFAULT 1000,
            lose_streak INTEGER DEFAULT 0
        )""")
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect("casino.db") as db:
        async with db.execute("SELECT balance, lose_streak FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return 1000, 0
            return row[0], row[1]

async def update_balance(user_id, amount):
    async with aiosqlite.connect("casino.db") as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def set_streak(user_id, streak):
    async with aiosqlite.connect("casino.db") as db:
        await db.execute("UPDATE users SET lose_streak = ? WHERE user_id = ?", (streak, user_id))
        await db.commit()

# --- Команда для получения ID (напиши боту /myid) ---
@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    await message.answer(f"Твой ID: <code>{message.from_user.id}</code>\nТвой юзернейм: @{message.from_user.username}", parse_mode="HTML")

# --- Главное меню ---
def get_main_menu(balance):
    kb = InlineKeyboardBuilder()
    kb.button(text="🎰 Казино (Цвета)", callback_data="casino_menu")
    kb.button(text="🎁 Кейсы", callback_data="cases_menu")
    kb.button(text="👤 Профиль", callback_data="profile")
    kb.button(text="🛒 О магазине", callback_data="about")
    kb.button(text="📞 Обратная связь", url=f"https://t.me/{ADMIN_USERNAME}")
    kb.adjust(1)
    
    text = (
        "🔥 <b>ДОБРО ПОЖАЛОВАТЬ В GIFT UPGRADER!</b> 🔥\n\n"
        "💎 Ты попал в лучший магазин подарков и казино!\n"
        "🎰 Здесь ты можешь испытать удачу в рулетке или открыть кейс с элитными подарками.\n\n"
        f"💰 Твой баланс: <b>{balance} ⭐</b>\n\n"
        "🎲 <i>Испытай удачу и сорви куш!</i>\n"
        "👇 Выбирай раздел:"
    )
    return text, kb.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    balance, _ = await get_user(message.from_user.id)
    text, kb = get_main_menu(balance)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

# --- Профиль ---
@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    balance, _ = await get_user(call.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await call.message.edit_text(
        f"👤 <b>Твой профиль</b>\n\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"💰 Баланс: <b>{balance} ⭐</b>\n\n"
        f"👨‍💻 Поддержка: @{ADMIN_USERNAME}",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "topup")
async def topup(call: CallbackQuery):
    await update_balance(call.from_user.id, 1000)
    await call.answer("💸 Тебе начислено 1000 звезд (тестовое пополнение)!", show_alert=True)
    await profile(call)

# --- Казино ---
@dp.callback_query(F.data == "casino_menu")
async def casino_menu(call: CallbackQuery):
    balance, _ = await get_user(call.from_user.id)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔴 Красный (x2)", callback_data="bet_red")
    kb.button(text="⚫ Черный (x2)", callback_data="bet_black")
    kb.button(text="🟢 Зеленый (x10)", callback_data="bet_green")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(2, 1, 1)
    
    await call.message.edit_text(
        f"🎰 <b>Рулетка</b>\n\n"
        f"Выбери цвет и поставь 500 ⭐.\n"
        f"💰 Твой баланс: <b>{balance} ⭐</b>\n\n"
        f"🔴 Красный — x2\n"
        f"⚫ Черный — x2\n"
        f"🟢 Зеленый — x10\n\n"
        f"<i>Угадаешь цвет — забираешь множитель. Не угадаешь — теряешь ставку.</i>",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("bet_"))
async def play_casino(call: CallbackQuery):
    bet_amount = 500
    user_id = call.from_user.id
    balance, lose_streak = await get_user(user_id)
    
    if balance < bet_amount:
        await call.answer("🚫 Недостаточно звезд! Пополни профиль.", show_alert=True)
        return
        
    chosen_color = call.data.split("_")[1]
    
    # --- ЛОГИКА ПОДКРУТКИ ---
    win = False
    
    if lose_streak > 0:
        win = False
        await set_streak(user_id, lose_streak - 1) 
    else:
        if random.random() < 0.30:
            win = True
            new_streak = random.randint(2, 4)
            await set_streak(user_id, new_streak)
        else:
            win = False

    if win:
        winning_color = chosen_color
    else:
        winning_color = random.choice([c for c in ["red", "black", "green"] if c != chosen_color])

    if win:
        if winning_color == "green":
            payout = bet_amount * 10
            await update_balance(user_id, payout - bet_amount)
            result_text = f"🤯 <b>ДЖЕКПОТ!!! ЗЕЛЕНЫЙ!</b> Ты выиграл <b>{payout} ⭐</b>!"
        else:
            payout = bet_amount * 2
            await update_balance(user_id, payout - bet_amount)
            result_text = f"🎉 <b>ПОБЕДА!</b> Выпал {winning_color.upper()}. Ты выиграл <b>{payout} ⭐</b>!"
    else:
        await update_balance(user_id, -bet_amount)
        result_text = f"😢 <b>ПРОИГРЫШ.</b> Выпал {winning_color.upper()}. Ты потерял <b>{bet_amount} ⭐</b>."
        
    new_balance, _ = await get_user(user_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить еще", callback_data="casino_menu")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back")]
    ])
    
    await call.message.edit_text(
        f"{result_text}\n\n"
        f"💰 Новый баланс: <b>{new_balance} ⭐</b>",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

# --- Кейсы ---
CASES = {
    "case_1": {"name": "🥉 Дешевый кейс", "price": 100, "items": [("Мусор", 80), ("Стикер", 15), ("Миньон", 4), ("Элитный подарок", 1)]},
    "case_2": {"name": "🥈 Обычный кейс", "price": 500, "items": [("Мусор", 75), ("Стикер", 18), ("Миньон", 5), ("Элитный подарок", 2)]},
    "case_3": {"name": "🥇 Редкий кейс", "price": 1000, "items": [("Мусор", 70), ("Стикер", 20), ("Миньон", 8), ("Элитный подарок", 2)]},
    "case_4": {"name": "💎 Эпический кейс", "price": 2500, "items": [("Мусор", 60), ("Стикер", 25), ("Миньон", 12), ("Элитный подарок", 3)]},
    "case_5": {"name": "👑 Элитный кейс", "price": 5000, "items": [("Мусор", 50), ("Стикер", 30), ("Миньон", 15), ("Элитный подарок", 5)]}
}

@dp.callback_query(F.data == "cases_menu")
async def cases_menu(call: CallbackQuery):
    balance, _ = await get_user(call.from_user.id)
    kb = InlineKeyboardBuilder()
    for case_id, data in CASES.items():
        kb.button(text=f"{data['name']} — {data['price']} ⭐", callback_data=f"open_{case_id}")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(1)
    
    await call.message.edit_text(
        f"🎁 <b>Магазин кейсов</b>\n\n"
        f"💰 Твой баланс: <b>{balance} ⭐</b>\n"
        f"Выбери кейс, чтобы испытать удачу:",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("open_"))
async def open_case(call: CallbackQuery):
    case_id = call.data.split("_")[1] + "_" + call.data.split("_")[2]
    case = CASES[case_id]
    user_id = call.from_user.id
    balance, _ = await get_user(user_id)
    
    if balance < case["price"]:
        await call.answer("🚫 Недостаточно звезд!", show_alert=True)
        return
        
    await update_balance(user_id, -case["price"])
    
    items = [item[0] for item in case["items"]]
    weights = [item[1] for item in case["items"]]
    won_item = random.choices(items, weights=weights, k=1)[0]
    
    new_balance, _ = await get_user(user_id)
    
    if "Элитный" in won_item:
        await update_balance(user_id, case["price"] * 2)
        new_balance, _ = await get_user(user_id)
        result = f"🎉 ДЖЕКПОТ! Тебе выпал <b>{won_item}</b>! Ты сорвал куш!"
    else:
        result = f"📦 Тебе выпал: <b>{won_item}</b>."
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Открыть еще", callback_data="cases_menu")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back")]
    ])
    
    await call.message.edit_text(
        f"{result}\n\n"
        f"💰 Новый баланс: <b>{new_balance} ⭐</b>",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

# --- О магазине ---
@dp.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Связаться", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await call.message.edit_text(
        f"🛒 <b>О магазине GiftUpgrader</b>\n\n"
        f"Мы предоставляем лучший сервис по открытию кейсов и игре в рулетку с подарками Telegram.\n\n"
        f"✅ Честность (почти) \n"
        f"✅ Мгновенные выплаты\n"
        f"✅ Лучшие цены\n\n"
        f"👨‍💻 Админ: @{ADMIN_USERNAME}",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

# --- Навигация ---
@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    balance, _ = await get_user(call.from_user.id)
    text, kb = get_main_menu(balance)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

async def main():
    await init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    print(f"[*] Бот запущен. Админ: @{ADMIN_USERNAME}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
