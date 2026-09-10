from uuid import uuid4

from app.models.item import ClothingItem
from app.services.capsule_rules import is_compatible, select_capsule_sets


def item(item_type: str, **kwargs) -> ClothingItem:
    return ClothingItem(
        id=uuid4(),
        user_id=uuid4(),
        type=item_type,
        image_path="test/item.jpg",
        **kwargs,
    )


def test_rejects_casual_denim_with_loafers() -> None:
    tee = item("t-shirt", primary_color="white", formality="casual")
    jeans = item("jeans", subtype="jeans", primary_color="blue", formality="casual")
    loafers = item("shoes", subtype="loafers", primary_color="navy", formality="smart-casual")

    compatible, reason = is_compatible([tee, jeans, loafers])

    assert not compatible
    assert reason == "loafers with casual denim outfit"


def test_allows_smart_casual_chinos_with_loafers() -> None:
    shirt = item("shirt", primary_color="navy", formality="smart-casual")
    chinos = item("pants", subtype="chinos", primary_color="beige", formality="smart-casual")
    loafers = item("shoes", subtype="loafers", primary_color="navy", formality="smart-casual")

    compatible, reason = is_compatible([shirt, chinos, loafers])

    assert compatible
    assert reason is None


def test_rejects_boots_in_warm_weather() -> None:
    tee = item("t-shirt", primary_color="white", formality="casual")
    chinos = item("pants", primary_color="beige", formality="casual")
    boots = item("boots", primary_color="black", formality="casual")

    compatible, reason = is_compatible(
        [tee, chinos, boots], weather_data={"temperature": 23}
    )

    assert not compatible
    assert reason == "winter footwear is unsuitable for warm weather"


def test_select_capsule_sets_prefers_reuse_then_difference() -> None:
    sets = [[1, 3, 5], [1, 3, 6], [1, 4, 5], [2, 4, 6], [2, 3, 6]]
    selected = select_capsule_sets(sets, 3)

    assert selected == [[1, 3, 5], [1, 3, 6], [1, 4, 5]]
    assert len({frozenset(candidate) for candidate in selected}) == 3


def test_explicit_forbidden_item_pair_is_user_scoped() -> None:
    tee = item("t-shirt", primary_color="white", formality="casual")
    pants = item("pants", primary_color="black", formality="casual")
    shoes = item("shoes", primary_color="white", formality="casual")

    compatible, reason = is_compatible(
        [tee, pants, shoes],
        forbidden_item_pairs={frozenset({str(tee.id), str(pants.id)})},
    )

    assert not compatible
    assert reason == "explicitly forbidden item pairing"
