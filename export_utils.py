"""结果导出工具。

把多个分析结果（{分析名: DataFrame}）写入同一个 Excel 文件的不同 Sheet，
供网页上的「一键下载」使用。
"""

import io

import pandas as pd

# Excel sheet 名的非法字符
_INVALID_SHEET_CHARS = ':\\/?*[]'


def _safe_sheet_name(name: str) -> str:
    """规范化 sheet 名：去掉非法字符，限制在 31 个字符内。"""
    for ch in _INVALID_SHEET_CHARS:
        name = name.replace(ch, "_")
    name = name.strip() or "Sheet"
    return name[:31]


def build_multi_sheet_excel(results: dict) -> bytes:
    """把 {分析名: DataFrame} 写成单文件多 sheet 的 Excel，返回字节流。

    - 只有非空结果才写入对应 sheet；
    - 若所有结果均为空，则写入一个「提示」sheet，保证文件可正常打开。

    Args:
        results: 形如 ``{"复购率分析": df1, "脱落分析": df2}``

    Returns:
        xlsx 文件的字节内容（可直接传给 st.download_button）。
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        wrote_any = False
        used_sheets = set()
        for analysis_name, df in results.items():
            if df is None or len(df) == 0:
                continue
            sheet_name = _safe_sheet_name(str(analysis_name))
            # 极端情况下避免 sheet 重名
            base, idx = sheet_name, 1
            while sheet_name in used_sheets:
                suffix = f"_{idx}"
                sheet_name = base[: 31 - len(suffix)] + suffix
                idx += 1
            used_sheets.add(sheet_name)
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            wrote_any = True

        if not wrote_any:
            pd.DataFrame({"提示": ["本次分析没有可导出的结果"]}).to_excel(
                writer, index=False, sheet_name="提示"
            )

    return buf.getvalue()
