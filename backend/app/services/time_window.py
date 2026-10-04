"""点位补货时段窗：一天内分钟数，半开区间 [start, end)。

点位页窗配置、补货生成接口、补货单列表共用本模块的同一套放行口径，
禁止各接口自行解释窗界。开始、结束都为 None 表示不限制时段（随时可生成）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

MIN_MINUTE = 0
MAX_MINUTE = 24 * 60 - 1
OUTSIDE_REASON = "不在补货时段"


def validate_window(start: Optional[int], end: Optional[int]) -> Optional[str]:
    """返回 None 表示合法；否则返回拒绝原因。

    - 开始、结束必须同时为空（不限制）或同时给值
    - 取值范围 [0, 1439]
    - 半开区间要求结束严格大于开始
    """
    if start is None and end is None:
        return None
    if start is None or end is None:
        return "开始分钟与结束分钟必须同时填写或同时为空"
    if not (MIN_MINUTE <= start <= MAX_MINUTE) or not (MIN_MINUTE <= end <= MAX_MINUTE):
        return "补货时段分钟数越界（0-1439）"
    if end <= start:
        return "结束分钟必须大于开始分钟"
    return None


def is_valid_window(start: Optional[int], end: Optional[int]) -> bool:
    return validate_window(start, end) is None


def window_open(start: Optional[int], end: Optional[int], now_minute: int) -> bool:
    """半开区间 [start, end)；调用方须保证窗合法。双空表示不限制。"""
    if start is None or end is None:
        return True
    return start <= now_minute < end


def current_minute(now: Optional[datetime] = None) -> int:
    now = now or datetime.now()
    return now.hour * 60 + now.minute


def location_open(loc, now: Optional[datetime] = None,
                  clock: Optional[Callable[[], datetime]] = None) -> bool:
    """点位对象（含 fill_start_minute/fill_end_minute）当前是否放行。"""
    now = now or (clock() if clock else datetime.now())
    return window_open(loc.fill_start_minute, loc.fill_end_minute, current_minute(now))
