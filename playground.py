import json
import math
import os
import random
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


def get_random_message(messages):
    return random.choice(messages)


FILE_NAME = "players.json"
OLD_FILE_NAME = Path(__file__).with_name("bot_data.json")

# --- Сохранение данных ---
def load_data():
    """Загружает игроков из JSON-файла."""
    try:
        players_file = Path(__file__).with_name(FILE_NAME)
        with open(players_file, "r", encoding="utf-8") as f:
            players_data = json.load(f)
    except FileNotFoundError:
        players_data = {}
    except json.JSONDecodeError:
        players_data = {}
    except (OSError, UnicodeError) as error:
        raise RuntimeError(f"Не удалось прочитать данные из {FILE_NAME}.") from error

    if isinstance(players_data, dict) and players_data:
        return players_data

    try:
        with open(OLD_FILE_NAME, "r", encoding="utf-8") as f:
            old_data = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Файл со старыми данными {OLD_FILE_NAME} повреждён."
        ) from error
    except (OSError, UnicodeError) as error:
        raise RuntimeError(
            f"Не удалось прочитать старые данные из {OLD_FILE_NAME}."
        ) from error

    if isinstance(old_data, dict):
        return old_data.get("players", {})
    return {}


def save_data(data):
    """Сохраняет игроков в JSON-файл."""
    try:
        if os.getenv("BOT_DEBUG_SAVE") == "1":
            breakpoint()
        players_file = Path(__file__).with_name(FILE_NAME)
        with open(players_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (OSError, TypeError, ValueError) as error:
        raise RuntimeError(f"Не удалось сохранить данные в {FILE_NAME}.") from error


# Загружаем игроков один раз при запуске бота.
players = load_data()


def get_player_stats(user_id):
    player_id = str(user_id)
    if player_id not in players:
        players[player_id] = {
            "wins": 0,
            "loses": 0,
            "games": 0,
            "draws": 0,
            "points": 0,
            "coin": 0,
            "dice": 0,
        }
    player = players[player_id]
    player.setdefault("draws", 0)
    player.setdefault("points", player.get("wins", 0) * 3 + player["draws"])
    return player


def update_game_result(user_id, win):
    player = get_player_stats(user_id)
    player["games"] += 1
    if win is True:
        player["wins"] += 1
        player["points"] += 3
    elif win is False:
        player["loses"] += 1
    else:
        player["draws"] += 1
        player["points"] += 1
    save_data(players)

# --- Состояние текущих игр ---
games = {}

GAME_LEVELS = {
    "easy": (1, 10, "лёгкий"),
    "medium": (1, 100, "средний"),
    "hard": (1, 1000, "сложный"),
}


def start_number_game(user_id, level):
    low, high, level_name = GAME_LEVELS[level]
    max_attempts = math.ceil(math.log2(high - low + 1))
    games[user_id] = {
        "type": "guess",
        "secret": random.randint(low, high),
        "low": low,
        "high": high,
        "attempts": 0,
        "max_attempts": max_attempts,
    }
    return (
        f"Уровень: {level_name}. Я загадал число от {low} до {high}. "
        f"У тебя {max_attempts} попыток. Попробуй угадать!"
    )


# --- Основные команды ---
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    games[user_id] = {"type": "menu"}

    await update.message.reply_text(
        "Привет! Я — мини-бот с играми.\n\n"
        "Команды:\n"
        "/guess — игра «Угадай число»\n"
        "Уровни сложности:\n"
        "easy — лёгкий (1–10)\n"
        "medium — средний (1–100)\n"
        "hard — сложный (1–1000)\n"
        "/coin — подброс монеты\n"
        "/dice — бросок кубика\n"
        "/rps — камень/ножницы/бумага\n"
        "/fact — случайный факт\n"
        "/stats — статистика\n"
        "/leaderboard — таблица лидеров\n\n"
        "/fame — зал славы игроков с 3+ победами\n\n"
        f"{format_leaderboard(players)}\n\n"
        "/help — помощь\n"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/guess — игра «Угадай число»\n"
        "Уровни сложности:\n"
        "easy — лёгкий (1–10)\n"
        "medium — средний (1–100)\n"
        "hard — сложный (1–1000)\n"
        "/coin — орёл или решка\n"
        "/dice — бросок кубика\n"
        "/rps — камень/ножницы/бумага\n"
        "/fact — случайный факт\n"
        "/stats — статистика\n"
        "/leaderboard — таблица лидеров\n"
        "/fame — зал славы игроков с 3+ победами\n"
        "/start — главное меню\n"
    )


def format_leaderboard(players):
    if not players:
        return "Пока нет игроков."

    top_players = sorted(
        players.items(),
        key=lambda item: item[1].get(
            "points",
            item[1].get("wins", 0) * 3 + item[1].get("draws", 0),
        ),
        reverse=True,
    )[:5]
    lines = ["🏆 Топ-5 по очкам (победа — 3, ничья — 1):"]

    for place, (user_id, player) in enumerate(top_players, start=1):
        points = player.get(
            "points",
            player.get("wins", 0) * 3 + player.get("draws", 0),
        )
        lines.append(
            f"{place}. Игрок {user_id} — {points} очков"
        )

    return "\n".join(lines)


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send(update, format_leaderboard(players))

async def fame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    famous_players = [
        (user_id, player)
        for user_id, player in players.items()
        if player.get("wins", 0) >= 3
    ]
    if not famous_players:
        await send(update, "В зале славы пока никого нет. Набери 3 победы!")
        return

    top_players = sorted(
        famous_players,
        key=lambda item: item[1].get(
            "points",
            item[1].get("wins", 0) * 3 + item[1].get("draws", 0),
        ),
        reverse=True,
    )[:5]
    lines = ["🌟 Зал славы — игроки с 3+ победами:"]
    for place, (user_id, player) in enumerate(top_players, start=1):
        points = player.get(
            "points",
            player.get("wins", 0) * 3 + player.get("draws", 0),
        )
        lines.append(f"{place}. Игрок {user_id} — {points} очков")
    await send(update, "\n".join(lines))

# --- /guess: уровни ---
async def guess_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        keyboard = [
            [InlineKeyboardButton("Лёгкий (1–10)", callback_data="guess_level:easy")],
            [InlineKeyboardButton("Средний (1–100)", callback_data="guess_level:medium")],
            [InlineKeyboardButton("Сложный (1–1000)", callback_data="guess_level:hard")],
        ]
        await update.effective_message.reply_text(
            "Выбери уровень игры «Угадай число»:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    level = args[0].lower()

    if level not in GAME_LEVELS:
        await update.message.reply_text(
            "Неверный уровень. Выбери: easy, medium, hard\n"
            "Например: /guess easy. Или отправь /guess и нажми кнопку."
        )
        return

    await update.effective_message.reply_text(start_number_game(user_id, level))


async def game_level_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    level = query.data.partition(":")[2]
    if level not in GAME_LEVELS:
        await query.edit_message_text("Не удалось выбрать уровень. Отправь /guess и попробуй ещё раз.")
        return

    prompt = start_number_game(update.effective_user.id, level)
    await query.edit_message_text(prompt)

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message

    if user_id not in games or games[user_id].get("type") != "guess":
        return

    try:
        guess = int(message.text)
    except (TypeError, ValueError):
        await message.reply_text("Пожалуйста, введи число!")
        return

    game = games[user_id]
    secret = game["secret"]
    low = game["low"]
    high = game["high"]

    if guess < low or guess > high:
        await message.reply_text(f"Введи число от {low} до {high}!")
        return

    game["attempts"] += 1

    if guess < secret:
        await message.reply_text("Моё число больше!")
    elif guess > secret:
        await message.reply_text("Моё число меньше!")
    else:
        await message.reply_text(f"Поздравляю! Ты угадал число {secret}! 🎉")
        update_game_result(user_id, True)
        del games[user_id]
        return

    if game["attempts"] >= game["max_attempts"]:
        await message.reply_text(f"Ты проиграл 😢 Я загадал число {secret}.")
        update_game_result(user_id, False)
        del games[user_id]

# --- Монетка ---
async def coin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["орёл", "решка"])
    player = get_player_stats(update.effective_user.id)
    player["coin"] += 1
    save_data(players)
    await update.message.reply_text(f"Подбрасываю монетку... Выпало: {result}!")

# --- Кубик ---
async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    sides = 6

    if args:
        try:
            sides = int(args[0])
        except ValueError:
            await update.message.reply_text("Нужно число, например: /dice 20")
            return

    if sides < 2:
        await update.message.reply_text("Количество граней должно быть больше 1.")
        return

    roll = random.randint(1, sides)
    player = get_player_stats(update.effective_user.id)
    player["dice"] += 1
    save_data(players)
    await update.message.reply_text(f"🎲 Бросок кубика: {roll} / {sides}")

# --- Камень / Ножницы / Бумага ---
async def rps_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    games[user_id] = {"type": "rps"}
    await update.message.reply_text(
        "Игра: Камень / Ножницы / Бумага\n"
        "Напиши одно из: камень, ножницы, бумага"
    )

async def handle_rps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in games or games[user_id].get("type") != "rps":
        return

    text = update.message.text.lower().strip()
    options = ["камень", "ножницы", "бумага"]

    if text not in options:
        await update.message.reply_text("Напиши: камень, ножницы или бумага")
        return

    bot_choice = random.choice(options)
    win_map = {
        "камень": "ножницы",
        "ножницы": "бумага",
        "бумага": "камень"
    }

    if text == bot_choice:
        result = "Ничья!"
        update_game_result(user_id, None)
    elif win_map[text] == bot_choice:
        result = "Ты победил! 🎉"
        update_game_result(user_id, True)
    else:
        result = "Я победил! 😎"
        update_game_result(user_id, False)

    await update.message.reply_text(
        f"Ты: {text}\nЯ: {bot_choice}\n{result}"
    )
    del games[user_id]

# --- Случайный факт ---
async def random_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    facts = [
        "Пчёлы могут распознавать человеческие лица.",
        "У морских ежей нет глаз.",
        "Вода в океанах способна светиться в некоторых местах из-за биолюминесценции.",
        "Бумага была изобретена в Китае около 2 тысяч лет назад.",
        "Крокодилы не могут высовывать язык.",
        "У кошек больше костей в хвосте, чем вы думаете.",
        "Летучие мыши — единственные млекопитающие, способные к настоящему полёту.",
        "Медузы могут жить очень долго, некоторые — десятки лет.",
    ]
    await send(update, random.choice(facts))
async def send(update, text):
    await update.effective_message.reply_text(text)

# --- Статистика ---
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    player = get_player_stats(user_id)
    save_data(players)
    await update.message.reply_text(
        f"Твоя статистика:\n"
        f"Побед: {player['wins']}\n"
        f"Поражений: {player['loses']}\n"
        f"Ничьих: {player['draws']}\n"
        f"Очков: {player['points']}\n"
        f"Всего игр: {player['games']}\n"
        f"Монет: {player['coin']}\n"
        f"Кубиков: {player['dice']}"
    )

# --- Общий обработчик текстовых сообщений ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip().lower()
    user_id = update.effective_user.id

    # Если игра "камень/ножницы/бумага"
    if user_id in games and games[user_id].get("type") == "rps":
        await handle_rps(update, context)
        return

    # Если игра "угадай число"
    if user_id in games and games[user_id].get("type") == "guess":
        await handle_guess(update, context)
        return

    # Просто ответы на слова
    if text in ["камень", "ножницы", "бумага"]:
        await handle_rps(update, context)
        return

    if text in ["орёл", "орел", "решка"]:
        result = random.choice(["орёл", "решка"])
        await update.message.reply_text(f"Подбрасываю... Выпало: {result}!")
        return

def main():
    load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN в файле .env")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start_game))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        CallbackQueryHandler(game_level_callback, pattern=r"^guess_level:")
    )
    app.add_handler(CommandHandler("guess", guess_game))
    app.add_handler(CommandHandler("coin", coin_game))
    app.add_handler(CommandHandler("dice", dice_game))
    app.add_handler(CommandHandler("rps", rps_game))
    app.add_handler(CommandHandler("fact", random_fact))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("fame", fame))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()