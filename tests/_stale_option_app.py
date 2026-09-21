"""AppTest 专用：验证「多选框拿到已失效旧值」时的行为（不是用户页面）。

背景：views.py 在创建筛选框之前会把默认值写进 session_state。
当上传的文件或分组维度改变后，session_state 里可能残留「已不在 options 中」的取值。
代码依赖「Streamlit 会自动过滤掉这些失效值、不报错」这一实测结论，
所以这里用探针应用把它固化成回归测试。

仅供 tests/smoke_app.py 使用。
"""

import streamlit as st

# 预置一个"已失效"的取值（"z" 不在 options 里）
st.session_state["probe_multi"] = ["a", "z"]
st.multiselect("探针多选框", ["a", "b"], key="probe_multi")
