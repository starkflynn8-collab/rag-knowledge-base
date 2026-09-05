"""
检索、生成

"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableWithMessageHistory
from file_history_store import get_history
from vector_stores import VectorStoreService
from langchain_community.embeddings import DashScopeEmbeddings
import config_data as config
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_community.chat_models.tongyi import ChatTongyi



#------------------------rag.py 主要负责“检索+生成”--------------------------------
class RagService(object):
    def __init__(self):

        #---------------构建索引，完整过程在vector_stores.py里---------------------------
        self.vector_service = VectorStoreService(
            embedding=DashScopeEmbeddings(model=config.embedding_model_name),
        )  #-------------文本 ——> Embedding模型 ——> 向量 ------------------------------

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system","以我提供的已知参考资料为主，简洁和专业的回答用户的问题，参考资料：{context}。"),
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

            for doc in docs:
                formatted_str += (
                    f"文档片段：{doc.page_content}\n"
                    f"文档元数据：{doc.metadata}\n\n"
                )

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
                        self.vector_service.hybrid_search
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
