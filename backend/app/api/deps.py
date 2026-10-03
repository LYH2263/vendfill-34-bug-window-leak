from datetime import datetime

from fastapi import Depends


def get_now() -> datetime:
    """窗判定的唯一时钟来源。抽成依赖便于测试冻结时间。

    点位页窗配置、补货生成、补货单列表均经由此依赖取当前时刻，
    再交给 app.services.time_window 做同一套半开区间判定。
    """
    return datetime.now()


NowDep = Depends(get_now)
