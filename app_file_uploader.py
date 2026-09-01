import os
import tempfile
import streamlit as st
from knowledge_base import KnowledgeBaseService
from document_loader import DocumentLoaderService


st.title("知识库更新服务")
st.divider()

# 支持的文件类型
SUPPORTED_TYPES = ["pdf", "txt", "csv", "docx", "html", "htm"]

uploaded_file = st.file_uploader(
    "请上传知识库文件",
    type=SUPPORTED_TYPES,
    accept_multiple_files=False,
)

# 初始化知识库服务
if "service" not in st.session_state:
    st.session_state["service"] = KnowledgeBaseService()

# 初始化文件解析服务
if "loader" not in st.session_state:
    st.session_state["loader"] = DocumentLoaderService()


if uploaded_file is not None:

    file_name = uploaded_file.name
    file_type = uploaded_file.type
    file_size = uploaded_file.size / 1024

    st.subheader(f"文件名：{file_name}")
    st.write(
        f"格式：{file_type} | "
        f"大小：{file_size:.2f} KB"
    )

    # 获取文件后缀
    suffix = os.path.splitext(file_name)[1].lower()

    try:

        # Streamlit 上传的文件是 UploadedFile，
        # Loader 更方便处理文件路径，
        # 所以先保存为临时文件
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp_file:

            temp_file.write(uploaded_file.getvalue())
            temp_path = temp_file.name

        with st.spinner("解析文件并载入知识库中..."):

            # 文件 → List[Document]
            documents = st.session_state["loader"].load(
                temp_path
            )

            # Document → Chunk → Embedding → Chroma
            result = st.session_state["service"].upload_documents(
                documents,
                file_name
            )

        st.success(result)

        # 显示解析结果
        st.write(f"解析得到 {len(documents)} 个文档片段")

    except Exception as e:

        st.error(f"文件处理失败：{e}")

    finally:

        # 删除临时文件
        if "temp_path" in locals() and os.path.exists(temp_path):
            os.remove(temp_path)