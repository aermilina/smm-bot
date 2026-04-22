from aiogram.fsm.state import State, StatesGroup


class CoverFlow(StatesGroup):
    waiting_media = State()
    waiting_title = State()
    waiting_subtitle = State()
    preview = State()


class PostFlow(StatesGroup):
    waiting_account_type = State()
    waiting_media = State()
    waiting_topic = State()
    waiting_content_type = State()
    waiting_filter = State()
    waiting_overlay_choice = State()
    waiting_overlay_text = State()
    waiting_youtube_link = State()
    waiting_reel_format = State()
    preview = State()
