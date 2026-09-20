"""AppTest 冒烟测试。

1) app.py 首屏能否无异常渲染；
2) 结果视图（views.render_results）能否渲染出筛选控件、图表与下载按钮；
3) 多选框筛选后是否仍无异常。

不依赖 pytest，直接 `python tests/smoke_app.py` 运行。
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

from streamlit.testing.v1 import AppTest

APP = os.path.join(_ROOT, "app.py")
PREVIEW = os.path.join(_HERE, "_results_view_app.py")
MANY = os.path.join(_HERE, "_results_view_many_app.py")


def test_app_initial_render():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert not at.exception, [e.message for e in at.exception]


def test_results_view_renders_filters_charts_downloads():
    at = AppTest.from_file(PREVIEW, default_timeout=180)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    # 品种 / 药房两个筛选框
    assert len(at.multiselect) == 2, f"multiselect={len(at.multiselect)}"
    # 一键下载(1) + 四个分析各一个(4) = 5
    assert len(at.download_button) == 5, f"download_button={len(at.download_button)}"


def test_few_combos_default_select_all():
    """组合数 <= 阈值时，筛选框默认全选。"""
    at = AppTest.from_file(PREVIEW, default_timeout=180)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.multiselect[0].value) == 2   # 2 个品种
    assert len(at.multiselect[1].value) == 2   # 2 个药房


def test_many_combos_default_select_none():
    """组合数 > 阈值时，筛选框默认不选（避免首屏折线过多）。"""
    at = AppTest.from_file(MANY, default_timeout=180)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.multiselect) == 2
    assert at.multiselect[0].value == []
    assert at.multiselect[1].value == []


def test_results_view_filter_reduces_series_without_error():
    at = AppTest.from_file(PREVIEW, default_timeout=180)
    at.run()
    at.multiselect[0].set_value(["百泽安"]).run()
    at.multiselect[1].set_value(["药店A"]).run()
    assert not at.exception, [e.message for e in at.exception]



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
