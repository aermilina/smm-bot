import asyncio
import io

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.keyboards.inline import cover_preview_kb
from bot.states import CoverFlow
from services.image_processor import create_cover

router = Router()


@router.message(Command("cover"))
async def cmd_cover(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CoverFlow.waiting_media)
    await message.answer("🖼 Send a photo for the cover.")


@router.message(CoverFlow.waiting_media, F.photo)
async def handle_cover_media(message: Message, state: FSMContext, bot: Bot) -> None:
    file = await bot.get_file(message.photo[-1].file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, buf)
    await state.update_data(media_bytes=buf.getvalue())
    await state.set_state(CoverFlow.waiting_title)
    await message.answer("✏️ Enter the title (e.g. ZRENJANIN):")


@router.message(CoverFlow.waiting_media)
async def handle_cover_media_wrong(message: Message) -> None:
    await message.answer("Please send a 📸 photo.")


@router.message(CoverFlow.waiting_title)
async def handle_cover_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(CoverFlow.waiting_subtitle)
    await message.answer("✏️ Enter the subtitle (e.g. WEEKEND TRIP IDEA):")


@router.message(CoverFlow.waiting_subtitle)
async def handle_cover_subtitle(message: Message, state: FSMContext) -> None:
    await state.update_data(subtitle=message.text.strip())
    await _render_and_send(message, state)


@router.callback_query(CoverFlow.preview, F.data.startswith("cover:"))
async def handle_cover_action(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":")[1]

    if action == "done":
        await callback.message.edit_caption("✅ Cover saved!", reply_markup=None)
        await state.clear()
    elif action == "edit_title":
        await state.set_state(CoverFlow.waiting_title)
        await callback.message.answer("✏️ Enter a new title:")
    elif action == "edit_subtitle":
        await state.set_state(CoverFlow.waiting_subtitle)
        await callback.message.answer("✏️ Enter a new subtitle:")

    await callback.answer()


async def _render_and_send(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    status = await message.answer("⏳ Generating cover...")
    loop = asyncio.get_event_loop()
    cover_bytes = await loop.run_in_executor(
        None,
        lambda: create_cover(data["media_bytes"], data["title"], data.get("subtitle", "")),
    )
    await state.set_state(CoverFlow.preview)
    await message.answer_photo(
        photo=BufferedInputFile(cover_bytes, filename="cover.jpg"),
        caption=f"*{data['title'].upper()}*\n{data.get('subtitle', '').upper()}",
        parse_mode="Markdown",
        reply_markup=cover_preview_kb(),
    )
    try:
        await status.delete()
    except Exception:
        pass
