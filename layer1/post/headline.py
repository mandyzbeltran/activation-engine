"""Deterministic localized headline templates."""

from __future__ import annotations

ZH = {
    "career": ("事业结构的调整窗口", "外部要求正在变得清晰，适合校准职业承诺与长期方向。"),
    "wealth": ("资源与价值的整理窗口", "近期更适合审视资源配置，并让长期安排贴近真实优先级。"),
    "relationships": ("关系边界的重新校准", "互动中的需求与边界更容易浮现，适合进行具体而诚实的沟通。"),
    "family": ("家庭与内在根基的调整", "家庭节奏或安全感议题可能更受关注，适合维护稳定的支持结构。"),
}
EN = {
    "career": ("A window for career recalibration", "External expectations may become clearer, supporting a review of commitments and long-term direction."),
    "wealth": ("A window for resource review", "This period may support practical review of resources, priorities, and longer-term plans."),
    "relationships": ("A recalibration of relationship boundaries", "Needs and boundaries may become easier to notice, inviting specific and honest conversation."),
    "family": ("Adjusting family and inner foundations", "Home rhythms or security needs may receive more attention, supporting steadier foundations."),
}


def localized_text(area: str, locale: str) -> tuple[dict, dict]:
    headline, one_line = (ZH if locale == "zh-Hans" else EN)[area]
    return ({"locale": locale, "text": headline}, {"locale": locale, "text": one_line})
