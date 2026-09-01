"""
向量库创建，检索器获取
"""

from langchain_chroma import Chroma
import config_data as config
from langchain_community.embeddings import DashScopeEmbeddings


#-----------------------Rag的检索基础设施(Chroma创建，Retriever获取)---------------------
class VectorStoreService(object):
    def __init__(self,embedding):
        self.embedding = embedding  # rag.py传入Embedding模型
    #-----------Chroma 向量数据库 (主要负责检索)--------------------------
        self.vector_store = Chroma(
            collection_name=config.collection_name, # Chroma里的一个知识库集合
            embedding_function=self.embedding,
            persist_directory=config.persist_directory, # Chroma把数据持久化到‘./chroma_db’

        )

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k":config.similarity_threshold})


# ----------------------------测试----------------------------------
if __name__ == "__main__":
    retriever = VectorStoreService(DashScopeEmbeddings(model=config.embedding_model_name)).get_retriever()

    res = retriever.invoke("我的体重180斤，尺码推荐")
    print(res)