"""新患率分析。

定义（业务确认：以 Python "历史首次购药" 为准）：
    新患 = 当月购药，且在整个历史中从未购药的患者。
    新患率 = 新患人数 / 当月购药总人数。

"历史库"在每个分组内独立累计，跨分组互不干扰。
"""

import pandas as pd

from data_loader import iter_groups

EMPTY_COLUMNS = ['药店', '药品名称', '月份', '购药总人数', '新患人数(历史首购)', '新患率']


def calculate_new_patient_rate(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    results = []

    for label, group_df in iter_groups(df, group_cols):
        store_name = label.get('Store', '全部药店')
        medic_name = label.get('Medic', '全部药品')

        group_df = group_df.sort_values('period')
        all_months = group_df['period'].unique()
        seen_patients = set()

        for curr_m in all_months:
            curr_pts = set(group_df[group_df['period'] == curr_m]['ID'])
            new_pts = curr_pts - seen_patients

            total_cnt = len(curr_pts)
            new_cnt = len(new_pts)
            rate = new_cnt / total_cnt if total_cnt > 0 else 0

            results.append({
                '药店': store_name,
                '药品名称': medic_name,
                '月份': str(curr_m),
                '购药总人数': total_cnt,
                '新患人数(历史首购)': new_cnt,
                '新患率': rate,
            })
            seen_patients.update(curr_pts)

    if not results:
        return pd.DataFrame(columns=EMPTY_COLUMNS)
    return pd.DataFrame(results).sort_values(['药店', '药品名称', '月份']).reset_index(drop=True)
