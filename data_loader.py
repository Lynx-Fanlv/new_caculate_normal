"""共享数据加载与清洗模块。

所有分析逻辑都依赖本模块完成：
1. 列名标准化（兼容中文/英文表头）
2. 必需字段校验（TIME / ID / Quantity）
3. Store、Medic 作为可选分组维度处理（按开关保留/丢弃列）
4. 时间转换为月度 Period，供后续滑动窗口计算
"""

import pandas as pd

# 列名标准化映射：原始表头 -> 内部标准名
COLUMN_MAPPING = {
    '药店': 'Store', 'Store': 'Store',
    '药品名称': 'Medic', 'Medic': 'Medic',
    '患者ID': 'ID', 'ID': 'ID',
    '销售时间': 'TIME', '时间': 'TIME',
    '数量': 'Quantity', '销量': 'Quantity', 'Quantity': 'Quantity',
}

# 必需字段：缺一则无法计算
REQUIRED_COLUMNS = ['TIME', 'ID', 'Quantity']


class DataValidationError(Exception):
    """上传数据格式不合法时抛出。"""
    pass


def validate_columns(df: pd.DataFrame) -> None:
    """校验必需列是否存在，缺失则抛出可读的错误。"""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(
            f"数据缺少必需字段：{missing}。\n"
            f"当前识别到的列：{df.columns.tolist()}\n"
            f"必需字段为：TIME（销售时间）、ID（患者ID）、Quantity（数量）。"
        )


def load_and_clean(
    file_path: str,
    use_store: bool = True,
    use_medic: bool = True,
) -> pd.DataFrame:
    """读取 Excel 并完成标准化清洗。

    Store / Medic 为可选维度：
    - use_store=True 且数据含 Store 列 -> 保留并按药店分组
    - 否则 -> 丢弃 Store 列，整体合并
    - Medic 同理

    Args:
        file_path: Excel 文件路径
        use_store: 是否按药店分组
        use_medic: 是否按药品分组

    Returns:
        标准化后的 DataFrame，含 Store / Medic / ID / Quantity / TIME / period 列
        （Store、Medic 在关闭分组时不存在于返回结果中）
    """
    df = pd.read_excel(file_path)

    # 列名标准化
    df = df.rename(
        columns={c: COLUMN_MAPPING[c] for c in df.columns if c in COLUMN_MAPPING}
    )

    # 必需字段校验
    validate_columns(df)

    # ---- 可选维度：按开关保留或丢弃对应列 ----
    if not (use_store and 'Store' in df.columns):
        df = df.drop(columns=['Store'], errors='ignore')
    if not (use_medic and 'Medic' in df.columns):
        df = df.drop(columns=['Medic'], errors='ignore')

    # ---- 必需字段清洗 ----
    df = df.dropna(subset=['ID', 'TIME', 'Quantity'])
    df['ID'] = df['ID'].astype(str)
    # 负数销量保留（业务确认：退货/冲红计入）
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
    df['TIME'] = pd.to_datetime(df['TIME'], errors='coerce')
    df = df.dropna(subset=['TIME'])

    # 月度 Period：用于 T-2 / 12个月滑动窗口
    df['period'] = df['TIME'].dt.to_period('M')

    return df


def build_group_cols(use_store: bool, use_medic: bool, df: pd.DataFrame) -> list:
    """根据实际数据列与开关，决定分组维度。"""
    group_cols = []
    if use_store and 'Store' in df.columns:
        group_cols.append('Store')
    if use_medic and 'Medic' in df.columns:
        group_cols.append('Medic')
    return group_cols


def iter_groups(df: pd.DataFrame, group_cols: list):
    """逐组 yield (标签字典, 子DataFrame)。

    兼容无分组（全部归一组）的情况。
    """
    if not group_cols:
        yield {'Store': '全部药店', 'Medic': '全部药品'}, df
        return

    for key, group_df in df.groupby(group_cols):
        # groupby 单键返回标量，多键返回元组，统一成元组
        if not isinstance(key, tuple):
            key = (key,)
        label = dict(zip(group_cols, key))
        # 补全缺失的标签字段
        label.setdefault('Store', '全部药店')
        label.setdefault('Medic', '全部药品')
        yield label, group_df
