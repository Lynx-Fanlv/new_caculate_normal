"""DOT（Duration of Treatment）分析。

定义：
    DOT = 倒推12个月销量总和 / 倒推12个月去重患者数。

优化点（相比原版）：
    1. 先在每个分组内按月预聚合（月销量 + 月患者集合），
       再做12个月滑动窗口，避免在完整数据上反复扫描。
    2. 窗口合并仅遍历至多12个月的预聚合结果，复杂度大幅下降。
    3. 负数销量保留（业务确认：退货/冲红计入）。
"""

import pandas as pd

from data_loader import iter_groups

EMPTY_COLUMNS = ['药店', '药品名称', '月份', 'DOT', '倒推12个月销量', '倒推12个月去重患者数']


def calculate_dot(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    results = []

    for label, group_df in iter_groups(df, group_cols):
        store_name = label.get('Store', '全部药店')
        medic_name = label.get('Medic', '全部药品')

        # 按月预聚合：月销量 + 月患者集合
        monthly = (
            group_df.groupby('period')
            .agg(qty=('Quantity', 'sum'), patients=('ID', lambda x: set(x.unique())))
            .sort_index()
        )

        for curr_m in monthly.index:
            start_m = curr_m - 11  # 倒推12个月起点（含当月共12个月）
            window = monthly[(monthly.index >= start_m) & (monthly.index <= curr_m)]

            total_qty = window['qty'].sum()

            all_patients = set()
            for pset in window['patients']:
                all_patients.update(pset)
            unique_cnt = len(all_patients)

            dot = total_qty / unique_cnt if unique_cnt > 0 else 0

            results.append({
                '药店': store_name,
                '药品名称': medic_name,
                '月份': str(curr_m),
                'DOT': dot,
                '倒推12个月销量': total_qty,
                '倒推12个月去重患者数': unique_cnt,
            })

    if not results:
        return pd.DataFrame(columns=EMPTY_COLUMNS)
    return pd.DataFrame(results).sort_values(['药店', '药品名称', '月份']).reset_index(drop=True)
