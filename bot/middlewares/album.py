import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message


class AlbumMiddleware(BaseMiddleware):
    """Collects Telegram media group messages and passes them together as `album`."""

    def __init__(self, latency: float = 0.5):
        self.latency = latency
        self._albums: dict[str, list[Message]] = defaultdict(list)
        self._tasks: dict[str, asyncio.Task] = {}

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if not event.media_group_id:
            return await handler(event, data)

        group_id = event.media_group_id
        self._albums[group_id].append(event)

        if group_id in self._tasks:
            self._tasks[group_id].cancel()

        async def fire() -> None:
            await asyncio.sleep(self.latency)
            messages = self._albums.pop(group_id, [])
            self._tasks.pop(group_id, None)
            if messages:
                data["album"] = messages
                await handler(messages[0], data)

        self._tasks[group_id] = asyncio.create_task(fire())
        return None  # suppress individual messages until group is complete
