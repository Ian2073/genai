"""共用統計工具。

提供報表與驗證腳本可重用的基礎統計與相關係數計算，
避免同樣邏輯在多個腳本重複維護。
"""

from __future__ import annotations

import math
from typing import Iterable, List, Optional, Tuple


def _to_valid_pairs(x_values: Iterable[object], y_values: Iterable[object]) -> List[Tuple[float, float]]:
    """將兩個序列過濾為可用的數值配對。"""
    pairs: List[Tuple[float, float]] = []
    for left, right in zip(x_values, y_values):
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            continue
        left_f = float(left)
        right_f = float(right)
        if math.isnan(left_f) or math.isnan(right_f):
            continue
        pairs.append((left_f, right_f))
    return pairs


def mean(values: Iterable[float]) -> float:
    """計算平均值，空序列回傳 0。"""
    data = list(values)
    if not data:
        return 0.0
    return float(sum(data) / len(data))


def stdev(values: Iterable[float]) -> float:
    """計算樣本標準差，樣本少於 2 筆回傳 0。"""
    data = list(values)
    n = len(data)
    if n < 2:
        return 0.0
    m = mean(data)
    variance = sum((value - m) ** 2 for value in data) / (n - 1)
    return math.sqrt(max(0.0, variance))


def median(values: Iterable[float]) -> float:
    """計算中位數，空序列回傳 0。"""
    data = sorted(values)
    n = len(data)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 0:
        return float((data[mid - 1] + data[mid]) / 2.0)
    return float(data[mid])


def pearson_correlation(x_values: Iterable[object], y_values: Iterable[object], *, min_samples: int = 2) -> float:
    """計算皮爾遜相關係數。"""
    pairs = _to_valid_pairs(x_values, y_values)
    n = len(pairs)
    if n < min_samples:
        return 0.0

    xs = [item[0] for item in pairs]
    ys = [item[1] for item in pairs]
    mean_x = mean(xs)
    mean_y = mean(ys)

    numerator = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    sum_sq_x = sum((xs[i] - mean_x) ** 2 for i in range(n))
    sum_sq_y = sum((ys[i] - mean_y) ** 2 for i in range(n))
    denominator = math.sqrt(sum_sq_x * sum_sq_y)

    if denominator == 0.0:
        return 0.0
    return float(numerator / denominator)


def _rank_with_ties(values: List[float]) -> List[float]:
    """名次轉換（並列使用平均名次）。"""
    pairs = sorted((value, idx) for idx, value in enumerate(values))
    ranks: List[float] = [0.0] * len(values)
    i = 0
    n = len(pairs)
    while i < n:
        j = i + 1
        while j < n and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[pairs[k][1]] = avg_rank
        i = j
    return ranks


def spearman_correlation(x_values: Iterable[object], y_values: Iterable[object], *, min_samples: int = 2) -> float:
    """計算 Spearman 等級相關係數。"""
    pairs = _to_valid_pairs(x_values, y_values)
    n = len(pairs)
    if n < min_samples:
        return 0.0
    xs = [item[0] for item in pairs]
    ys = [item[1] for item in pairs]
    rank_x = _rank_with_ties(xs)
    rank_y = _rank_with_ties(ys)
    return pearson_correlation(rank_x, rank_y, min_samples=min_samples)
