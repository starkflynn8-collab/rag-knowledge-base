import json
import os
from pathlib import Path
from typing import Sequence
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict


def get_history(session_id):
    project_root = Path(__file__).resolve().parent
    return FileChatMessageHistory(session_id, str(project_root / "chat_history"))


class FileChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id, storage_path):
        self.session_id = session_id        # 会话id
        self.storage_path = storage_path     # 不同会话id的存储文件，所在的文件夹路径
        # 生成每个会话对应的文件路径 ：storage_path / session_id
        self.file_path = os.path.join(self.storage_path, self.session_id)

        # 确保文件夹是存在的
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    """保存对话到文件"""
    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        # Sequence序列 类似list、tuple
        all_messages = list(self.messages) # 已有的消息列表，包括HumanMessage和AIMessage
        all_messages.extend(messages)               # 新的和已有的融合成一个list
        #序列化：Message对象 ——> Dictionary
        new_messages = [message_to_dict(message) for message in all_messages]
        # 将数据写入文件
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(new_messages, f)

    """从本地JSON文件里读取历史聊天记录，并将其反序列化为Message对象"""
    @property
    def messages(self) -> list[BaseMessage]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                messages_data = json.load(f)   # 返回值就是: list[字典]
                return messages_from_dict(messages_data)
        except FileNotFoundError:
            return []

    def clear(self) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([], f)
