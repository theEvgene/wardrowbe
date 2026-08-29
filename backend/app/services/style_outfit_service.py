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
from app.utils.clothing import ITEM_ROLE, canonical_item_order, normalize_style_labels
from app.utils.timezone import get_user_today

MAX_GENERATION_ATTEMPTS = 3
MAX_VISIBLE_TEXT_LENGTH = 2000


class StyleContextError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


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
    def _valid_core_number_sets(items: list[ClothingItem], limit: int = 200) -> list[list[int]]:
        by_role: dict[str, list[int]] = {}
        for number, item in enumerate(items, 1):
            role = ITEM_ROLE.get((item.type or "").lower())
            if role:
                by_role.setdefault(role, []).append(number)

        valid: list[list[int]] = []
        for full_body in by_role.get("full_body", []):
            for footwear in by_role.get("footwear", []):
                valid.append([full_body, footwear])
                if len(valid) == limit:
                    return valid
        for base_top in by_role.get("base_top", []):
            for bottom in by_role.get("bottom", []):
                for footwear in by_role.get("footwear", []):
                    valid.append([base_top, bottom, footwear])
                    if len(valid) == limit:
                        return valid
        return valid

    @classmethod
    def _prompt(
        cls, items: list[ClothingItem], target_style: str, count: int, occasion: str
    ) -> str:
        lines = []
        for number, item in enumerate(items, 1):
            details = [f"[{number}] type={item.type}"]
            role = ITEM_ROLE.get((item.type or "").lower())
            if role:
                details.append(f"role={role}")
            if item.primary_color:
                details.append(f"color={item.primary_color}")
            if item.style:
                details.append(f"styles={','.join(item.style)}")
            if item.formality:
                details.append(f"formality={item.formality}")
            lines.append(" | ".join(details))
        valid_core_sets = cls._valid_core_number_sets(items)
        example = json.dumps(valid_core_sets[0], separators=(",", ":"))
        return (
            "You are a wardrobe stylist. Use only the numbered items below.\n"
            f"Create exactly {count} complete, distinct outfits in the '{target_style}' style "
            f"for the '{occasion}' occasion.\n"
            "Each outfit must contain either exactly one full_body and exactly one footwear, "
            "or exactly one base_top, exactly one bottom, and exactly one footwear. "
            "Never include two items with the same role. Optional outer_layer, mid_layer, "
            "socks, neckwear, and accessories are allowed.\n"
            "Outfits must differ in at least one non-accessory item. Never invent item numbers.\n"
            f"VALID CORE ITEM SETS: {json.dumps(valid_core_sets)}\n"
            f"For every outfit, copy one distinct VALID CORE ITEM SET unchanged into items. "
            f'Return JSON only: {{"outfits":[{{"items":{example},"headline":"...",'
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
        if isinstance(parsed, list):
            if parsed and all(
                isinstance(wrapper, dict) and isinstance(wrapper.get("outfits"), list)
                for wrapper in parsed
            ):
                outfits = [proposal for wrapper in parsed for proposal in wrapper["outfits"]]
            else:
                outfits = parsed
        else:
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
        normalized: list[int] = []
        for number in numbers:
            if isinstance(number, bool):
                raise AIRecommendationError("Outfit contains a non-numeric item reference")
            if isinstance(number, int):
                normalized.append(number)
                continue
            if isinstance(number, str) and re.fullmatch(r"[1-9]\d*", number.strip()):
                normalized.append(int(number))
                continue
            raise AIRecommendationError("Outfit contains a non-numeric item reference")
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

    @staticmethod
    def _validated_proposal(proposal: object) -> dict:
        if not isinstance(proposal, dict):
            raise AIRecommendationError("Each outfit proposal must be an object")
        safe: dict[str, object] = {"items": proposal.get("items")}
        for field in ("headline", "reasoning", "styling_tip", "style_notes"):
            value = proposal.get(field)
            if value is None:
                continue
            if not isinstance(value, str) or len(value.strip()) > MAX_VISIBLE_TEXT_LENGTH:
                raise AIRecommendationError(f"Outfit {field} is invalid or too long")
            safe[field] = value.strip()
        highlights = proposal.get("highlights")
        if highlights is not None:
            if (
                not isinstance(highlights, list)
                or len(highlights) > 10
                or any(
                    not isinstance(value, str) or len(value.strip()) > 500 for value in highlights
                )
            ):
                raise AIRecommendationError("Outfit highlights are invalid or too long")
            safe["highlights"] = [value.strip() for value in highlights]
        return safe

    async def generate(
        self,
        *,
        user: User,
        target_style: str,
        count: int = 3,
        occasion: str = "casual",
        scheduled_date: date | None = None,
        generation_context: dict | None = None,
    ) -> list[Outfit]:
        """Generate, validate, and atomically persist an exact style-driven outfit batch."""

        require_internal_ai("text")
        target_style = target_style.strip().lower()
        candidates = await self._candidates(user.id)
        context = generation_context or {
            "time_of_day": None,
            "activity": None,
            "constraints": {
                "required_item_ids": [],
                "excluded_item_ids": [],
                "avoided_colors": [],
                "note": None,
            },
        }
        constraints = context.get("constraints") or {}
        constrained_ids = {
            UUID(item_id)
            for field in ("required_item_ids", "excluded_item_ids")
            for item_id in constraints.get(field, [])
        }
        candidate_ids = {item.id for item in candidates}
        if unavailable_ids := constrained_ids - candidate_ids:
            raise StyleContextError(
                "constraint_item_unavailable",
                "Constraint items must be active canonical wardrobe items owned by the user: "
                + ", ".join(sorted(str(item_id) for item_id in unavailable_ids)),
            )
        detected_styles = {
            normalized for item in candidates for normalized in normalize_style_labels(item.style)
        }
        if target_style not in detected_styles:
            raise ValueError(f"Style '{target_style}' was not detected in the current wardrobe")
        if len(candidates) < 3:
            raise InsufficientWardrobeError(
                "Not enough active wardrobe items for a complete outfit"
            )
        valid_core_sets = self._valid_core_number_sets(candidates)
        if len(valid_core_sets) < count:
            raise InsufficientWardrobeError(
                f"Only {len(valid_core_sets)} distinct complete outfits can be built from the "
                f"current wardrobe; {count} requested"
            )

        preference_result = await self.db.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        preferences = preference_result.scalar_one_or_none()
        ai_service = AIService(
            endpoints=preferences.ai_endpoints if preferences and preferences.ai_endpoints else None
        )
        number_map = dict(enumerate(candidates, 1))
        accepted: list[tuple[dict, list[ClothingItem], str, str]] = []
        accepted_key_sets: set[frozenset[UUID]] = set()
        validation_errors: list[str] = []
        base_prompt = self._prompt(candidates, target_style, count, occasion)

        for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
            remaining = count - len(accepted)
            prompt = base_prompt
            if attempt > 1:
                recent_errors = "; ".join(validation_errors[-5:])
                prompt = (
                    self._prompt(candidates, target_style, remaining, occasion)
                    + "\nREPAIR ATTEMPT: Return only new valid outfits. Do not repeat earlier sets. "
                    + f"Previous validation problems: {recent_errors}"
                )
            try:
                result = await ai_service.generate_text(prompt, return_metadata=True)
                proposals = self._parse(result.content)
            except Exception as exc:
                validation_errors.append(str(exc) or exc.__class__.__name__)
                continue

            for proposal in proposals:
                if len(accepted) == count:
                    break
                try:
                    safe_proposal = self._validated_proposal(proposal)
                    selected = self._validate_selection(safe_proposal, number_map)
                    key_set = frozenset(
                        item.id
                        for item in selected
                        if ITEM_ROLE.get((item.type or "").lower())
                        not in {"accessory", "socks", "neckwear"}
                    )
                    if key_set in accepted_key_sets:
                        raise AIRecommendationError("Outfit repeats an existing key-piece set")
                except AIRecommendationError as exc:
                    validation_errors.append(str(exc))
                    continue
                accepted.append((safe_proposal, selected, result.model, result.endpoint))
                accepted_key_sets.add(key_set)

            if len(accepted) == count:
                break

        if len(accepted) != count:
            details = "; ".join(dict.fromkeys(validation_errors[-5:]))
            raise AIRecommendationError(
                f"Could not generate {count} valid diverse outfits after "
                f"{MAX_GENERATION_ATTEMPTS} attempts. Please retry. Validation: {details}"
            )

        created: list[Outfit] = []
        try:
            for index, (proposal, selected, model, endpoint) in enumerate(accepted):
                outfit = Outfit(
                    user_id=user.id,
                    occasion=occasion,
                    target_style=target_style,
                    scheduled_for=scheduled_date or get_user_today(user),
                    generation_context=context,
                    ai_raw_response={
                        **proposal,
                        "_ai_model": model,
                        "_ai_endpoint": endpoint,
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
