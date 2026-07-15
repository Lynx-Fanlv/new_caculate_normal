"""脱落率分析。

定义（业务确认）：
    脱落患者 = 在 T-2 月购药，但在 T-1 月与 T 月均未购药的患者。
    脱落率   = 脱落患者数 / T-2 月购药人数。

T-2 / T-1 均按"日历月"推算（period - 2 / period - 1），
即使中间存在断档月份也能正确定位。
"""

import pandas as pd

from data_loader import iter_groups

EMPTY_COLUMNS = ['药店', '药品名称', '月份', '基准月(T-2)购药人数', '脱落人数', '脱落率']


def calculate_dropout_rate(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    results = []

    for label, group_df in iter_groups(df, group_cols):
        store_name = label.get('Store', '全部药店')
        medic_name = label.get('Medic', '全部药品')

        all_months = sorted(group_df['period'].unique())

        for curr_m in all_months:
            # 日历月推算：T-2、T-1
            p2 = curr_m - 2
            p1 = curr_m - 1

            pts_t2 = set(group_df[group_df['period'] == p2]['ID'])
            pts_recent = set(group_df[group_df['period'].isin([p1, curr_m])]['ID'])

            dropout_pts = pts_t2 - pts_recent
            base_cnt = len(pts_t2)
            rate = len(dropout_pts) / base_cnt if base_cnt > 0 else 0

            results.append({
                '药店': store_name,
                '药品名称': medic_name,
                '月份': str(curr_m),
                '基准月(T-2)购药人数': base_cnt,
                '脱落人数': len(dropout_pts),
                '脱落率': rate,
            })

    if not results:
        return pd.DataFrame(columns=EMPTY_COLUMNS)
    return pd.DataFrame(results).sort_values(['药店', '药品名称', '月份']).reset_index(drop=True)
