from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def account_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✈️ Travel", callback_data="account:travel")
    builder.button(text="🎨 Kids Art", callback_data="account:kids_art")
    builder.button(text="🐶 Dog", callback_data="account:dog")
    builder.adjust(3)
    return builder.as_markup()


def content_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 Post", callback_data="type:post")
    builder.button(text="🎞 Carousel", callback_data="type:carousel")
    builder.button(text="🎬 Reels", callback_data="type:reels")
    builder.adjust(3)
    return builder.as_markup()


def filter_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎞 Vintage", callback_data="filter:vintage")
    builder.button(text="✨ Bright", callback_data="filter:bright")
    builder.button(text="⚫ B&W", callback_data="filter:bw")
    builder.button(text="🌅 Warm", callback_data="filter:warm")
    builder.button(text="❄️ Cool", callback_data="filter:cool")
    builder.button(text="🚫 No filter", callback_data="filter:none")
    builder.adjust(3)
    return builder.as_markup()


def overlay_choice_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🖼 Banner bottom", callback_data="overlay:banner")
    builder.button(text="☝️ Banner top", callback_data="overlay:top")
    builder.button(text="💫 Shadow", callback_data="overlay:shadow")
    builder.button(text="🚫 No overlay", callback_data="overlay:no")
    builder.adjust(3, 1)
    return builder.as_markup()


def preview_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Regenerate text", callback_data="preview:regenerate")
    builder.button(text="🎨 Change filter", callback_data="preview:change_filter")
    builder.button(text="✏️ Change overlay", callback_data="preview:change_overlay")
    builder.button(text="🎬 Change format", callback_data="preview:change_format")
    builder.adjust(1, 2, 1)
    return builder.as_markup()


def youtube_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="▶️ Yes, add link", callback_data="youtube:yes")
    builder.button(text="🚫 No", callback_data="youtube:no")
    builder.adjust(2)
    return builder.as_markup()


def cover_preview_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Done", callback_data="cover:done")
    builder.button(text="✏️ Change title", callback_data="cover:edit_title")
    builder.button(text="✏️ Change subtitle", callback_data="cover:edit_subtitle")
    builder.adjust(1)
    return builder.as_markup()


def reel_format_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Ken Burns", callback_data="format:ken_burns")
    builder.button(text="⚡ Fast cut", callback_data="format:fast_cut")
    builder.button(text="🎣 Hook + slides", callback_data="format:hook_slides")
    builder.adjust(1)
    return builder.as_markup()
