import asyncio
from copy import deepcopy
from uuid import uuid4


class ConversationNotFoundError(KeyError):
    pass


class ConversationStore:
    def __init__(self, system_prompt: str, max_messages: int = 24) -> None:
        self._system_prompt = system_prompt
        self._max_messages = max_messages
        self._conversations: dict[str, list[dict[str, str]]] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> str:
        conversation_id = str(uuid4())
        async with self._lock:
            self._conversations[conversation_id] = [
                {"role": "system", "content": self._system_prompt}
            ]
        return conversation_id

    async def messages(self, conversation_id: str) -> list[dict[str, str]]:
        async with self._lock:
            messages = self._conversations.get(conversation_id)
            if messages is None:
                raise ConversationNotFoundError(conversation_id)
            return deepcopy(messages)

    async def append(self, conversation_id: str, role: str, content: str) -> None:
        async with self._lock:
            messages = self._conversations.get(conversation_id)
            if messages is None:
                raise ConversationNotFoundError(conversation_id)
            messages.append({"role": role, "content": content})
            if len(messages) > self._max_messages:
                self._conversations[conversation_id] = [messages[0], *messages[-(self._max_messages - 1) :]]

    async def delete(self, conversation_id: str) -> bool:
        async with self._lock:
            return self._conversations.pop(conversation_id, None) is not None

