import json
import re
from datetime import date
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.item import ClothingItem, ItemStatus
from app.models.outfit import (
    FamilyOutfitRating,
    Outfit,
    OutfitItem,
    OutfitSource,
    OutfitStatus,
)
from app.models.preference import UserPreference
from app.models.user import User
from app.services.ai_service import AIService, require_internal_ai
from app.services.recommendation_service import AIRecommendationError, InsufficientWardrobeError
from app.utils.clothing import ITEM_ROLE, canonical_item_order
from app.utils.timezone import get_user_today


class StyleOutfitService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _candidates(self, user_id: UUID) -> list[ClothingItem]:
        result = await self.db.execute(
            select(ClothingItem).where(
                and_(
                    ClothingItem.user_id == user_id,
                    ClothingItem.status == ItemStatus.ready,
                    ClothingItem.is_archived.is_(False),
                    ClothingItem.canonical_item_id.is_(None),
                    ClothingItem.type != "unknown",
                )
            )
        )
        return sorted(result.scalars().all(), key=lambda item: (item.type or "", str(item.id)))

    @staticmethod
    def _prompt(items: list[ClothingItem], target_style: str, count: int, occasion: str) -> str:
        lines = []
        for number, item in enumerate(items, 1):
            details = [f"[{number}] type={item.type}"]
            if item.primary_color:
                details.append(f"color={item.primary_color}")
            if item.style:
                details.append(f"styles={','.join(item.style)}")
            if item.formality:
                details.append(f"formality={item.formality}")
            lines.append(" | ".join(details))
        return (
            "You are a wardrobe stylist. Use only the numbered items below.\n"
            f"Create exactly {count} complete, distinct outfits in the '{target_style}' style "
            f"for the '{occasion}' occasion.\n"
            "Each outfit must contain either one full-body item and footwear, or one top, "
            "one bottom, and footwear. Optional outerwear and accessories are allowed.\n"
            "Outfits must differ in at least one non-accessory item. Never invent item numbers.\n"
            'Return JSON only: {"outfits":[{"items":[1,2,3],"headline":"...",'
            '"styling_tip":"..."}]}\n\n'
            "AVAILABLE ITEMS:\n" + "\n".join(lines)
        )

    @staticmethod
    def _parse(content: str) -> list[dict]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIRecommendationError("AI returned invalid JSON") from exc
        outfits = parsed.get("outfits") if isinstance(parsed, dict) else None
        if not isinstance(outfits, list):
            raise AIRecommendationError("AI response must contain an outfits array")
        return outfits

    @staticmethod
    def _validate_selection(
        proposal: dict, number_map: dict[int, ClothingItem]
    ) -> list[ClothingItem]:
        numbers = proposal.get("items")
        if not isinstance(numbers, list) or not numbers:
            raise AIRecommendationError("Each outfit must contain item numbers")
        try:
            normalized = [int(number) for number in numbers]
        except (TypeError, ValueError) as exc:
            raise AIRecommendationError("Outfit contains a non-numeric item reference") from exc
        if len(normalized) != len(set(normalized)):
            raise AIRecommendationError("Outfit contains the same item more than once")
        if any(number not in number_map for number in normalized):
            raise AIRecommendationError("Outfit contains an item outside the candidate wardrobe")

        selected = [number_map[number] for number in normalized]
        roles = [ITEM_ROLE.get((item.type or "").lower()) for item in selected]
        occupied = [role for role in roles if role not in {None, "accessory"}]
        if len(occupied) != len(set(occupied)):
            raise AIRecommendationError("Outfit contains conflicting body-slot items")
        has_footwear = "footwear" in roles
        has_full_body = "full_body" in roles
        has_separates = "base_top" in roles and "bottom" in roles
        if not has_footwear or not (has_full_body or has_separates):
            raise AIRecommendationError("Outfit is incomplete")
        if has_full_body and ("base_top" in roles or "bottom" in roles):
            raise AIRecommendationError("Full-body and separates cannot be combined")
        return selected

    async def generate(
        self,
        *,
        user: User,
        target_style: str,
        count: int = 3,
        occasion: str = "casual",
        scheduled_date: date | None = None,
    ) -> list[Outfit]:
        require_internal_ai("text")
        target_style = target_style.strip().lower()
        candidates = await self._candidates(user.id)
        detected_styles = {
            normalized
            for item in candidates
            for style in (item.style or [])
            if (normalized := style.strip().lower())
        }
        if target_style not in detected_styles:
            raise ValueError(f"Style '{target_style}' was not detected in the current wardrobe")
        if len(candidates) < 3:
            raise InsufficientWardrobeError(
                "Not enough active wardrobe items for a complete outfit"
            )

        preference_result = await self.db.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        preferences = preference_result.scalar_one_or_none()
        ai_service = AIService(
            endpoints=preferences.ai_endpoints if preferences and preferences.ai_endpoints else None
        )
        result = await ai_service.generate_text(
            self._prompt(candidates, target_style, count, occasion),
            return_metadata=True,
        )
        proposals = self._parse(result.content)
        if len(proposals) != count:
            raise AIRecommendationError(f"AI returned {len(proposals)} outfits; expected {count}")

        number_map = dict(enumerate(candidates, 1))
        validated = [self._validate_selection(proposal, number_map) for proposal in proposals]
        key_piece_sets = [
            frozenset(
                item.id
                for item in selected
                if ITEM_ROLE.get((item.type or "").lower())
                not in {"accessory", "socks", "neckwear"}
            )
            for selected in validated
        ]
        if len(set(key_piece_sets)) != count:
            raise AIRecommendationError("Generated outfits are not sufficiently diverse")

        created: list[Outfit] = []
        try:
            for index, (proposal, selected) in enumerate(zip(proposals, validated, strict=True)):
                outfit = Outfit(
                    user_id=user.id,
                    occasion=occasion,
                    target_style=target_style,
                    scheduled_for=scheduled_date or get_user_today(user),
                    reasoning=proposal.get("headline") or proposal.get("reasoning"),
                    style_notes=proposal.get("styling_tip") or proposal.get("style_notes"),
                    ai_raw_response={
                        **proposal,
                        "_ai_model": result.model,
                        "_ai_endpoint": result.endpoint,
                        "_batch_index": index,
                    },
                    source=OutfitSource.on_demand,
                    status=OutfitStatus.pending,
                )
                self.db.add(outfit)
                await self.db.flush()
                type_map = {item.id: (item.type or "").lower() for item in selected}
                ordered_ids = canonical_item_order([item.id for item in selected], type_map)
                for position, item_id in enumerate(ordered_ids):
                    self.db.add(OutfitItem(outfit_id=outfit.id, item_id=item_id, position=position))
                created.append(outfit)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        ids = [outfit.id for outfit in created]
        loaded = await self.db.execute(
            select(Outfit)
            .where(Outfit.id.in_(ids))
            .options(
                selectinload(Outfit.items).selectinload(OutfitItem.item),
                selectinload(Outfit.feedback),
                selectinload(Outfit.family_ratings).selectinload(FamilyOutfitRating.user),
            )
        )
        by_id = {outfit.id: outfit for outfit in loaded.scalars().all()}
        return [by_id[outfit_id] for outfit_id in ids]
