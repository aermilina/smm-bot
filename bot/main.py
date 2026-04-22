import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import settings
from bot.handlers import cover, flow, start
from bot.middlewares.album import AlbumMiddleware
from services.gemini import setup_gemini


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    setup_gemini(settings.get_gemini_keys())

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    await bot.set_my_commands([
        BotCommand(command="start", description="Start / choose account"),
        BotCommand(command="cover", description="Generate reel cover"),
    ])

    flow.router.message.middleware(AlbumMiddleware())

    dp.include_router(start.router)
    dp.include_router(cover.router)
    dp.include_router(flow.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
