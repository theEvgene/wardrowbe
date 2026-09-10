"""Deterministic outfit compatibility and capsule batch selection rules."""

from __future__ import annotations

from itertools import combinations
from typing import Iterable

from app.models.item import ClothingItem
from app.utils.clothing import ITEM_ROLE

FORMALITY_LEVELS = {
    "very-casual": 0,
    "casual": 1,
    "smart-casual": 2,
    "business-casual": 3,
    "formal": 4,
    "very-formal": 5,
}


def _normalized(value: str | None) -> str:
    return (value or "").strip().lower()


def _styles(item: ClothingItem) -> set[str]:
    return {_normalized(style) for style in (item.style or []) if _normalized(style)}


def _colors(item: ClothingItem) -> set[str]:
    return {
        _normalized(color)
        for color in [item.primary_color, *(item.colors or [])]
        if _normalized(color)
    }


def _is_denim(item: ClothingItem) -> bool:
    return _normalized(item.subtype) in {"jeans", "denim"} or "denim" in _colors(item)


def _is_loafer(item: ClothingItem) -> bool:
    return _normalized(item.subtype) in {"loafer", "loafers", "moccasin", "moccasins"}


def _is_graphic_or_statement(item: ClothingItem) -> bool:
    return bool(
        _normalized(item.pattern) not in {"", "solid", "plain"}
        or {"graphic", "statement", "bold"} & _styles(item)
    )


def _formality(item: ClothingItem) -> int | None:
    value = _normalized(item.formality)
    return FORMALITY_LEVELS.get(value)


def _distinct_color_count(items: Iterable[ClothingItem]) -> int:
    colors = set()
    for item in items:
        colors.update(_colors(item))
    neutral = {"black", "white", "gray", "grey", "beige", "cream", "navy", "brown"}
    return len(colors - neutral)


def is_compatible(
    items: Iterable[ClothingItem],
    *,
    weather_data: dict | None = None,
    forbidden_item_pairs: set[frozenset[str]] | None = None,
) -> tuple[bool, str | None]:
    """Return whether a complete item set is a coherent recommendation.

    Hard safety checks (ownership, active state and completeness) remain in the
    service. These rules cover composition-level failures that a text model can
    otherwise miss. The optional pair list is user-scoped and uses item UUIDs.
    """

    selected = list(items)
    if not selected:
        return False, "empty outfit"

    item_ids = {str(item.id) for item in selected}
    if forbidden_item_pairs:
        for pair in forbidden_item_pairs:
            if pair <= item_ids:
                return False, "explicitly forbidden item pairing"

    roles = [ITEM_ROLE.get(_normalized(item.type)) for item in selected]
    tops = [item for item, role in zip(selected, roles) if role == "base_top"]
    bottoms = [item for item, role in zip(selected, roles) if role == "bottom"]
    shoes = [item for item, role in zip(selected, roles) if role == "footwear"]

    if shoes and weather_data:
        temperature = weather_data.get("temperature")
        if isinstance(temperature, (int, float)) and temperature >= 20:
            if any(_normalized(shoe.type) == "boots" for shoe in shoes):
                return False, "winter footwear is unsuitable for warm weather"

    # User-observable guardrail: denim plus loafers is only allowed when the
    # upper layer is explicitly smart-casual or more formal. A casual tee or
    # polo with loafers and jeans was a repeated bad recommendation.
    if shoes and any(_is_loafer(shoe) for shoe in shoes) and any(
        _is_denim(bottom) for bottom in bottoms
    ):
        upper_levels = [_formality(item) for item in tops]
        known_upper_levels = [level for level in upper_levels if level is not None]
        if not known_upper_levels or max(known_upper_levels) < 2:
            return False, "loafers with casual denim outfit"

    if shoes and any(_is_loafer(shoe) for shoe in shoes) and any(
        _is_graphic_or_statement(top) for top in tops
    ):
        return False, "loafers with graphic casual top"

    levels = [level for level in (_formality(item) for item in selected) if level is not None]
    if len(levels) >= 2 and max(levels) - min(levels) > 2:
        return False, "formality levels are too far apart"

    if _distinct_color_count(selected) > 3:
        return False, "too many accent colors"

    return True, None


def select_capsule_sets(
    candidate_sets: list[list[int]],
    count: int,
    *,
    item_roles: dict[int, str] | None = None,
) -> list[list[int]]:
    """Select a diverse batch while preferring reuse of the same key pieces.

    The objective is intentionally deterministic: first minimize the number of
    unique key pieces, then maximize pairwise set difference. This produces a
    compact capsule without allowing duplicate outfits.
    """

    if count <= 0:
        return []
    normalized = []
    seen: set[frozenset[int]] = set()
    for item_set in candidate_sets:
        key = frozenset(item_set)
        if key and key not in seen:
            normalized.append(sorted(key))
            seen.add(key)

    if len(normalized) <= count:
        return normalized

    best: tuple[tuple[float, float, tuple[tuple[int, ...], ...]], list[list[int]]] | None = None
    for combo in combinations(normalized, count):
        unique_items = len(set().union(*(set(item_set) for item_set in combo)))
        pairwise_difference = sum(
            len(set(left) ^ set(right)) for left, right in combinations(combo, 2)
        )
        diversity_penalty = 0
        if item_roles:
            available_by_role: dict[str, set[int]] = {}
            used_by_role: dict[str, set[int]] = {}
            for item_set in normalized:
                for item_number in item_set:
                    role = item_roles.get(item_number)
                    if role:
                        available_by_role.setdefault(role, set()).add(item_number)
            for item_set in combo:
                for item_number in item_set:
                    role = item_roles.get(item_number)
                    if role:
                        used_by_role.setdefault(role, set()).add(item_number)
            for role, available in available_by_role.items():
                minimum_unique = min(count, 2, len(available))
                diversity_penalty += max(0, minimum_unique - len(used_by_role.get(role, set())))
        # Reuse dominates, but difference breaks ties and prevents identical
        # looking batches when several compact choices are available. When
        # role metadata is available, first require meaningful top/bottom/
        # footwear variation so compactness cannot collapse into one base
        # outfit with only interchangeable shoes.
        objective = (
            float(diversity_penalty),
            float(unique_items),
            -float(pairwise_difference),
            tuple(combo),
        )
        if best is None or objective < best[0]:
            best = (objective, [list(item_set) for item_set in combo])
    return best[1] if best else []
