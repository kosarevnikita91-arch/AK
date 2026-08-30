import asyncio
import os
from html import escape
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)


ALLOWED_PACK_NAME = "t_me_akstikers_by_fStikBot"
SUGGESTIONS_GROUP_ID = -1002993889807
SUGGESTIONS_THREAD_ID = 56643
MUTE_HOURS = 2

dp = Dispatcher()


start_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Предложить стикер",
                callback_data="suggest_sticker",
            )
        ]
    ]
)


async def is_admin(message: Message, bot: Bot) -> bool:
    member = await bot.get_chat_member(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
    )

    return member.status in {"administrator", "creator"}


async def mute_user(message: Message, bot: Bot):
    """Удаляет запрещённое сообщение и выдаёт мут на 2 часа."""

    try:
        await message.delete()
        print("Запрещённое сообщение удалено", flush=True)

    except Exception as error:
        print(f"Ошибка удаления сообщения: {error}", flush=True)

    try:
        until_date = datetime.now(timezone.utc) + timedelta(
            hours=MUTE_HOURS
        )

        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            permissions=ChatPermissions(
                can_send_messages=False,
            ),
            until_date=until_date,
        )

        print("Пользователь получил мут на 2 часа", flush=True)

    except Exception as error:
        print(f"Ошибка выдачи мута: {error}", flush=True)


async def send_sanction_message(message: Message, bot: Bot):
    """Отправляет уведомление о наказании в группу."""

    if message.from_user.username:
        user_text = f"@{escape(message.from_user.username)}"
    else:
        user_text = escape(message.from_user.full_name)

    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=(
                f"{user_text}, были наложены санкции за использование "
                "запрещённого стикерпака.\n\n"
                "Разрешённый стикерпак:\n"
                "https://t.me/addstickers/t_me_akstikers_by_fStikBot"
            ),
            parse_mode="HTML",
        )

        print("Уведомление отправлено", flush=True)

    except Exception as error:
        print(f"Ошибка отправки уведомления: {error}", flush=True)


@dp.message(F.chat.type == "private", F.text.startswith("/start"))
async def start_command(message: Message):
    await message.answer(
        text=(
            "Здравствуйте. Я — бот предложка для стикеров в группу: "
            "https://t.me/andrew_kingsman_group.\n\n"
            "Предложения принимаются только в формате фото."
        ),
        reply_markup=start_keyboard,
    )


@dp.callback_query(F.data == "suggest_sticker")
async def suggest_sticker_button(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        "Прикрепите фото стикера к следующему сообщению."
    )


@dp.message(F.chat.type == "private")
async def forward_suggestion(message: Message, bot: Bot):
    """Передаёт фотографии из личного чата в тему предложки."""

    if not message.photo:
        await message.answer(
            "Предложение принимается только в формате фото. "
            "Прикрепите фото стикера."
        )
        return

    try:
        await bot.copy_message(
            chat_id=SUGGESTIONS_GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=SUGGESTIONS_THREAD_ID,
        )

        await message.answer(
            "Спасибо! Фото стикера отправлено в предложку."
        )

        print(
            "Фото стикера отправлено в тему предложки",
            flush=True,
        )

    except Exception as error:
        print(
            f"Ошибка пересылки предложения: {error}",
            flush=True,
        )

        await message.answer(
            "Не удалось отправить фото. Попробуйте ещё раз."
        )


@dp.message()
async def handle_sticker(message: Message, bot: Bot):
    print("Бот получил сообщение", flush=True)
    print(f"Тип сообщения: {message.content_type}", flush=True)

    # Работаем только в группах
    if message.chat.type not in {"group", "supergroup"}:
        return

    # Проверяем отправителя
    if message.from_user is None:
        return

    # Администраторов не наказываем
    try:
        if await is_admin(message, bot):
            print(
                "Администратор — наказание не выдаётся",
                flush=True,
            )
            return

    except Exception as error:
        print(
            f"Ошибка проверки администратора: {error}",
            flush=True,
        )
        return

    # Запрещённые GIF
    if message.animation is not None:
        print("Обнаружена GIF-анимация", flush=True)

        await mute_user(message, bot)
        await send_sanction_message(message, bot)

        return

    # Если сообщение не является стикером
    if message.sticker is None:
        return

    # Проверяем стикерпак
    sticker_pack_name = message.sticker.set_name

    print(
        f"Имя набора стикера: {sticker_pack_name}",
        flush=True,
    )

    # Разрешённый стикерпак
    if sticker_pack_name == ALLOWED_PACK_NAME:
        print("Стикер разрешён", flush=True)
        return

    # Запрещённый стикерпак
    print("Стикер запрещён", flush=True)

    await mute_user(message, bot)
    await send_sanction_message(message, bot)


async def main():
    token = os.getenv("BOT_TOKEN")

    if not token:
        raise RuntimeError(
            "Не указана переменная окружения BOT_TOKEN"
        )

    bot = Bot(token=token)

    print(
        "Бот запущен и ожидает сообщения...",
        flush=True,
    )

    try:
        await dp.start_polling(bot)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
