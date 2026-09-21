"""结果展示视图。

把「筛选控件 + 折线图 + 数据表 + 下载按钮」的渲染逻辑抽成独立模块，
既让 app.py 更清爽，也便于用 Streamlit AppTest 单独测试渲染路径。

两处体验要点：
- 未勾选品种 / 药房时，不再只显示一行灰字提示，而是渲染「虚线占位图框」，
  让用户明确知道此处本应有折线图，并给出「▶ 先看前 N 个组合」一键预览按钮。
- 数据表默认展开，避免用户以为只有图、看不到明细。
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

# 「快速预览」按钮一次勾选的组合数
QUICK_PICK_COMBOS = 6

# 占位图框样式：虚线边框 + 浅色底，看起来就是"这里本来有一张图"
_PLACEHOLDER_CSS = """<style>
    .chart-placeholder {
        border: 2px dashed #c7d0d9;
        border-radius: 10px;
        background: linear-gradient(180deg, #fbfcfd 0%, #f3f7fa 100%);
        padding: 2rem 1.5rem;
        text-align: center;
        margin: 0.25rem 0 0.75rem 0;
    }
    .chart-placeholder .ph-icon { font-size: 2.1rem; line-height: 1; margin-bottom: .5rem; }
    .chart-placeholder .ph-title { color: #2c3e50; font-size: 1.05rem; font-weight: 600; margin-bottom: .5rem; }
    .chart-placeholder .ph-desc { color: #5a6b7b; font-size: .88rem; line-height: 1.8; }
    .chart-placeholder .ph-kbd {
        display: inline-block; padding: 0 .35rem; margin: 0 .1rem;
        border: 1px solid #cfd8e3; border-radius: 4px;
        background: #eef2f7; color: #34495e; font-size: .82rem;
    }
</style>"""


def decide_preselect(all_medics, all_stores, limit: int = COMBO_PRESELECT_LIMIT):
    """决定筛选控件默认值。

    Returns:
        (是否预选全部, 默认品种列表, 默认药房列表)
    """
    total = len(all_medics) * len(all_stores)
    if total <= limit:
        return True, list(all_medics), list(all_stores)
    return False, [], []


def pick_first_combos(all_medics, all_stores, max_combos: int = QUICK_PICK_COMBOS):
    """取「前 N 个组合」对应的最小勾选集合，且保证曲线数不超过 N。

    曲线数 = 选中品种 × 选中药房（笛卡尔积），所以两边要一起放大：
    在「品种数 × 药房数 <= max_combos」的前提下取乘积最大的搭配
    （并列时优先多取药房，即让同一品种的不同药房互相比较）。

    例：2 个品种 × 28 个药房、上限 6 -> 1 个品种 × 6 个药房 = 6 条曲线，
    而不是把 6 个品种全勾上导致画出几十条线。

    Args:
        all_medics: 全部品种（有序）
        all_stores: 全部药房（有序）
        max_combos: 期望的组合条数上限

    Returns:
        (品种列表, 药房列表)
    """
    if not all_medics or not all_stores or max_combos < 1:
        return [], []

    best_medics, best_stores, best_total = [], [], 0
    for n_stores in range(min(len(all_stores), max_combos), 0, -1):
        n_medics = min(len(all_medics), max_combos // n_stores)
        total = n_medics * n_stores
        if total > best_total:
            best_total, best_medics, best_stores = total, n_medics, n_stores
    return list(all_medics[:best_medics]), list(all_stores[:best_stores])


def _scope_text(all_medics, all_stores) -> str:
    """占位框里的数据规模描述。"""
    if all_medics and all_stores:
        return (
            f"当前数据共 {len(all_medics)} 个品种 × {len(all_stores)} 个药房"
            f" = {len(all_medics) * len(all_stores)} 个组合"
        )
    if all_medics:
        return f"当前数据共 {len(all_medics)} 个品种"
    if all_stores:
        return f"当前数据共 {len(all_stores)} 个药房"
    return ""


def chart_placeholder_html(metric_title: str, all_medics, all_stores) -> str:
    """未选择品种 / 药房时的图表占位框。

    目的：即使没勾选任何筛选条件，用户也能一眼看到"这里本应有一张折线图"，
    并知道该怎么把它画出来（而不是只看到一句灰字提示）。
    """
    scope = _scope_text(all_medics, all_stores)
    scope_line = f"{scope}。<br/>" if scope else ""
    return f"""
<div class="chart-placeholder">
  <div class="ph-icon">📈</div>
  <div class="ph-title">趋势折线图 · {metric_title}</div>
  <div class="ph-desc">
    {scope_line}
    请在上方 <span class="ph-kbd">选择品种（药品）</span>
    <span class="ph-kbd">选择药房（药店）</span> 后，
    此处会为每个「品种 · 药房」组合绘制一条趋势曲线（X 轴 = 月份，Y 轴 = {metric_title}）。<br/>
    也可以点上方 <b>▶ 先看前 {QUICK_PICK_COMBOS} 个组合</b> 一键预览。<br/>
    出图后：单击曲线或图例项可高亮该曲线、其余淡化；按住 Shift 单击可多选；双击空白处复位。
  </div>
</div>
"""


def _render_chart(chart) -> None:
    """跨 Streamlit 版本渲染 Altair 图（新版用 width='stretch'）。"""
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:
        st.altair_chart(chart, use_container_width=True)


def _apply_quick_pick(all_medics, all_stores) -> None:
    """「快速预览」按钮回调：勾选前 N 个组合（回调在重跑前执行，故可直接改 session_state）。"""
    medics, stores = pick_first_combos(all_medics, all_stores)
    st.session_state["sel_medics"] = medics
    st.session_state["sel_stores"] = stores


def render_results(results: dict) -> None:
    """渲染整个结果区。

    结构：
        全局筛选（品种 / 药房，组合数少时默认全选）
        -> 一键下载（所有结果写入同一 Excel 的不同 Sheet）
        -> 逐分析卡片：折线图（未勾选时显示占位图框）+ 数据表（默认展开）+ 单独下载
    """
    if not results:
        return

    st.markdown(
        '<p class="step-header">第五步：趋势图与结果下载</p>',
        unsafe_allow_html=True,
    )
    st.markdown(_PLACEHOLDER_CSS, unsafe_allow_html=True)

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
        # 控件创建前写入默认值（官方推荐写法，避免 default= 与 session_state 打架），
        # 同时让「快速预览」按钮的回调可以直接改写这两项取值。
        # 若 session_state 里残留了已不存在的旧选项，多选框会自动过滤，不会报错（已实测）。
        if "sel_medics" not in st.session_state:
            st.session_state["sel_medics"] = list(default_medics)
        if "sel_stores" not in st.session_state:
            st.session_state["sel_stores"] = list(default_stores)

        fcol1, fcol2 = st.columns(2)
        sel_medics = fcol1.multiselect(
            "选择品种（药品）", all_medics, key="sel_medics"
        )
        sel_stores = fcol2.multiselect(
            "选择药房（药店）", all_stores, key="sel_stores"
        )

        if not preselect_all:
            total = len(all_medics) * len(all_stores)
            st.caption(
                f"共 {len(all_medics)} 个品种 × {len(all_stores)} 个药房 = {total} 个组合，"
                f"为避免图表拥挤已默认不勾选，请在上方选择要展示的品种 / 药房。"
            )

        # 只要当前选不出一条曲线，就给一个「快速预览」入口，避免作图功能被埋没
        if (not preselect_all) or (not sel_medics) or (not sel_stores):
            st.button(
                f"▶ 先看前 {QUICK_PICK_COMBOS} 个组合（快速预览）",
                key="quick_pick",
                on_click=_apply_quick_pick,
                args=(all_medics, all_stores),
                help=f"自动勾选前 {QUICK_PICK_COMBOS} 个「品种 · 药房」组合，立即生成折线图",
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
                    elif (all_medics or all_stores) and (not sel_medics or not sel_stores):
                        # 有可选项但没勾选 -> 用占位图框告诉用户这里有折线图功能
                        st.markdown(
                            chart_placeholder_html(metric_col, all_medics, all_stores),
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info("当前筛选条件下没有可绘制的数据，请重新选择品种 / 药房。")

                # 数据表（默认展开）
                with st.expander("查看数据表", expanded=True):
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
