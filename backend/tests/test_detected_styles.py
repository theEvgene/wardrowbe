from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem, ItemStatus
from app.models.user import User


def _item(user_id, *, styles, status=ItemStatus.ready, archived=False, canonical_id=None):
    return ClothingItem(
        user_id=user_id,
        type="shirt",
        image_path=f"test/{uuid4()}.jpg",
        style=styles,
        status=status,
        is_archived=archived,
        canonical_item_id=canonical_id,
    )


@pytest.mark.asyncio
async def test_detected_styles_only_count_current_active_canonical_ready_items(
    client: AsyncClient,
    auth_headers,
    db_session: AsyncSession,
    test_user: User,
):
    canonical = _item(test_user.id, styles=[" Casual ", "SMART-CASUAL", "casual", ""])
    second = _item(test_user.id, styles=["smart-casual"])
    db_session.add_all([canonical, second])
    await db_session.flush()

    other_user = User(
        external_id=f"other-{uuid4()}",
        email=f"other-{uuid4()}@example.com",
        display_name="Other User",
        timezone="UTC",
    )
    db_session.add(other_user)
    await db_session.flush()
    db_session.add_all(
        [
            _item(test_user.id, styles=["archived"], archived=True),
            _item(test_user.id, styles=["processing"], status=ItemStatus.processing),
            _item(test_user.id, styles=["alias"], canonical_id=canonical.id),
            _item(other_user.id, styles=["other-user"]),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/styles/detected", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "styles": [
            {"style": "casual", "item_count": 1},
            {"style": "smart-casual", "item_count": 2},
        ]
    }
