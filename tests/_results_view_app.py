"""AppTest 专用最小应用：只调用结果视图 render_results，用于测试渲染路径。

不是给用户使用的页面，仅供 tests/smoke_app.py 调用。
"""

import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import streamlit as st
from views import render_results

st.set_page_config(page_title="results-preview", layout="wide")


def _four_analyses():
    medics = ["百泽安", "百悦泽"]
    stores = ["药店A", "药店B"]
    months = ["2024-01", "2024-02", "2024-03"]

    def build(metric, extra_cols, percent_values):
        rows = []
        for m in medics:
            for s in stores:
                for i, mo in enumerate(months):
                    row = {"药店": s, "药品名称": m, "月份": mo}
                    row.update(extra_cols(i))
                    row[metric] = percent_values[i]
                    rows.append(row)
        return pd.DataFrame(rows)

    return {
        "复购率分析": build("复购率", lambda i: {"复购人数": i + 1, "基准月(T-2)购药人数": i + 2}, [0.5, 0.6, 0.7]),
        "脱落分析":   build("脱落率", lambda i: {"基准月(T-2)购药人数": i + 2, "脱落人数": i}, [0.1, 0.2, 0.15]),
        "DOT分析":    build("DOT", lambda i: {"倒推12个月销量": 10 * (i + 1), "倒推12个月去重患者数": i + 3}, [1.5, 2.0, 2.5]),
        "新患分析":   build("新患率", lambda i: {"购药总人数": i + 4, "新患人数(历史首购)": i + 1}, [0.25, 0.3, 0.4]),
    }


render_results(_four_analyses())
