"""AppTest 冒烟测试。

1) app.py 首屏能否无异常渲染；
2) 结果视图（views.render_results）能否渲染出筛选控件、图表与下载按钮；
3) 数据表默认展开；
4) 未勾选品种 / 药房时给出占位图框 + 「快速预览」按钮，点击后能直接出图。

不依赖 pytest，直接 `python tests/smoke_app.py` 运行。
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

from streamlit.testing.v1 import AppTest

from views import QUICK_PICK_COMBOS

APP = os.path.join(_ROOT, "app.py")
PREVIEW = os.path.join(_HERE, "_results_view_app.py")
MANY = os.path.join(_HERE, "_results_view_many_app.py")
STALE = os.path.join(_HERE, "_stale_option_app.py")

# 占位图框的判别标记：注意不能用 "chart-placeholder"，
# 因为注入的 <style> 里也含该选择器，会误判。
_PLACEHOLDER_MARK = 'class="chart-placeholder"'


def _has_placeholder(at) -> bool:
    return any(_PLACEHOLDER_MARK in (m.value or "") for m in at.markdown)


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


def test_data_tables_expanded_by_default():
    """四个分析的数据表都应默认展开。"""
    at = AppTest.from_file(PREVIEW, default_timeout=180)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.expander) == 4, f"expander={len(at.expander)}"
    assert [ex.label for ex in at.expander] == ["查看数据表"] * 4
    assert all(ex.proto.expanded for ex in at.expander), \
        [ex.proto.expanded for ex in at.expander]
    # 表格本体可见
    assert len(at.dataframe) >= 4


def test_few_combos_default_select_all():
    """组合数 <= 阈值时，筛选框默认全选，且不出现「快速预览」按钮与占位框。"""
    at = AppTest.from_file(PREVIEW, default_timeout=180)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.multiselect[0].value) == 2   # 2 个品种
    assert len(at.multiselect[1].value) == 2   # 2 个药房
    assert len(at.button) == 0
    assert not _has_placeholder(at)


def test_many_combos_default_select_none():
    """组合数 > 阈值时，筛选框默认不选，但必须能看出「这里有折线图」。"""
    at = AppTest.from_file(MANY, default_timeout=180)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.multiselect) == 2
    assert at.multiselect[0].value == []
    assert at.multiselect[1].value == []
    # 关键：不再只有一行灰字，而是渲染占位图框 + 一键预览按钮
    assert _has_placeholder(at), "未勾选时应显示占位图框"
    assert len(at.button) == 1, f"button={len(at.button)}"
    assert "先看前" in at.button[0].label
    assert len(at.info) == 0, "不应再退化为一句普通提示"


def test_quick_pick_button_renders_charts():
    """点「快速预览」后应勾选恰好 N 个组合并出图，占位框随之消失。"""
    at = AppTest.from_file(MANY, default_timeout=180)
    at.run()
    at.button[0].click().run()
    assert not at.exception, [e.message for e in at.exception]
    combos = len(at.multiselect[0].value) * len(at.multiselect[1].value)
    assert combos == QUICK_PICK_COMBOS, f"combos={combos}"
    assert not _has_placeholder(at), "出图后不应再显示占位框"
    # 组合数超阈值时按钮常驻（便于随时回到「前 N 个组合」的预览）
    assert len(at.button) == 1
    assert len(at.info) == 0


def test_deselect_all_shows_placeholder_and_quick_pick():
    """组合数少时若用户手动取消全部勾选，也要给出占位框与快速预览入口。"""
    at = AppTest.from_file(PREVIEW, default_timeout=180)
    at.run()
    at.multiselect[0].set_value([]).run()
    assert not at.exception, [e.message for e in at.exception]
    assert _has_placeholder(at)
    assert len(at.button) == 1


def test_results_view_filter_reduces_series_without_error():
    at = AppTest.from_file(PREVIEW, default_timeout=180)
    at.run()
    at.multiselect[0].set_value(["百泽安"]).run()
    at.multiselect[1].set_value(["药店A"]).run()
    assert not at.exception, [e.message for e in at.exception]


def test_streamlit_drops_stale_multiselect_values():
    """守住 views.py 依赖的假设：session_state 里的失效旧值会被自动过滤而非报错。

    换文件 / 改分组维度后，筛选框的旧取值可能已不在当前选项里；
    若某天 Streamlit 改为抛异常，应用会在这些场景直接崩溃。
    """
    at = AppTest.from_file(STALE, default_timeout=60)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.multiselect[0].value == ["a"], f"value={at.multiselect[0].value}"



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
