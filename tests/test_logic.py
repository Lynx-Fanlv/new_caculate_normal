"""逻辑层单元测试。

使用合成数据验证四项指标的核心计算，覆盖：
- 日历月 T-2 / T-1 推算
- Store / Medic 可选分组
- 负数销量保留
- 新患"历史首购"口径
"""

import os
import tempfile
import pandas as pd

from data_loader import load_and_clean, build_group_cols, iter_groups
from dropout_logic import calculate_dropout_rate
from repurchase_analysis import calculate_medic_repurchase
from new_patient_logic import calculate_new_patient_rate
from dot_logic import calculate_dot


def _write_temp(df: pd.DataFrame) -> str:
    """将 DataFrame 落盘为临时 xlsx，返回路径。"""
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    df.to_excel(path, index=False)
    return path


def _load_sample(use_store=True, use_medic=True) -> pd.DataFrame:
    return load_and_clean(_write_temp(_make_sample_df()), use_store, use_medic)


def _make_sample_df():
    """构造已知结果的小数据集：药店A / 药X，2024-01~03。

    P1: 01,02,03 各买1
    P2: 01买2, 02不买, 03买2
    P3: 03买1（新患）
    """
    rows = [
        ("2024-01-05", "药X", 1, "P1", "药店A"),
        ("2024-01-10", "药X", 2, "P2", "药店A"),
        ("2024-02-05", "药X", 1, "P1", "药店A"),
        ("2024-03-05", "药X", 1, "P1", "药店A"),
        ("2024-03-06", "药X", 2, "P2", "药店A"),
        ("2024-03-07", "药X", 1, "P3", "药店A"),
    ]
    return pd.DataFrame(rows, columns=["TIME", "Medic", "Quantity", "ID", "Store"])


def test_load_and_clean_keeps_optional_columns():
    df = _load_sample(True, True)
    assert {"Store", "Medic", "ID", "Quantity", "TIME", "period"}.issubset(df.columns)
    assert df['Quantity'].sum() == 8


def test_load_and_clean_drops_disabled_columns():
    df = _load_sample(False, False)
    assert "Store" not in df.columns
    assert "Medic" not in df.columns


def test_load_and_clean_missing_required_raises():
    bad = pd.DataFrame({"Medic": ["x"], "Quantity": [1], "ID": ["a"]})
    raised = False
    try:
        load_and_clean(_write_temp(bad), True, True)
    except Exception:
        raised = True
    assert raised, "缺少必需字段时应当抛出异常"


def test_dropout_calendar_month():
    df = _load_sample(True, True)
    gc = build_group_cols(True, True, df)
    res = calculate_dropout_rate(df, gc)
    # 2024-03: T-2=2024-01 {P1,P2}, Recent={P1,P2,P3} -> 脱落0
    row_mar = res[res['月份'] == "2024-03"].iloc[0]
    assert row_mar['脱落人数'] == 0
    assert row_mar['脱落率'] == 0.0
    # 2024-02: T-2=2023-12 无数据 -> 基准0 -> 率0
    row_feb = res[res['月份'] == "2024-02"].iloc[0]
    assert row_feb['基准月(T-2)购药人数'] == 0
    assert row_feb['脱落率'] == 0.0


def test_repurchase_rate():
    df = _load_sample(True, True)
    gc = build_group_cols(True, True, df)
    res = calculate_medic_repurchase(df, gc)
    # 2024-03: T-2=2024-01 {P1,P2}, T-1/T={P1,P2,P3} -> 复购2/2=1.0
    row_mar = res[res['月份'] == "2024-03"].iloc[0]
    assert row_mar['复购人数'] == 2
    assert row_mar['复购率'] == 1.0


def test_new_patient_historical_first():
    df = _load_sample(True, True)
    gc = build_group_cols(True, True, df)
    res = calculate_new_patient_rate(df, gc)
    by_month = {r['月份']: r for _, r in res.iterrows()}
    # 01: 首购 P1,P2 -> 2/2
    assert by_month["2024-01"]['新患人数(历史首购)'] == 2
    assert by_month["2024-01"]['新患率'] == 1.0
    # 02: P1 已见过 -> 0
    assert by_month["2024-02"]['新患人数(历史首购)'] == 0
    # 03: P3 为新患 -> 1/3
    assert by_month["2024-03"]['新患人数(历史首购)'] == 1
    assert by_month["2024-03"]['新患率'] == 1 / 3


def test_dot_calculation():
    df = _load_sample(True, True)
    gc = build_group_cols(True, True, df)
    res = calculate_dot(df, gc)
    by_month = {r['月份']: r for _, r in res.iterrows()}
    # 2024-01: qty 3, patients 2 -> 1.5
    assert by_month["2024-01"]['DOT'] == 1.5
    # 2024-03: 12m qty 8, patients 3 -> 8/3
    assert abs(by_month["2024-03"]['DOT'] - 8 / 3) < 1e-9


def test_no_grouping_single_result():
    df = _load_sample(False, False)
    gc = build_group_cols(False, False, df)
    assert gc == []
    res = calculate_dropout_rate(df, gc)
    # 不分组时仍为单组结果
    assert len(res) >= 1
    assert (res['药店'] == "全部药店").all()


def test_negative_quantity_preserved():
    rows = [
        ("2024-01-05", "药X", -1, "P1", "药店A"),
        ("2024-02-05", "药X", 3, "P1", "药店A"),
    ]
    df = pd.DataFrame(rows, columns=["TIME", "Medic", "Quantity", "ID", "Store"])
    df = load_and_clean(_write_temp(df), True, True)
    gc = build_group_cols(True, True, df)
    res = calculate_dot(df, gc)
    # 2024-02: qty = -1 + 3 = 2, patients 1 -> DOT 2.0 (负数已计入)
    row = res[res['月份'] == "2024-02"].iloc[0]
    assert row['DOT'] == 2.0


if __name__ == "__main__":
    test_load_and_clean_keeps_optional_columns()
    test_load_and_clean_drops_disabled_columns()
    test_load_and_clean_missing_required_raises()
    test_dropout_calendar_month()
    test_repurchase_rate()
    test_new_patient_historical_first()
    test_dot_calculation()
    test_no_grouping_single_result()
    test_negative_quantity_preserved()
    print("All tests passed!")
