# Habit Tracker Bot

Персональный Telegram-бот для отслеживания ежедневных привычек.

## Установка

```bash
cd habit_bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Настройка

Скопируй `.env.example` в `.env` и заполни:

```bash
cp .env.example .env
```

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен от @BotFather |
| `ALLOWED_USER_ID` | Твой Telegram user ID (узнать: @userinfobot) |
| `DAILY_TIME` | Время утренней рассылки (HH:MM) |
| `TIMEZONE` | Часовой пояс (например `Europe/Minsk`) |

## Запуск

```bash
python main.py
```

## Команды

- `/start` — приветствие + карточка дня
- `/today` — карточка на сегодня
- `/stats` — статистика (неделя / месяц / всё время)

## Иконки

Замени файлы в `assets/icons/` на свои PNG 120×120.
