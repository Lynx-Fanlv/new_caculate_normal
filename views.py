"""结果展示视图。

把「筛选控件 + 折线图 + 数据表 + 下载按钮」的渲染逻辑抽成独立模块，
既让 app.py 更清爽，也便于用 Streamlit AppTest 单独测试渲染路径。
"""

import io
from datetime import datetime

import streamlit as st

from export_utils import build_multi_sheet_excel
from charts import prepare_chart_df, build_line_chart

# 每个分析对应的核心指标列（折线图 Y 轴）；percent=True 表示按百分比展示
ANALYSIS_METRIC = {
    "复购率分析": {"col": "复购率", "percent": True},
    "脱落分析":   {"col": "脱落率", "percent": True},
    "DOT分析":    {"col": "DOT",   "percent": False},
    "新患分析":   {"col": "新患率", "percent": True},
}

# 组合数上限：不超过则默认全选；超过则默认不选，避免首屏折线过多糊成一团
COMBO_PRESELECT_LIMIT = 10


def decide_preselect(all_medics, all_stores, limit: int = COMBO_PRESELECT_LIMIT):
    """决定筛选控件默认值。

    Returns:
        (是否预选全部, 默认品种列表, 默认药房列表)
    """
    total = len(all_medics) * len(all_stores)
    if total <= limit:
        return True, list(all_medics), list(all_stores)
    return False, [], []


def _render_chart(chart) -> None:
    """跨 Streamlit 版本渲染 Altair 图（新版用 width='stretch'）。"""
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:
        st.altair_chart(chart, use_container_width=True)


def render_results(results: dict) -> None:
    """渲染整个结果区。

    结构：
        全局筛选（品种 / 药房，默认全选）
        -> 一键下载（所有结果写入同一 Excel 的不同 Sheet）
        -> 逐分析卡片：折线图 + 可折叠数据表 + 单独下载
    """
    if not results:
        return

    st.markdown(
        '<p class="step-header">第五步：趋势图与结果下载</p>',
        unsafe_allow_html=True,
    )

    # ---- 全局筛选选项：从所有结果里汇总品种 / 药房 ----
    all_medics, all_stores = set(), set()
    for rdf in results.values():
        if rdf is None or rdf.empty:
            continue
        if '药品名称' in rdf.columns:
            all_medics.update(map(str, rdf['药品名称'].dropna().unique().tolist()))
        if '药店' in rdf.columns:
            all_stores.update(map(str, rdf['药店'].dropna().unique().tolist()))
    all_medics = sorted(all_medics)
    all_stores = sorted(all_stores)

    # ---- 智能默认：组合数过多时不预选，避免首屏折线糊成一团 ----
    preselect_all, default_medics, default_stores = decide_preselect(all_medics, all_stores)

    sel_medics, sel_stores = default_medics, default_stores
    if all_medics or all_stores:
        fcol1, fcol2 = st.columns(2)
        sel_medics = fcol1.multiselect(
            "选择品种（药品）", all_medics, default=default_medics, key="sel_medics"
        )
        sel_stores = fcol2.multiselect(
            "选择药房（药店）", all_stores, default=default_stores, key="sel_stores"
        )
        if not preselect_all:
            total = len(all_medics) * len(all_stores)
            st.caption(
                f"共 {len(all_medics)} 个品种 × {len(all_stores)} 个药房 = {total} 个组合，"
                f"为避免图表拥挤已默认不勾选，请在上方选择要展示的品种 / 药房。"
            )

    # ---- 一键下载：所有结果写入同一 Excel 的不同 Sheet ----
    _stamp = datetime.now().strftime("%Y%m%d_%H%M")
    st.download_button(
        label="📦 一键下载全部结果（多 Sheet）",
        data=build_multi_sheet_excel(results),
        file_name=f"分析结果汇总_{_stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_all",
    )

    # ---- 逐分析卡片 ----
    for analysis_name, result_df in results.items():
        with st.container():
            st.markdown('<div class="result-card">', unsafe_allow_html=True)
            st.subheader(f"📈 {analysis_name} 结果")

            if result_df is not None and not result_df.empty:
                metric_cfg = ANALYSIS_METRIC.get(analysis_name, {})
                metric_col = metric_cfg.get("col")
                is_percent = metric_cfg.get("percent", False)

                # 折线图：每个「品种 · 药房」组合一条线
                if metric_col and metric_col in result_df.columns:
                    chart_df = prepare_chart_df(
                        result_df, metric_col, sel_medics, sel_stores
                    )
                    chart = build_line_chart(
                        chart_df, metric_col,
                        metric_title=metric_col, percent=is_percent,
                    )
                    if chart is not None:
                        _render_chart(chart)
                        st.caption(
                            "提示：单击某条曲线或图例中的某一项，即可高亮该曲线、其余淡化；"
                            "按住 Shift 单击可同时高亮多条；双击图表空白处复位为全部高亮。"
                        )
                    else:
                        st.info("当前筛选条件下没有可绘制的数据，请重新选择品种 / 药房。")

                # 数据表（默认折叠）
                with st.expander("查看数据表", expanded=False):
                    st.dataframe(result_df)

                # 单独下载该分析结果
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
