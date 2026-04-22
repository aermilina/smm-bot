import asyncio
import io

from typing import Optional

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.keyboards.inline import (
    account_type_kb,
    content_type_kb,
    filter_kb,
    overlay_choice_kb,
    preview_kb,
    reel_format_kb,
    youtube_kb,
)
from bot.states import PostFlow
from services.gemini import DailyQuotaExceededError, generate_content
from services.image_processor import process_image
from services.video_processor import create_reels_video

router = Router()

_FORMAT_LABELS = {
    "ken_burns": "🎬 Ken Burns",
    "fast_cut": "⚡ Fast cut",
    "hook_slides": "🎣 Hook + slides",
}


# ── Step 0: account type ──────────────────────────────────────────────────────

@router.callback_query(PostFlow.waiting_account_type, F.data.startswith("account:"))
async def handle_account_type(callback: CallbackQuery, state: FSMContext) -> None:
    account_type = callback.data.split(":")[1]
    await state.update_data(account_type=account_type)
    await state.set_state(PostFlow.waiting_media)
    await callback.message.edit_text("📸 Send me a photo or video to get started!")
    await callback.answer()


# ── Step 1: receive media ──────────────────────────────────────────────────────

@router.message(PostFlow.waiting_media, F.photo | F.video)
async def handle_media(
    message: Message,
    state: FSMContext,
    bot: Bot,
    album: Optional[list[Message]] = None,
) -> None:
    messages = album or [message]

    media_list: list[bytes] = []
    for msg in messages:
        if msg.photo:
            file_id = msg.photo[-1].file_id
        elif msg.video:
            file_id = msg.video.file_id
        else:
            continue
        file = await bot.get_file(file_id)
        buf = io.BytesIO()
        await bot.download_file(file.file_path, buf)
        media_list.append(buf.getvalue())

    media_type = "photo" if message.photo else "video"
    await state.update_data(
        media_bytes=media_list[0],
        media_list=media_list,
        media_type=media_type,
    )
    await state.set_state(PostFlow.waiting_topic)

    count = len(media_list)
    suffix = f" ({count} files received, using the first one)" if count > 1 else ""
    await message.answer(f"✍️ What's the topic or brief description for this post?{suffix}")


@router.message(PostFlow.waiting_media)
async def handle_media_wrong(message: Message) -> None:
    await message.answer("Please send a 📸 photo or 🎬 video.")


# ── Step 2: topic ──────────────────────────────────────────────────────────────

@router.message(PostFlow.waiting_topic)
async def handle_topic(message: Message, state: FSMContext) -> None:
    await state.update_data(topic=message.text)
    await state.set_state(PostFlow.waiting_content_type)
    await message.answer("Choose content type:", reply_markup=content_type_kb())


# ── Step 3: content type ───────────────────────────────────────────────────────

@router.callback_query(PostFlow.waiting_content_type, F.data.startswith("type:"))
async def handle_content_type(callback: CallbackQuery, state: FSMContext) -> None:
    content_type = callback.data.split(":")[1]
    await state.update_data(content_type=content_type)
    await state.set_state(PostFlow.waiting_filter)
    await callback.message.edit_text("🎨 Choose a filter:", reply_markup=filter_kb())
    await callback.answer()


# ── Step 4: filter ─────────────────────────────────────────────────────────────

@router.callback_query(PostFlow.waiting_filter, F.data.startswith("filter:"))
async def handle_filter(callback: CallbackQuery, state: FSMContext) -> None:
    filter_name = callback.data.split(":")[1]
    data = await state.get_data()
    await state.update_data(filter_name=filter_name)

    if data.get("editing_from_preview"):
        await state.update_data(editing_from_preview=False)
        await _rebuild_preview(callback, state)
    else:
        await state.set_state(PostFlow.waiting_overlay_choice)
        await callback.message.edit_text(
            "✏️ Want to add a text overlay on the photo?",
            reply_markup=overlay_choice_kb(),
        )
    await callback.answer()


# ── Step 5: overlay choice ─────────────────────────────────────────────────────

_OVERLAY_STYLES = {"banner", "top", "shadow"}


@router.callback_query(PostFlow.waiting_overlay_choice, F.data.startswith("overlay:"))
async def handle_overlay_choice(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":")[1]
    data = await state.get_data()

    if data.get("editing_from_preview") and choice == "no":
        await state.update_data(overlay_text=None, overlay_style=None, editing_from_preview=False)
        await _rebuild_preview(callback, state)
        await callback.answer()
        return

    if choice in _OVERLAY_STYLES:
        await state.update_data(overlay_style=choice)
        await state.set_state(PostFlow.waiting_overlay_text)
        await callback.message.edit_text("✏️ Write your overlay text (short, up to 6 words):")
    else:
        await state.update_data(overlay_text=None, overlay_style=None)
        await _ask_youtube_or_generate(callback.message, state, edit=True)
    await callback.answer()


# ── Step 6: overlay text ───────────────────────────────────────────────────────

@router.message(PostFlow.waiting_overlay_text)
async def handle_overlay_text(message: Message, state: FSMContext) -> None:
    await state.update_data(overlay_text=message.text)
    data = await state.get_data()

    if data.get("editing_from_preview"):
        await state.update_data(editing_from_preview=False)
        status = await message.answer("⏳ Processing...")
        loop = asyncio.get_event_loop()
        processed, is_video = await loop.run_in_executor(
            None, lambda: _process_media(data, message.text)
        )
        await state.update_data(processed_image=processed)
        await _send_preview_media(message, state, processed, is_video, status_msg=status)
    else:
        await _ask_youtube_or_generate(message, state, edit=False)


# ── YouTube link (kids_art only) ───────────────────────────────────────────────

@router.callback_query(PostFlow.waiting_youtube_link, F.data.startswith("youtube:"))
async def handle_youtube_choice(callback: CallbackQuery, state: FSMContext) -> None:
    has_video = callback.data.split(":")[1] == "yes"
    await state.update_data(youtube_cta=has_video)
    await callback.message.edit_text("⏳ Generating content, please wait...")
    await _generate_and_send_preview(callback.message, state)
    await callback.answer()


# ── Reel format override (from preview) ───────────────────────────────────────

@router.callback_query(PostFlow.waiting_reel_format, F.data.startswith("format:"))
async def handle_reel_format(callback: CallbackQuery, state: FSMContext) -> None:
    fmt = callback.data.split(":")[1]
    await state.update_data(reel_format=fmt, editing_from_preview=False)
    await _rebuild_preview(callback, state)
    await callback.answer()


# ── Preview actions ────────────────────────────────────────────────────────────

@router.callback_query(PostFlow.preview, F.data.startswith("preview:"))
async def handle_preview_action(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":")[1]
    data = await state.get_data()

    if action == "approve":
        await callback.message.edit_caption(
            callback.message.caption + "\n\n✅ *Approved!*\n\nNext step — publishing to TikTok and Instagram.",
            parse_mode="Markdown",
        )
        await state.clear()

    elif action == "regenerate":
        await _safe_edit_caption(callback.message, "🔄 Generating a new version...")
        try:
            result = await generate_content(
                image_data=data["media_bytes"],
                topic=data["topic"],
                content_type=data["content_type"],
                account_type=data.get("account_type", "travel"),
                additional_instructions="Create a different version, don't repeat the previous one",
            )
            if data.get("content_type") == "reels":
                await state.update_data(
                    reel_format=result.get("reel_format", data.get("reel_format", "ken_burns")),
                    hook_text=result.get("hook_text"),
                )
            await state.update_data(
                caption=result["caption"],
                hashtags=result["hashtags"],
                youtube_cta_text=result.get("youtube_cta_text"),
            )
            data = await state.get_data()
            caption_text = _build_caption(data["caption"], data["hashtags"], data.get("reel_format"), data.get("youtube_cta", False), data.get("youtube_cta_text"))
            await _safe_edit_caption(callback.message, caption_text, parse_mode="Markdown", reply_markup=preview_kb())
        except DailyQuotaExceededError as e:
            await _safe_edit_caption(callback.message, f"⚠️ {e}", reply_markup=preview_kb())
        except Exception as e:
            await _safe_edit_caption(callback.message, f"❌ Generation error: {e}", reply_markup=preview_kb())

    elif action == "change_filter":
        await state.update_data(editing_from_preview=True)
        await state.set_state(PostFlow.waiting_filter)
        await callback.message.answer("🎨 Choose a new filter:", reply_markup=filter_kb())

    elif action == "change_overlay":
        await state.update_data(editing_from_preview=True)
        await state.set_state(PostFlow.waiting_overlay_choice)
        await callback.message.answer("✏️ Change the photo overlay?", reply_markup=overlay_choice_kb())

    elif action == "change_format":
        if data.get("content_type") != "reels":
            await callback.answer("Format is only available for Reels", show_alert=True)
            return
        current = _FORMAT_LABELS.get(data.get("reel_format", "ken_burns"), "Ken Burns")
        await state.update_data(editing_from_preview=True)
        await state.set_state(PostFlow.waiting_reel_format)
        await callback.message.answer(
            f"🎬 Choose reel format (current: {current}):",
            reply_markup=reel_format_kb(),
        )

    await callback.answer()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _safe_edit_caption(message: Message, text: str, **kwargs) -> None:
    try:
        await message.edit_caption(text, **kwargs)
    except Exception:
        await message.answer(text, **kwargs)


def _build_caption(
    caption: str,
    hashtags: list[str],
    reel_format: Optional[str] = None,
    youtube_cta: bool = False,
    youtube_cta_text: Optional[str] = None,
) -> str:
    format_line = f"\n_{_FORMAT_LABELS[reel_format]}_" if reel_format in _FORMAT_LABELS else ""
    if youtube_cta:
        cta = f"{youtube_cta_text} — link in bio 🔗" if youtube_cta_text else "Watch also my video about it on YouTube — link in bio 🔗"
        youtube_line = f"\n\n{cta}"
    else:
        youtube_line = ""
    return f"👁 *Preview*{format_line}\n\n{caption}{youtube_line}\n\n{' '.join(hashtags)}"


async def _ask_youtube_or_generate(msg: Message, state: FSMContext, edit: bool) -> None:
    data = await state.get_data()
    if data.get("account_type") == "kids_art" and "youtube_cta" not in data:
        await state.set_state(PostFlow.waiting_youtube_link)
        text = "▶️ Is there a YouTube video for this post?"
        if edit:
            await msg.edit_text(text, reply_markup=youtube_kb())
        else:
            await msg.answer(text, reply_markup=youtube_kb())
    else:
        if edit:
            await msg.edit_text("⏳ Generating content, please wait...")
            await _generate_and_send_preview(msg, state)
        else:
            status = await msg.answer("⏳ Generating content, please wait...")
            await _generate_and_send_preview(status, state)


def _is_reels_video(data: dict) -> bool:
    return data.get("content_type") == "reels" and len(data.get("media_list", [])) > 1


def _process_media(data: dict, overlay_text: Optional[str]) -> tuple[bytes, bool]:
    filter_name = data.get("filter_name", "none")
    overlay_style = data.get("overlay_style", "banner")
    if _is_reels_video(data):
        return create_reels_video(
            data["media_list"],
            filter_name,
            overlay_text,
            overlay_style,
            reel_format=data.get("reel_format", "ken_burns"),
            hook_text=data.get("hook_text"),
        ), True
    return process_image(data["media_bytes"], filter_name, overlay_text, overlay_style), False


async def _generate_and_send_preview(status_msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        result = await generate_content(
            image_data=data["media_bytes"],
            topic=data["topic"],
            content_type=data["content_type"],
            account_type=data.get("account_type", "travel"),
        )
        overlay_text = data["overlay_text"] if "overlay_text" in data else result.get("overlay_text")

        if data.get("content_type") == "reels":
            data["reel_format"] = result.get("reel_format", "ken_burns")
            data["hook_text"] = result.get("hook_text")

        loop = asyncio.get_event_loop()
        processed, is_video = await loop.run_in_executor(
            None, lambda: _process_media(data, overlay_text)
        )
        await state.update_data(
            caption=result["caption"],
            hashtags=result["hashtags"],
            overlay_text=overlay_text,
            reel_format=data.get("reel_format"),
            hook_text=data.get("hook_text"),
            youtube_cta_text=result.get("youtube_cta_text"),
            processed_image=processed,
        )
        await _send_preview_media(status_msg, state, processed, is_video, status_msg=status_msg)

    except DailyQuotaExceededError as e:
        await status_msg.edit_text(f"⚠️ {e}")
        await state.clear()
    except Exception as e:
        await status_msg.edit_text(f"❌ Generation error: {e}\n\nStart over — /start")
        await state.clear()


async def _send_preview_media(
    message: Message,
    state: FSMContext,
    processed: bytes,
    is_video: bool,
    status_msg: Message = None,
) -> None:
    data = await state.get_data()
    caption_text = _build_caption(data["caption"], data["hashtags"], data.get("reel_format"), data.get("youtube_cta", False), data.get("youtube_cta_text"))
    await state.set_state(PostFlow.preview)

    if is_video:
        await message.answer_video(
            video=BufferedInputFile(processed, filename="reels.mp4"),
            caption=caption_text,
            parse_mode="Markdown",
            reply_markup=preview_kb(),
        )
    else:
        await message.answer_photo(
            photo=BufferedInputFile(processed, filename="preview.jpg"),
            caption=caption_text,
            parse_mode="Markdown",
            reply_markup=preview_kb(),
        )

    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass


async def _rebuild_preview(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    loop = asyncio.get_event_loop()
    processed, is_video = await loop.run_in_executor(
        None, lambda: _process_media(data, data.get("overlay_text"))
    )
    await state.update_data(processed_image=processed)
    caption_text = _build_caption(data["caption"], data["hashtags"], data.get("reel_format"), data.get("youtube_cta", False), data.get("youtube_cta_text"))
    await state.set_state(PostFlow.preview)

    if is_video:
        await callback.message.answer_video(
            video=BufferedInputFile(processed, filename="reels.mp4"),
            caption=caption_text,
            parse_mode="Markdown",
            reply_markup=preview_kb(),
        )
    else:
        await callback.message.answer_photo(
            photo=BufferedInputFile(processed, filename="preview.jpg"),
            caption=caption_text,
            parse_mode="Markdown",
            reply_markup=preview_kb(),
        )
