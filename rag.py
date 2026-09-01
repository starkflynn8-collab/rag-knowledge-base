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
        #-----------向量数据库获取一个retriever,负责检索-----------------------
        retriever = self.vector_service.get_retriever()

        #-----------将retriever返回的List[document]——> str字符串 -------------------
        def format_document(docs:list[Document]):
            if not docs:
                return "无相关资料"

            formatted_str = ""
            for doc in docs:
                formatted_str += f"文档片段：{doc.page_content}\n文档元数据：{doc.metadata}\n\n"
            # ----------提取 page_content 和 metadata 拼接成字符串 -----------------
            return formatted_str

        #--------输入：“用户问题 + 对话历史” ——> 输出：用户问题 ——> retriever ------------
        def format_for_retriever(value: dict) -> str:
            return value["input"]

        #--------把复杂输入（历史会话 + 检索内容）转化成Prompt需要的结构-----------------------------
        def format_for_prompt_template(value):
            # value结构：{"input":{"input":"xxx","history":[...]} , "context":"检索出来的参考资料字符串"}
            new_value = {}
            new_value["input"] = value["input"]["input"]  # 当前用户问题
            new_value["context"] = value["context"]  # 检索得到的参考资料
            new_value["history"] = value["input"]["history"]  # 对话历史消息
            return new_value

        def print_prompt(prompt):
            print("=" * 50)
            print(prompt.to_string())
            print("=" * 50)
            return prompt

        chain = (
                {
                    "input": RunnablePassthrough(),
                    "context": RunnableLambda(format_for_retriever) | retriever | format_document
                }
                | RunnableLambda(format_for_prompt_template)
                | self.prompt_template
                | print_prompt
                | self.chat_model
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

    res = RagService().chain.invoke({"input":"简单介绍下ZRDDS"},config.session_config)
    print(res)
