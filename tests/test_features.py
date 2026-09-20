"""新增功能测试：多 Sheet 导出 + 折线图数据准备 / 图表构建。

不依赖 pytest，直接 `python tests/test_features.py` 即可运行。
"""

import io
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from export_utils import build_multi_sheet_excel
from charts import prepare_chart_df, build_line_chart, COMBO_COL


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
    assert list(d.columns) == ["月份", COMBO_COL, "复购率"]


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
