"""患者服务部数据分析工具 —— Streamlit Web 应用。

相比原版的主要改进：
1. 单次运算可同时获得多种分析结果，下载任一结果不会清空其它结果。
2. 提供「数据模板」下载，降低新用户误传格式的风险。
3. Store / Medic 作为可选分组维度，用户可在 UI 上自由开启/关闭。
4. T-2 按日历月推算（业务确认）。
5. 文件仅读取一次后传入各分析函数，避免重复 IO。
6. 上传后做列名校验，错误提示更友好。
"""

import streamlit as st
import pandas as pd
import tempfile
import os
import io
import importlib

from data_loader import load_and_clean, build_group_cols, DataValidationError

st.set_page_config(page_title="患者服务部数据分析工具", layout="wide")

# ========== 自定义CSS ==========
st.markdown("""
<style>
    .main-title { color: #2c3e50; text-align: center; font-size: 2.5rem; margin-bottom: 1rem; }
    .sub-header { color: #34495e; font-size: 1.2rem; margin-bottom: 1.5rem; }
    .checkbox-container { background-color: #f8f9fa; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; }
    .result-card { background-color: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 2rem; }
    .stDownloadButton button { background-color: #27ae60; color: white; border: none; border-radius: 5px; padding: 0.5rem 1rem; font-weight: bold; }
    .stDownloadButton button:hover { background-color: #2ecc71; }
    .step-header { color: #34495e; font-weight: 500; margin-top: 1rem; margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)

st.title("患者服务部数据分析工具")
st.markdown("上传 Excel 文件（含 TIME / ID / Quantity 字段，可选 Store / Medic），选择分组维度与分析类型，即可获得结果。")

# 分析类型 -> 模块/函数
ANALYSIS_TYPES = {
    "复购率分析": {"module": "repurchase_analysis", "function": "calculate_medic_repurchase"},
    "脱落分析":   {"module": "dropout_logic", "function": "calculate_dropout_rate"},
    "DOT分析":    {"module": "dot_logic", "function": "calculate_dot"},
    "新患分析":   {"module": "new_patient_logic", "function": "calculate_new_patient_rate"},
}


# ========== 第一步：下载模板 ==========
st.markdown('<p class="step-header">第一步：下载数据模板（可选）</p>', unsafe_allow_html=True)
st.markdown("若不确定上传格式，可先下载模板，按模板填写后上传。")


@st.cache_data
def make_template() -> bytes:
    """生成示例模板 Excel，返回字节流。"""
    sample = pd.DataFrame({
        "TIME": ["2024-11-01", "2024-11-01", "2024-12-05"],
        "Medic": ["示例药品A", "示例药品B", "示例药品A"],
        "Quantity": [2, 1, 3],
        "ID": ["患者ID001", "患者ID002", "患者ID001"],
        "Store": ["示例药店甲", "示例药店乙", "示例药店甲"],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        sample.to_excel(writer, index=False, sheet_name="模板")
        # 在第二个 sheet 写字段说明
        note = pd.DataFrame({
            "字段": ["TIME", "Medic", "Quantity", "ID", "Store"],
            "含义": ["销售时间(日期)", "药品名称", "购买数量(可负)", "患者ID", "药店(可选)"],
            "是否必填": ["必填", "可选", "必填", "必填", "可选"],
        })
        note.to_excel(writer, index=False, sheet_name="字段说明")
    return buf.getvalue()


template_bytes = make_template()
st.download_button(
    label="📥 下载数据模板",
    data=template_bytes,
    file_name="数据模板.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)


# ========== 第二步：选择分组维度 ==========
st.markdown('<p class="step-header">第二步：选择分组维度</p>', unsafe_allow_html=True)
col_store, col_medic = st.columns(2)
use_store = col_store.checkbox("按药店分组 (Store)", value=True, help="取消则所有药店合并为一组")
use_medic = col_medic.checkbox("按药品分组 (Medic)", value=True, help="取消则所有药品合并为一组")


# ========== 第三步：选择分析类型（可多选） ==========
st.markdown('<p class="step-header">第三步：选择分析类型（可多选）</p>', unsafe_allow_html=True)
col1, col2 = st.columns(2)
selected_analyses = []
items = list(ANALYSIS_TYPES.items())
half = len(items) // 2
for i, (name, info) in enumerate(items):
    with col1 if i < half else col2:
        if st.checkbox(name, key=f"chk_{name}"):
            selected_analyses.append(name)


# ========== 第四步：上传文件 ==========
st.markdown('<p class="step-header">第四步：上传数据</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("请上传Excel文件", type=["xlsx", "xls"])

# ---- 状态管理：仅在「新文件」出现时清理旧结果 ----
if uploaded_file is not None:
    # 用 (文件名, 文件大小) 作为文件指纹，区分是否同一文件
    file_id = (uploaded_file.name, uploaded_file.size)

    if st.session_state.get("file_id") != file_id:
        # 新文件 -> 保存临时副本并清空历史结果
        if 'input_path' in st.session_state and os.path.exists(st.session_state['input_path']):
            os.unlink(st.session_state['input_path'])
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_input:
            tmp_input.write(uploaded_file.getvalue())
            st.session_state['input_path'] = tmp_input.name
        st.session_state['file_id'] = file_id
        # 仅在新文件时清空，下载等操作不会触发
        if 'results' in st.session_state:
            del st.session_state['results']
        st.success(f"已上传文件：{uploaded_file.name}")
    # 同一文件：保持不变，保留已有分析结果
else:
    # 用户移除了文件 -> 清理所有状态
    if 'input_path' in st.session_state:
        if os.path.exists(st.session_state['input_path']):
            os.unlink(st.session_state['input_path'])
        del st.session_state['input_path']
    for k in ('file_id', 'results'):
        if k in st.session_state:
            del st.session_state[k]


# ========== 上传后列名校验 ==========
if 'input_path' in st.session_state:
    try:
        from data_loader import COLUMN_MAPPING, REQUIRED_COLUMNS
        preview = pd.read_excel(st.session_state['input_path'], nrows=5)
        mapped = [COLUMN_MAPPING.get(c, c) for c in preview.columns]
        missing = [c for c in REQUIRED_COLUMNS if c not in mapped]
        if missing:
            st.error(f"文件缺少必需字段：{missing}。请使用上方「下载数据模板」检查列名。")
    except Exception as e:
        st.error(f"文件读取失败：{e}")


# ========== 开始分析按钮 ==========
if st.button("🚀 开始分析", type="primary"):
    if 'input_path' not in st.session_state:
        st.warning("请先上传文件")
    elif not selected_analyses:
        st.warning("请至少选择一种分析类型")
    else:
        with st.spinner("正在计算中，请稍候..."):
            # 读取并清洗一次
            try:
                df = load_and_clean(st.session_state['input_path'], use_store, use_medic)
            except DataValidationError as e:
                st.error(str(e))
                st.stop()
            except Exception as e:
                st.error(f"数据加载失败：{e}")
                st.stop()

            if df.empty:
                st.error("清洗后无有效数据，请检查 TIME / ID / Quantity 字段是否有空值。")
                st.stop()

            group_cols = build_group_cols(use_store, use_medic, df)

            # 调用各分析函数
            results = {}
            for analysis_name in selected_analyses:
                try:
                    module_info = ANALYSIS_TYPES[analysis_name]
                    module = importlib.import_module(module_info["module"])
                    func = getattr(module, module_info["function"])
                    result_df = func(df, group_cols)
                    results[analysis_name] = result_df if (result_df is not None and not result_df.empty) else None
                except Exception as e:
                    st.error(f"{analysis_name} 计算失败：{e}")
                    results[analysis_name] = None

            st.session_state['results'] = results
            st.success("分析完成！可分别下载各结果，互不影响。")


# ========== 显示结果（下载不触发清零） ==========
if 'results' in st.session_state and st.session_state['results']:
    for analysis_name, result_df in st.session_state['results'].items():
        with st.container():
            st.markdown('<div class="result-card">', unsafe_allow_html=True)
            st.subheader(f"📈 {analysis_name} 结果")

            if result_df is not None and not result_df.empty:
                st.dataframe(result_df)

                # 用 BytesIO 直接下载，避免临时文件残留
                buf = io.BytesIO()
                result_df.to_excel(buf, index=False)
                buf.seek(0)
                st.download_button(
                    label=f"📥 下载 {analysis_name} 结果",
                    data=buf.getvalue(),
                    file_name=f"{analysis_name}_结果.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{analysis_name}",
                )
            else:
                st.warning(f"{analysis_name} 计算完成，但结果为空。请检查输入数据格式。")

            st.markdown('</div>', unsafe_allow_html=True)
