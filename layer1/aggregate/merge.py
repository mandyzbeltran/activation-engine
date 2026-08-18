"""Order-independent connected-component activation bucketing."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List


def window_jaccard(first: dict, second: dict) -> float:
    intersection = max(0.0, (min(first["end"], second["end"]) - max(first["start"], second["start"])).total_seconds())
    union = max(first["end"], second["end"]) - min(first["start"], second["start"])
    return intersection / union.total_seconds() if union.total_seconds() else 1.0


def connected_buckets(drivers: Iterable[dict]) -> List[List[dict]]:
    ordered = sorted(drivers, key=lambda item: item["driver_id"])
    adjacency = {index: set() for index in range(len(ordered))}
    for left in range(len(ordered)):
        for right in range(left + 1, len(ordered)):
            if (
                ordered[left]["tentative_area"] == ordered[right]["tentative_area"]
                and window_jaccard(ordered[left], ordered[right]) >= 0.50
            ):
                adjacency[left].add(right)
                adjacency[right].add(left)
    buckets = []
    unseen = set(adjacency)
    while unseen:
        root = min(unseen)
        stack = [root]
        component = []
        unseen.remove(root)
        while stack:
            current = stack.pop()
            component.append(ordered[current])
            for neighbor in sorted(adjacency[current], reverse=True):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        buckets.append(sorted(component, key=lambda item: item["driver_id"]))
    return buckets
