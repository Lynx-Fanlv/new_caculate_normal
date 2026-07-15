"""复购率分析。

定义（对齐 New_fugou.m 的 T-2 基准口径）：
    复购患者 = 在 T-2 月购药，且在 T-1 月或 T 月再次购药的患者。
    复购率   = 复购患者数 / T-2 月购药人数。

T-2 / T-1 按日历月推算。
"""

import pandas as pd

from data_loader import iter_groups

EMPTY_COLUMNS = ['药店', '药品名称', '月份', '复购人数', '基准月(T-2)购药人数', '复购率']


def calculate_medic_repurchase(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    results = []

    for label, group_df in iter_groups(df, group_cols):
        store_name = label.get('Store', '全部药店')
        medic_name = label.get('Medic', '全部药品')

        all_months = sorted(group_df['period'].unique())

        for curr_m in all_months:
            p2 = curr_m - 2  # 基准月 T-2（日历月）
            p1 = curr_m - 1  # T-1（日历月）

            base_pts = set(group_df[group_df['period'] == p2]['ID'])
            follow_pts = set(group_df[group_df['period'].isin([p1, curr_m])]['ID'])

            total_base = len(base_pts)
            repurchase_pts = base_pts & follow_pts
            repurchase_count = len(repurchase_pts)
            rate = repurchase_count / total_base if total_base > 0 else 0

            results.append({
                '药店': store_name,
                '药品名称': medic_name,
                '月份': str(curr_m),
                '复购人数': repurchase_count,
                '基准月(T-2)购药人数': total_base,
                '复购率': rate,
            })

    if not results:
        return pd.DataFrame(columns=EMPTY_COLUMNS)
    return pd.DataFrame(results).sort_values(['药店', '药品名称', '月份']).reset_index(drop=True)
