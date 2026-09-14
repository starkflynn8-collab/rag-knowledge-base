from typing import Iterable
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage

from auth_store import SqliteChatMessageHistory


def get_history(session_id):
    return SqliteChatMessageHistory(session_id)


class FileChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id, storage_path):
        self.session_id = session_id

    def add_messages(self, messages: Iterable[BaseMessage]) -> None:
        SqliteChatMessageHistory(self.session_id).add_messages(messages)

    @property
    def messages(self) -> list[BaseMessage]:
        return SqliteChatMessageHistory(self.session_id).messages

    def clear(self) -> None:
        SqliteChatMessageHistory(self.session_id).clear()
