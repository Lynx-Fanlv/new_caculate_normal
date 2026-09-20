"""折线图构建。

设计：
- 每个「品种 · 药房」组合画一条线；
- X 轴为月份，Y 轴为该分析的核心指标（复购率 / 脱落率 / DOT / 新患率）；
- 用户可在 UI 上按品种、药房筛选要显示的线。

依赖 Altair（Streamlit 自带依赖，无需额外安装）。
"""

import pandas as pd

COMBO_COL = "组合"   # 由「药品名称 · 药店」拼接而成
MONTH_COL = "月份"


def prepare_chart_df(
    result_df: pd.DataFrame,
    metric_col: str,
    sel_medics=None,
    sel_stores=None,
) -> pd.DataFrame:
    """从分析结果中筛出绘图数据，并生成用于分色的「组合」列。

    Args:
        result_df:  分析结果表（含 药店 / 药品名称 / 月份 / metric_col）
        metric_col: 该分析的核心指标列名（如 "复购率"）
        sel_medics: 选中的药品列表；None 表示不筛选（全部）
        sel_stores: 选中的药店列表；None 表示不筛选（全部）

    Returns:
        仅含 [月份, 组合, metric_col] 三列的 DataFrame（按组合、月份排序）。
    """
    empty = pd.DataFrame(columns=[MONTH_COL, COMBO_COL, metric_col])
    if result_df is None or len(result_df) == 0:
        return empty
    if metric_col not in result_df.columns:
        return empty

    df = result_df.copy()

    if sel_medics is not None and "药品名称" in df.columns:
        df = df[df["药品名称"].isin(sel_medics)]
    if sel_stores is not None and "药店" in df.columns:
        df = df[df["药店"].isin(sel_stores)]

    if len(df) == 0:
        return empty

    medic = df["药品名称"].astype(str) if "药品名称" in df.columns else "全部药品"
    store = df["药店"].astype(str) if "药店" in df.columns else "全部药店"
    df[COMBO_COL] = medic + " · " + store

    df = df[[MONTH_COL, COMBO_COL, metric_col]].copy()
    df[metric_col] = pd.to_numeric(df[metric_col], errors="coerce")
    df = df.dropna(subset=[metric_col])
    # 月份为 "YYYY-MM" 字符串，字典序即时间序
    df = df.sort_values([COMBO_COL, MONTH_COL]).reset_index(drop=True)
    return df


def build_line_chart(
    chart_df: pd.DataFrame,
    metric_col: str,
    metric_title: str = None,
    percent: bool = False,
):
    """构建 Altair 折线图（每个「组合」一条线）。

    Args:
        chart_df:     prepare_chart_df 的输出
        metric_col:   Y 轴指标列名
        metric_title: Y 轴标题（默认用列名）
        percent:      True 时 Y 轴与提示按百分比显示

    Returns:
        altair.Chart 对象；无数据时返回 None。
    """
    if chart_df is None or len(chart_df) == 0:
        return None

    import altair as alt  # 延迟导入：仅在有数据渲染时才需要

    title = metric_title or metric_col
    fmt = ".1%" if percent else ".4f"
    y_axis = alt.Axis(format=".0%") if percent else alt.Axis()

    chart = (
        alt.Chart(chart_df)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X(
                f"{MONTH_COL}:O",
                title="月份",
                axis=alt.Axis(labelAngle=-45, labelOverlap=True),
            ),
            y=alt.Y(f"{metric_col}:Q", title=title, axis=y_axis),
            color=alt.Color(f"{COMBO_COL}:N", title="品种 · 药房"),
            tooltip=[
                alt.Tooltip(f"{MONTH_COL}:O", title="月份"),
                alt.Tooltip(f"{COMBO_COL}:N", title="品种 · 药房"),
                alt.Tooltip(f"{metric_col}:Q", title=title, format=fmt),
            ],
        )
        .properties(height=360)
        .interactive()
    )
    return chart
