import streamlit as st
import config_data as config
from rag import RagService


st.title("智能客服")
st.divider()                # 分隔符

# 前端页面状态保存
if "message" not in st.session_state:
    st.session_state["message"] = [{"role": "assistant", "content": "你好，有什么可以帮助你？"}]
# 连接 rag.py
if "rag" not in st.session_state:
    st.session_state["rag"] = RagService()
# 显示已有聊天记录
for message in st.session_state["message"]:
    st.chat_message(message["role"]).write(message["content"])

# 在页面最下方提供用户输入栏
prompt = st.chat_input()

# 用户输入后
if prompt:
    st.chat_message("user").write(prompt)     # 在页面输出用户的提问
    st.session_state["message"].append({"role": "user", "content": prompt}) # 用户问题加入前端历史

    ai_res_list = []

    def capture(generator, cache_list):
        for chunk in generator:
            cache_list.append(chunk.content) # 保存答案到session_state
            yield chunk.content # 实时输出


    with st.chat_message("assistant"):
        with st.spinner("AI思考中..."):
            res_stream = st.session_state["rag"].chain.stream({"input": prompt}, config.session_config)
            output = st.write_stream(capture(res_stream, ai_res_list))

    st.session_state["message"].append({"role": "assistant", "content": "".join(ai_res_list)})

