"""AppTest 专用：组合数超过阈值（22 个）的场景，应默认不勾选。

仅供 tests/smoke_app.py 使用。
"""

import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import streamlit as st
from views import render_results

st.set_page_config(page_title="results-many", layout="wide")

medics = ["百泽安", "百悦泽"]
stores = [f"药店{i:02d}" for i in range(1, 12)]  # 11 个药店 -> 22 个组合

rows = []
for m in medics:
    for s in stores:
        for mo, v in [("2024-01", 0.5), ("2024-02", 0.6)]:
            rows.append({"药店": s, "药品名称": m, "月份": mo, "复购率": v})

render_results({"复购率分析": pd.DataFrame(rows)})
