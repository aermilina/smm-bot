from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.inline import account_type_kb
from bot.states import PostFlow

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PostFlow.waiting_account_type)
    await message.answer(
        "👋 Hi! I'm your AI SMM manager.\n\nWhich account are we posting for?",
        reply_markup=account_type_kb(),
    )
