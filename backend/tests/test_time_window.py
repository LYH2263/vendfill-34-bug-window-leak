from app.services.time_window import current_minute, is_valid_window, validate_window, window_open
from datetime import datetime


def test_null_window_is_unrestricted():
    assert validate_window(None, None) is None
    assert is_valid_window(None, None)
    assert window_open(None, None, current_minute(datetime(2026, 10, 3, 3, 17)))


def test_reject_one_sided():
    assert validate_window(600, None) is not None
    assert validate_window(None, 660) is not None


def test_reject_end_not_greater_than_start():
    assert validate_window(600, 600) is not None  # 半开，相等即空窗
    assert validate_window(700, 600) is not None


def test_reject_out_of_range():
    assert validate_window(-1, 100) is not None
    assert validate_window(0, 24 * 60) is not None  # 1440 越界
    assert validate_window(24 * 60, 24 * 60 + 1) is not None


def test_half_open_boundary():
    # [600, 660)：起点在内，终点分钟本身已在窗外
    assert window_open(600, 660, 600)
    assert window_open(600, 660, 659)
    assert not window_open(600, 660, 660)
    assert not window_open(600, 660, 599)


def test_full_day_window():
    assert window_open(0, 1439, 0)
    assert window_open(0, 1439, 1438)
    assert not window_open(0, 1439, 1439)
