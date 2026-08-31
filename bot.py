import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Dict

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import (
    Message,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)


ALLOWED_PACK_NAME = "t_me_akstikers_by_fStikBot"
SUGGESTIONS_USER_ID = 6558705988
MUTE_HOURS = 2
BAN_DAYS = 7

BANNED_USERS_FILE = Path("banned_users.json")
SUGGESTIONS_FILE = Path("suggestions.json")

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


def suggestion_keyboard(
    user_id: int,
    is_banned: bool = False,
    is_rejected: bool = False,
    is_accepted: bool = False,
) -> InlineKeyboardMarkup:
    accept_button = InlineKeyboardButton(
        text="Принято" if is_accepted else "Стикер принят",
        callback_data=(
            "already_accepted"
            if is_accepted
            else f"accept_suggestion:{user_id}"
        ),
    )

    reject_button = InlineKeyboardButton(
        text="Отклонено" if is_rejected else "Стикер отклонён",
        callback_data=(
            "already_rejected"
            if is_rejected
            else f"reject_suggestion:{user_id}"
        ),
    )

    ban_button = InlineKeyboardButton(
        text="Разбанить" if is_banned else "Забанить",
        callback_data=(
            f"unban_suggestion:{user_id}"
            if is_banned
            else f"ban_suggestion:{user_id}"
        ),
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [accept_button, reject_button],
            [ban_button],
        ]
    )


def load_banned_users() -> Dict[int, str]:
    if not BANNED_USERS_FILE.exists():
        return {}

    try:
        data = json.loads(
            BANNED_USERS_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(data, dict):
            return {}

        result = {}

        for user_id, ban_until in data.items():
            try:
                result[int(user_id)] = str(ban_until)
            except (ValueError, TypeError):
                continue

        return result

    except (OSError, json.JSONDecodeError) as error:
        print(f"Ошибка загрузки банов: {error}", flush=True)
        return {}


def save_banned_users(users: Dict[int, str]):
    try:
        BANNED_USERS_FILE.write_text(
            json.dumps(
                users,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    except OSError as error:
        print(f"Ошибка сохранения банов: {error}", flush=True)


banned_users = load_banned_users()


def is_user_banned(user_id: int) -> bool:
    ban_until_text = banned_users.get(user_id)

    if ban_until_text is None:
        return False

    try:
        ban_until = datetime.fromisoformat(ban_until_text)

        if ban_until.tzinfo is None:
            ban_until = ban_until.replace(tzinfo=timezone.utc)

    except (ValueError, TypeError):
        banned_users.pop(user_id, None)
        save_banned_users(banned_users)
        return False

    if datetime.now(timezone.utc) >= ban_until:
        banned_users.pop(user_id, None)
        save_banned_users(banned_users)
        return False

    return True


def load_suggestions() -> Dict[int, int]:
    if not SUGGESTIONS_FILE.exists():
        return {}

    try:
        data = json.loads(
            SUGGESTIONS_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(data, dict):
            return {}

        result = {}

        for message_id, user_id in data.items():
            try:
                result[int(message_id)] = int(user_id)
            except (ValueError, TypeError):
                continue

        return result

    except (OSError, json.JSONDecodeError) as error:
        print(
            f"Ошибка загрузки связей: {error}",
            flush=True,
        )
        return {}


def save_suggestions(suggestions: Dict[int, int]):
    try:
        SUGGESTIONS_FILE.write_text(
            json.dumps(
                suggestions,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    except OSError as error:
        print(
            f"Ошибка сохранения связей: {error}",
            flush=True,
        )


suggestion_messages = load_suggestions()


async def is_admin(message: Message, bot: Bot) -> bool:
    if message.from_user is None:
        return False

    member = await bot.get_chat_member(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
    )

    return member.status in {
        "administrator",
        "creator",
    }


async def mute_user(message: Message, bot: Bot):
    if message.from_user is None:
        return

    try:
        await message.delete()

    except Exception as error:
        print(
            f"Ошибка удаления сообщения: {error}",
            flush=True,
        )

    try:
        until_date = (
            datetime.now(timezone.utc)
            + timedelta(hours=MUTE_HOURS)
        )

        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
            ),
            until_date=until_date,
        )

    except Exception as error:
        print(
            f"Ошибка выдачи мута: {error}",
            flush=True,
        )


async def send_sanction_message(
    message: Message,
    bot: Bot,
):
    if message.from_user is None:
        return

    user = message.from_user
    user_name = escape(user.full_name)

    if user.username:
        sender_text = f"@{escape(user.username)}"
    else:
        sender_text = (
            f'<a href="tg://user?id={user.id}">'
            f"{user_name}"
            f"</a>"
        )

    text = (
        f"Пользователь: {sender_text}\n"
        f"Имя: {user_name}\n"
        f"ID: <code>{user.id}</code>\n\n"
        "ограничен за использование запрещённого "
        "стикерпака.\n\n"
        "Разрешённый стикерпак: "
        "https://t.me/addstickers/"
        "t_me_akstikers_by_fStikBot"
    )

    try:
        sent_message = await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            parse_mode="HTML",
        )

        await asyncio.sleep(15)

        try:
            await sent_message.delete()

        except Exception as error:
            print(
                f"Ошибка удаления уведомления: {error}",
                flush=True,
            )

    except Exception as error:
        print(
            f"Ошибка отправки уведомления: {error}",
            flush=True,
        )


@dp.message(
    F.chat.type == "private",
    F.text.startswith("/start"),
)
async def start_command(message: Message):
    await message.answer(
        text=(
            "Здравствуйте. Я — бот предложки для стикеров "
            "в группу:\n"
            "https://t.me/andrew_kingsman_group\n\n"
            "Предложения принимаются только в формате фото.\n\n"
            "Нажмите кнопку ниже, чтобы предложить стикер."
        ),
        reply_markup=start_keyboard,
    )


@dp.callback_query(F.data == "suggest_sticker")
async def suggest_sticker_button(callback: CallbackQuery):
    await callback.answer()

    if callback.message:
        await callback.message.answer(
            "Прикрепите фото стикера к следующему сообщению."
        )


@dp.message(
    F.chat.type == "private",
    F.reply_to_message,
)
async def reply_to_suggestion(
    message: Message,
    bot: Bot,
):
    if message.from_user is None:
        return

    if message.from_user.id != SUGGESTIONS_USER_ID:
        return

    replied_message_id = message.reply_to_message.message_id
    user_id = suggestion_messages.get(replied_message_id)

    if user_id is None:
        await message.answer(
            "Не удалось определить пользователя для этого предложения."
        )
        return

    try:
        if message.text:
            await bot.send_message(
                chat_id=user_id,
                text=message.text,
            )

        elif message.photo:
            await bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=message.caption,
            )

        elif message.document:
            await bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=message.caption,
            )

        else:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )

        await message.answer("Ответ отправлен пользователю.")

    except Exception as error:
        print(
            f"Ошибка отправки ответа: {error}",
            flush=True,
        )

        await message.answer(
            "Не удалось отправить ответ пользователю."
        )


@dp.message(F.chat.type == "private")
async def forward_suggestion(
    message: Message,
    bot: Bot,
):
    if message.from_user is None:
        return

    user = message.from_user
    user_id = user.id

    if user_id == SUGGESTIONS_USER_ID:
        return

    if is_user_banned(user_id):
        await message.answer(
            "Вы не можете отправлять предложения, "
            "так как заблокированы на 7 дней."
        )
        return

    if not message.photo:
        await message.answer(
            "Предложение принимается только в формате фото. "
            "Прикрепите фото стикера."
        )
        return

    user_name = escape(user.full_name)

    if user.username:
        sender_text = f"@{escape(user.username)}"
    else:
        sender_text = (
            f'<a href="tg://user?id={user.id}">'
            f"{user_name}"
            f"</a>"
        )

    caption = (
        f"Предложение от: {sender_text}\n"
        f"Имя: {user_name}\n"
        f"ID пользователя: <code>{user_id}</code>"
    )

    try:
        sent_message = await bot.send_photo(
            chat_id=SUGGESTIONS_USER_ID,
            photo=message.photo[-1].file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=suggestion_keyboard(
                user_id=user_id,
                is_banned=is_user_banned(user_id),
            ),
        )

        suggestion_messages[sent_message.message_id] = user_id
        save_suggestions(suggestion_messages)

        await message.answer(
            "Спасибо! Фото стикера отправлено."
        )

    except Exception as error:
        print(
            f"Ошибка отправки предложения: {error}",
            flush=True,
        )

        await message.answer(
            "Не удалось отправить фото. Попробуйте ещё раз."
        )


@dp.callback_query(F.data.startswith("accept_suggestion:"))
async def accept_suggestion(
    callback: CallbackQuery,
    bot: Bot,
):
    if callback.from_user.id != SUGGESTIONS_USER_ID:
        await callback.answer(
            "У вас нет прав для этого действия.",
            show_alert=True,
        )
        return

    try:
        user_id = int(callback.data.split(":", 1)[1])

        await bot.send_message(
            chat_id=user_id,
            text=(
                "Ваш стикер принят администрацией. "
                "Спасибо за предложение!"
            ),
        )

        await callback.answer(
            "Пользователь уведомлён о принятии."
        )

    except (ValueError, AttributeError):
        await callback.answer(
            "Неверный ID пользователя.",
            show_alert=True,
        )
        return

    except Exception as error:
        print(
            f"Ошибка уведомления о принятии: {error}",
            flush=True,
        )

        await callback.answer(
            "Не удалось уведомить пользователя.",
            show_alert=True,
        )
        return

    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=suggestion_keyboard(
                    user_id=user_id,
                    is_banned=is_user_banned(user_id),
                    is_accepted=True,
                )
            )

        except TelegramNetworkError as error:
            print(
                f"Ошибка изменения кнопки: {error}",
                flush=True,
            )


@dp.callback_query(F.data == "already_accepted")
async def already_accepted(callback: CallbackQuery):
    await callback.answer("Этот стикер уже был принят.")


@dp.callback_query(F.data.startswith("reject_suggestion:"))
async def reject_suggestion(
    callback: CallbackQuery,
    bot: Bot,
):
    if callback.from_user.id != SUGGESTIONS_USER_ID:
        await callback.answer(
            "У вас нет прав для этого действия.",
            show_alert=True,
        )
        return

    try:
        user_id = int(callback.data.split(":", 1)[1])

        await bot.send_message(
            chat_id=user_id,
            text="Ваш стикер был отклонён администрацией.",
        )

        await callback.answer(
            "Пользователь уведомлён об отклонении."
        )

    except (ValueError, AttributeError):
        await callback.answer(
            "Неверный ID пользователя.",
            show_alert=True,
        )
        return

    except Exception as error:
        print(
            f"Ошибка уведомления об отклонении: {error}",
            flush=True,
        )

        await callback.answer(
            "Не удалось уведомить пользователя.",
            show_alert=True,
        )
        return

    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=suggestion_keyboard(
                    user_id=user_id,
                    is_banned=is_user_banned(user_id),
                    is_rejected=True,
                )
            )

        except TelegramNetworkError as error:
            print(
                f"Ошибка изменения кнопки: {error}",
                flush=True,
            )


@dp.callback_query(F.data == "already_rejected")
async def already_rejected(callback: CallbackQuery):
    await callback.answer("Этот стикер уже был отклонён.")


@dp.callback_query(F.data.startswith("ban_suggestion:"))
async def ban_suggestion_user(callback: CallbackQuery):
    if callback.from_user.id != SUGGESTIONS_USER_ID:
        await callback.answer(
            "У вас нет прав для этого действия.",
            show_alert=True,
        )
        return

    try:
        user_id = int(callback.data.split(":", 1)[1])

    except (ValueError, AttributeError):
        await callback.answer(
            "Неверный ID пользователя.",
            show_alert=True,
        )
        return

    ban_until = (
        datetime.now(timezone.utc)
        + timedelta(days=BAN_DAYS)
    )

    banned_users[user_id] = ban_until.isoformat()
    save_banned_users(banned_users)

    await callback.answer(
        f"Пользователь заблокирован на {BAN_DAYS} дней."
    )

    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=suggestion_keyboard(
                    user_id=user_id,
                    is_banned=True,
                )
            )

        except TelegramNetworkError as error:
            print(
                f"Ошибка изменения кнопки: {error}",
                flush=True,
            )


@dp.callback_query(F.data.startswith("unban_suggestion:"))
async def unban_suggestion_user(callback: CallbackQuery):
    if callback.from_user.id != SUGGESTIONS_USER_ID:
        await callback.answer(
            "У вас нет прав для этого действия.",
            show_alert=True,
        )
        return

    try:
        user_id = int(callback.data.split(":", 1)[1])

    except (ValueError, AttributeError):
        await callback.answer(
            "Неверный ID пользователя.",
            show_alert=True,
        )
        return

    banned_users.pop(user_id, None)
    save_banned_users(banned_users)

    await callback.answer("Пользователь разблокирован.")

    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=suggestion_keyboard(
                    user_id=user_id,
                    is_banned=False,
                )
            )

        except TelegramNetworkError as error:
            print(
                f"Ошибка изменения кнопки: {error}",
                flush=True,
            )


@dp.message()
async def handle_sticker(
    message: Message,
    bot: Bot,
):
    if message.chat.type not in {"group", "supergroup"}:
        return

    if message.from_user is None:
        return

    try:
        if await is_admin(message, bot):
            return

    except Exception as error:
        print(
            f"Ошибка проверки администратора: {error}",
            flush=True,
        )
        return

    if message.animation is not None:
        await mute_user(message, bot)
        await send_sanction_message(message, bot)
        return

    if message.sticker is None:
        return

    sticker_pack_name = message.sticker.set_name or ""

    if sticker_pack_name == ALLOWED_PACK_NAME:
        return

    await mute_user(message, bot)
    await send_sanction_message(message, bot)


async def main():
    token = os.getenv("BOT_TOKEN")

    if not token:
        raise RuntimeError(
            "Не указана переменная окружения BOT_TOKEN"
        )

    session = AiohttpSession(timeout=120)

    bot = Bot(
        token=token,
        session=session,
    )

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
