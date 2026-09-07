"""
检索、生成

"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableWithMessageHistory
from file_history_store import get_history
from vector_stores import VectorStoreService
from langchain_ollama import OllamaEmbeddings
import config_data as config
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_community.chat_models.tongyi import ChatTongyi
from citation import format_document_block


#------------------------rag.py 主要负责“检索+生成”--------------------------------
class RagService(object):
    def __init__(self):

        #---------------构建索引，完整过程在vector_stores.py里---------------------------
        self.vector_service = VectorStoreService(
            OllamaEmbeddings(
                model=config.embedding_model_name,
                base_url=config.ollama_base_url,
            )
        )  #-------------文本 ——> Embedding模型 ——> 向量 ------------------------------

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是严谨的 DDS 技术文档问答助手。请仅基于我提供的参考资料回答用户问题，"
                    "不要编造资料之外的内容。回答时在相关句末使用 [n] 标注引用编号，"
                    "n 对应参考资料编号。若资料不足以回答，请明确说明资料不足。\n\n"
                    "参考资料：\n{context}"
                ),
                MessagesPlaceholder("history"),
                ("user","请回答用户提问：{input}")
            ]
        )

        self.chat_model = ChatTongyi(model=config.chat_model_name)

        self.chain = self._get_chain()

    def _get_chain(self):
        def format_document(docs: list[Document]):

            if not docs:
                return "无相关资料"

            formatted_str = ""

            for index, doc in enumerate(docs, start=1):
                formatted_str += format_document_block(index, doc)
                formatted_str += "\n\n"

            return formatted_str

        def format_for_retriever(value: dict) -> str:
            return value["input"]

        def format_for_prompt_template(value):

            new_value = {}

            new_value["input"] = value["input"]["input"]

            new_value["context"] = value["context"]

            new_value["history"] = value["input"]["history"]

            return new_value

        def print_prompt(prompt):
            print("=" * 50)
            print("Prompt 已生成")
            print(f"Prompt 字符数：{len(prompt.to_string())}")
            print("=" * 50)
            return prompt

        chain = (
                {
                    "input": RunnablePassthrough(),

                    "context": (
                            RunnableLambda(format_for_retriever)
                            | RunnableLambda(
                        self.vector_service.search
                    )
                            | RunnableLambda(format_document)
                    )
                }

                | RunnableLambda(format_for_prompt_template)

                | self.prompt_template

                | print_prompt

                | self.chat_model

                | StrOutputParser()
        )

        conversation_chain = RunnableWithMessageHistory(
            chain,
            get_history,
            input_messages_key="input",
            history_messages_key="history",
        )

        return conversation_chain

#测试
if __name__ == "__main__":

    res = RagService().chain.invoke({"input":"简单介绍下基于C++构建ZRDDS的方式"},config.session_config)
    print(res)
