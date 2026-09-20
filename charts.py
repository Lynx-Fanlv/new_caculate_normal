"""折线图构建。

设计：
- 每个「品种 · 药房」组合画一条线；
- X 轴为月份，Y 轴为该分析的核心指标（复购率 / 脱落率 / DOT / 新患率）；
- 用户可在 UI 上按品种、药房筛选要显示的线。

图例可读性（对应「药房被省略」的问题）：
- Vega-Lite 图例标签默认 160px 上限，超长会被截成「替雷利珠单抗注射液(百…」，
  药房部分完全看不见；这里显式设 labelLimit=0（Vega 中 0 = 不限长度，不截断）。
- 同时把「药品名称」压成易读短名：优先取括号内的商品名，
  例如「替雷利珠单抗注射液(百泽安)」→「百泽安」，
  使「百泽安 · 攀枝花药房(连锁）」这类整条标签保持在一行内、药房名完整可见。
  完整名称仍在 tooltip 中给出。

交互（高亮某条曲线）：
- 单击某条曲线或图例中的某一项 -> 该曲线高亮，其余淡化（单击另一条即切换高亮对象）；
- 按住 Shift 单击可同时高亮多条；双击图表空白处复位为全部高亮。
- 实现方式：一个 point selection 同时绑定 on="click" 与 bind="legend"。
  （已用 vega-lite 编译器实测：编译后信号同时订阅图表点击与图例点击两个事件源）

依赖 Altair（Streamlit 自带依赖，无需额外安装）。
"""

import re

import pandas as pd

COMBO_COL = "组合"      # 由「品种短名 · 药店」拼接而成，用于分色与图例
MONTH_COL = "月份"
MEDIC_COL = "药品名称"
STORE_COL = "药店"

DIMMED_OPACITY = 0.12   # 未选中曲线的透明度（越小越"不明显"）

_PAREN_RE = re.compile(r"[（(]\s*([^（()）]+?)\s*[)）]")
_SHORT_NAME_MAX = 8     # 无括号可提取时，名称的截断长度


def short_medic_name(name) -> str:
    """把较长的药品名压成易读短名（仅用于图例/曲线名，不改变原始数据）。

    - 「替雷利珠单抗注射液(百泽安)」->「百泽安」：优先取括号内的商品名
    - 无括号时：仅在超过 _SHORT_NAME_MAX 时截断，避免误伤本来就短的名字

    Args:
        name: 原始药品名称

    Returns:
        压缩后的短名（可能为空字符串）
    """
    s = str(name).strip()
    if not s:
        return s
    matches = _PAREN_RE.findall(s)
    if matches:
        brand = matches[-1].strip()      # 通常是商品名
        if brand:
            return brand
    return s if len(s) <= _SHORT_NAME_MAX else s[:_SHORT_NAME_MAX] + "…"


def _build_combo_labels(df: pd.DataFrame):
    """生成「品种 · 药房」标签列。

    无 药品名称 / 药店 列时分别退化为「全部药品」/「全部药店」。
    """
    if MEDIC_COL in df.columns:
        medic = df[MEDIC_COL].map(short_medic_name).astype(str)
    else:
        medic = pd.Series("全部药品", index=df.index)

    if STORE_COL in df.columns:
        store = df[STORE_COL].astype(str)
    else:
        store = pd.Series("全部药店", index=df.index)

    return medic + " · " + store


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
        含 [月份, 组合, metric_col(, 药品名称, 药店)] 的 DataFrame（按组合、月份排序）。
        药品名称 / 药店 列在原始表中存在时保留，用于 tooltip 展示完整信息。
    """
    empty = pd.DataFrame(columns=[MONTH_COL, COMBO_COL, metric_col])
    if result_df is None or len(result_df) == 0:
        return empty
    if metric_col not in result_df.columns:
        return empty

    df = result_df.copy()

    if sel_medics is not None and MEDIC_COL in df.columns:
        df = df[df[MEDIC_COL].isin(sel_medics)]
    if sel_stores is not None and STORE_COL in df.columns:
        df = df[df[STORE_COL].isin(sel_stores)]

    if len(df) == 0:
        return empty

    df[COMBO_COL] = _build_combo_labels(df)

    keep = [MONTH_COL, COMBO_COL, metric_col]
    for extra in (MEDIC_COL, STORE_COL):
        if extra in df.columns and extra not in keep:
            keep.append(extra)
    df = df[keep].copy()

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
    highlight: bool = True,
):
    """构建 Altair 折线图（每个「组合」一条线）。

    Args:
        chart_df:     prepare_chart_df 的输出
        metric_col:   Y 轴指标列名
        metric_title: Y 轴标题（默认用列名）
        percent:      True 时 Y 轴与提示按百分比显示
        highlight:    True 时启用「点选曲线/图例 -> 高亮、其余淡化」交互

    Returns:
        altair.Chart 对象；无数据时返回 None。
    """
    if chart_df is None or len(chart_df) == 0:
        return None

    import altair as alt  # 延迟导入：仅在有数据渲染时才需要

    title = metric_title or metric_col
    fmt = ".1%" if percent else ".4f"
    y_axis = alt.Axis(format=".0%") if percent else alt.Axis()

    # 图例：labelLimit=0 -> 不截断（Vega 中 limit<=0 视为不限长度）
    legend = alt.Legend(
        title="品种 · 药房",
        labelLimit=0,
        columns=1,
        symbolType="stroke",
        symbolStrokeWidth=3,
    )

    tooltip = [alt.Tooltip(f"{MONTH_COL}:O", title="月份")]
    if MEDIC_COL in chart_df.columns:
        tooltip.append(alt.Tooltip(f"{MEDIC_COL}:N", title="品种(全称)"))
    if STORE_COL in chart_df.columns:
        tooltip.append(alt.Tooltip(f"{STORE_COL}:N", title="药房"))
    tooltip.append(alt.Tooltip(f"{COMBO_COL}:N", title="品种 · 药房"))
    tooltip.append(alt.Tooltip(f"{metric_col}:Q", title=title, format=fmt))

    encoding = dict(
        x=alt.X(
            f"{MONTH_COL}:O",
            title="月份",
            axis=alt.Axis(labelAngle=-45, labelOverlap=True),
        ),
        y=alt.Y(f"{metric_col}:Q", title=title, axis=y_axis),
        color=alt.Color(f"{COMBO_COL}:N", title="品种 · 药房", legend=legend),
        tooltip=tooltip,
    )

    if highlight:
        # 单击曲线 或 单击图例项 都会更新同一个 selection；再点一次取消
        sel = alt.selection_point(
            name="highlight",
            fields=[COMBO_COL],
            on="click",
            toggle=True,
            clear="dblclick",
            bind="legend",
        )
        encoding["opacity"] = alt.condition(
            sel, alt.value(1.0), alt.value(DIMMED_OPACITY)
        )
        chart = alt.Chart(chart_df).mark_line(point=True, strokeWidth=2)
        chart = chart.encode(**encoding).add_params(sel)
    else:
        encoding["opacity"] = alt.value(1.0)
        chart = alt.Chart(chart_df).mark_line(point=True, strokeWidth=2).encode(**encoding)

    return chart.properties(height=380).interactive()
