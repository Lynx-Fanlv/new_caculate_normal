"""新增功能测试：多 Sheet 导出 + 折线图数据准备 / 图表构建。

不依赖 pytest，直接 `python tests/test_features.py` 即可运行。
"""

import io
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from export_utils import build_multi_sheet_excel
from charts import (
    prepare_chart_df,
    build_line_chart,
    short_medic_name,
    COMBO_COL,
    DIMMED_OPACITY,
)


def _sample_results():
    r1 = pd.DataFrame({
        "药店": ["药店A", "药店A", "药店B"],
        "药品名称": ["药X", "药X", "药X"],
        "月份": ["2024-01", "2024-02", "2024-01"],
        "复购率": [0.5, 0.6, 0.2],
    })
    r2 = pd.DataFrame({
        "药店": ["药店A"],
        "药品名称": ["药X"],
        "月份": ["2024-01"],
        "DOT": [1.5],
    })
    return {"复购率分析": r1, "DOT分析": r2}


# ---------------- 导出 ----------------

def test_multi_sheet_export_creates_one_sheet_per_analysis():
    data = build_multi_sheet_excel(_sample_results())
    assert isinstance(data, bytes) and len(data) > 0
    book = pd.ExcelFile(io.BytesIO(data))
    assert book.sheet_names == ["复购率分析", "DOT分析"]
    back = book.parse("复购率分析")
    assert list(back.columns) == ["药店", "药品名称", "月份", "复购率"]
    assert len(back) == 3


def test_multi_sheet_export_skips_empty_and_adds_notice():
    data = build_multi_sheet_excel({"A": None, "B": pd.DataFrame()})
    book = pd.ExcelFile(io.BytesIO(data))
    assert book.sheet_names == ["提示"]


def test_multi_sheet_export_sanitizes_sheet_name():
    weird = {"a/b:c*?[]": pd.DataFrame({"x": [1]})}
    data = build_multi_sheet_excel(weird)
    book = pd.ExcelFile(io.BytesIO(data))
    name = book.sheet_names[0]
    assert name.startswith("a_b_c")
    assert not (set(name) & set(':\\/?*[]'))   # 不含 Excel 非法字符
    assert len(name) <= 31


# ---------------- 图表数据准备 ----------------

def test_prepare_chart_df_filters_and_builds_combo():
    r1 = _sample_results()["复购率分析"]
    d = prepare_chart_df(r1, "复购率", sel_medics=["药X"], sel_stores=["药店A"])
    assert set(d[COMBO_COL]) == {"药X · 药店A"}
    assert len(d) == 2
    assert list(d["月份"]) == ["2024-01", "2024-02"]


def test_prepare_chart_df_all_combos_sorted():
    r1 = _sample_results()["复购率分析"]
    d = prepare_chart_df(r1, "复购率")
    assert len(d) == 3
    assert set(d[COMBO_COL]) == {"药X · 药店A", "药X · 药店B"}
    assert list(d.columns)[:3] == ["月份", COMBO_COL, "复购率"]
    # 完整名称列保留下来，供 tooltip 使用
    assert "药品名称" in d.columns and "药店" in d.columns


def test_prepare_chart_df_missing_metric_returns_empty():
    r1 = _sample_results()["复购率分析"]
    d = prepare_chart_df(r1, "不存在的指标")
    assert len(d) == 0


def test_prepare_chart_df_no_store_column():
    df = pd.DataFrame({"药品名称": ["药X"], "月份": ["2024-01"], "新患率": [0.3]})
    d = prepare_chart_df(df, "新患率")
    assert d.iloc[0][COMBO_COL] == "药X · 全部药店"


# ---------------- 图表构建 ----------------

def test_build_line_chart_spec():
    r1 = _sample_results()["复购率分析"]
    d = prepare_chart_df(r1, "复购率")
    chart = build_line_chart(d, "复购率", percent=True)
    assert chart is not None
    spec = chart.to_dict()
    assert spec["mark"]["type"] == "line"
    assert spec["encoding"]["x"]["field"] == "月份"
    assert spec["encoding"]["y"]["field"] == "复购率"
    assert spec["encoding"]["color"]["field"] == COMBO_COL


def test_build_line_chart_empty_returns_none():
    assert build_line_chart(pd.DataFrame(columns=["月份", COMBO_COL, "复购率"]), "复购率") is None


# ---------------- 图例可读性：短名 + 不截断 ----------------

def test_short_medic_name_extracts_brand():
    # 真实数据中的写法
    assert short_medic_name("替雷利珠单抗注射液(百泽安)") == "百泽安"
    assert short_medic_name("泽布替尼胶囊(百悦泽)") == "百悦泽"
    # 全角括号
    assert short_medic_name("某某注射液（商品名）") == "商品名"


def test_short_medic_name_fallback_truncates_only_when_long():
    assert short_medic_name("药X") == "药X"                      # 短名不截断
    assert short_medic_name("") == ""
    long_no_paren = "阿" * 20
    out = short_medic_name(long_no_paren)
    assert out.endswith("…") and len(out) == 9                    # 8 字 + 省略号


def test_prepare_chart_df_uses_short_medic_in_combo():
    df = pd.DataFrame({
        "药店": ["攀枝花药房(连锁）"],
        "药品名称": ["替雷利珠单抗注射液(百泽安)"],
        "月份": ["2024-01"],
        "DOT": [2.0],
    })
    d = prepare_chart_df(df, "DOT")
    assert d.iloc[0][COMBO_COL] == "百泽安 · 攀枝花药房(连锁）"


def test_legend_does_not_truncate_labels():
    d = prepare_chart_df(_sample_results()["复购率分析"], "复购率")
    chart = build_line_chart(d, "复购率")
    spec = chart.to_dict()
    legend = spec["encoding"]["color"]["legend"]
    # Vega 中 limit<=0 表示不限长度，即不做「…」截断
    assert legend["labelLimit"] == 0


# ---------------- 交互：点选曲线/图例高亮 ----------------

def test_highlight_selection_spec():
    d = prepare_chart_df(_sample_results()["复购率分析"], "复购率")
    spec = build_line_chart(d, "复购率").to_dict()
    params = spec.get("params", [])
    hl = [p for p in params if p.get("name") == "highlight"]
    assert len(hl) == 1, f"params={params}"
    sel = hl[0]["select"]
    assert sel["type"] == "point"
    assert sel["fields"] == [COMBO_COL]
    assert sel["on"] == "click"
    assert sel["toggle"] is True          # 再点一次取消高亮
    assert hl[0]["bind"] == "legend"      # 图例项可点


def test_highlight_opacity_condition():
    d = prepare_chart_df(_sample_results()["复购率分析"], "复购率")
    spec = build_line_chart(d, "复购率").to_dict()
    opacity = spec["encoding"]["opacity"]
    assert opacity["condition"]["param"] == "highlight"
    assert opacity["condition"]["value"] == 1.0
    assert opacity["value"] == DIMMED_OPACITY


def test_highlight_can_be_disabled():
    d = prepare_chart_df(_sample_results()["复购率分析"], "复购率")
    spec = build_line_chart(d, "复购率", highlight=False).to_dict()
    names = [p.get("name") for p in spec.get("params", [])]
    assert "highlight" not in names        # 只剩 .interactive() 的缩放参数
    assert spec["encoding"]["opacity"] == {"value": 1.0}


# ---------------- 筛选默认值（智能阈值） ----------------

def test_decide_preselect_by_combo_count():
    from views import decide_preselect
    # 2 × 3 = 6 <= 10 -> 全选
    ok, meds, stores = decide_preselect(["百泽安", "百悦泽"], ["A", "B", "C"])
    assert ok is True
    assert meds == ["百泽安", "百悦泽"] and stores == ["A", "B", "C"]
    # 2 × 11 = 22 > 10 -> 不选
    ok2, meds2, stores2 = decide_preselect(["百泽安", "百悦泽"], [f"s{i}" for i in range(11)])
    assert ok2 is False and meds2 == [] and stores2 == []



def _run():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} tests passed")


if __name__ == "__main__":
    _run()
