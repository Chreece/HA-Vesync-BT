"""Home Assistant AI Task bridge for food recognition."""

from __future__ import annotations

from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound, ServiceValidationError

from .food_scan import FoodScanResult, parse_food_scan_data
from .protocol.nutrition import NUTRIENT_NAMES

_AI_DOMAIN = "ai_task"
_AI_SERVICE = "generate_data"

_NUTRIENT_DESCRIPTIONS = {
    "calories_kcal": "Calories in kcal per 100 g.",
    "protein_g": "Protein in grams per 100 g.",
    "total_fat_g": "Total fat in grams per 100 g.",
    "saturated_fat_g": "Saturated fat in grams per 100 g.",
    "trans_fat_g": "Trans fat in grams per 100 g.",
    "total_carbs_g": "Total carbohydrates in grams per 100 g.",
    "dietary_fiber_g": "Dietary fiber in grams per 100 g.",
    "sugars_g": "Sugars in grams per 100 g.",
    "cholesterol_mg": "Cholesterol in milligrams per 100 g.",
    "sodium_mg": "Sodium in milligrams per 100 g.",
    "iron_mg": "Iron in milligrams per 100 g.",
}


def _structure() -> dict[str, Any]:
    """Return the strict structured-output schema for AI Task."""
    result: dict[str, Any] = {
        "identified": {
            "description": (
                "Return yes only when one edible food or packaged food can be "
                "identified with useful confidence."
            ),
            "required": True,
            "selector": {"select": {"options": ["yes", "no"]}},
        },
        "name": {
            "description": (
                "Concise food/product name, maximum 20 characters. Use the "
                "requested UI language when practical."
            ),
            "required": True,
            "selector": {"text": {}},
        },
        "confidence": {
            "description": "Recognition confidence from 0 to 100.",
            "required": True,
            "selector": {"number": {"min": 0, "max": 100, "step": 1}},
        },
        "basis": {
            "description": (
                "nutrition_label when values came from a visible readable label; "
                "known_food when using standard nutrition knowledge for a clearly "
                "recognized food; visual_estimate when recognition or nutrition "
                "requires estimation; unknown when reliable nutrition cannot be produced."
            ),
            "required": True,
            "selector": {
                "select": {
                    "options": [
                        "nutrition_label",
                        "known_food",
                        "visual_estimate",
                        "unknown",
                    ]
                }
            },
        },
        "warning": {
            "description": (
                "Short warning about uncertainty, missing label fields, conversion, "
                "or ambiguity. Return an empty string when there is no special warning."
            ),
            "required": True,
            "selector": {"text": {}},
        },
    }
    for field in NUTRIENT_NAMES:
        result[field] = {
            "description": _NUTRIENT_DESCRIPTIONS[field],
            "required": True,
            "selector": {"number": {"min": 0, "step": 0.1}},
        }
    return result


def _instructions(language: str, hint: str | None) -> str:
    """Build evidence-conscious food-recognition instructions."""
    hint_text = f"\nUser hint: {hint.strip()}" if hint and hint.strip() else ""
    return f"""Analyze the attached camera image for VeSync Local BT.

Identify ONE dominant edible food or packaged food that the user is likely
placing on a nutrition scale. Return the food name in Home Assistant language
code {language!r} when practical.

Nutrition values MUST be normalized to a 100 g reference because the scale
expects food nutrition per 100 g.

Evidence priority:
1. If a readable Nutrition Facts / nutrition label is visible, use the label.
   If it is per serving and the serving mass in grams is visible, convert every
   value to per 100 g.
2. Otherwise, if the food itself is clearly recognized, use typical nutrition
   values per 100 g and set basis=known_food.
3. If the identification or nutrition needs significant visual estimation, set
   basis=visual_estimate and explain the uncertainty in warning.
4. If no edible food can be identified reliably, set identified=no,
   basis=unknown, confidence low, and use zero for unavailable nutrient fields.

Never invent a visible label. Do not claim nutrition_label unless the label is
actually readable in the image. Prefer uncertainty over false precision.
All nutrient numbers must be non-negative. For nutrients not available on a
visible label, use 0 and mention that omission in warning.
{hint_text}"""


async def async_recognize_food(
    hass: HomeAssistant,
    *,
    camera_entity: str,
    ai_task_entity: str | None = None,
    hint: str | None = None,
    context: Context | None = None,
) -> FoodScanResult:
    """Run one multimodal AI Task against a Home Assistant camera."""
    camera_state = hass.states.get(camera_entity)
    if camera_state is None or not camera_entity.startswith("camera."):
        raise ServiceValidationError(
            f"Camera entity {camera_entity!r} was not found"
        )
    if camera_state.state in {"unknown", "unavailable"}:
        raise ServiceValidationError(
            f"Camera entity {camera_entity!r} is {camera_state.state}"
        )

    service_data: dict[str, Any] = {
        "task_name": "VeSync Local BT food scanner",
        "instructions": _instructions(hass.config.language, hint),
        "structure": _structure(),
        "attachments": [
            {
                "media_content_id": f"media-source://camera/{camera_entity}",
            }
        ],
    }
    if ai_task_entity:
        if not ai_task_entity.startswith("ai_task."):
            raise ServiceValidationError(
                f"AI Task entity {ai_task_entity!r} is not valid"
            )
        service_data["entity_id"] = ai_task_entity

    try:
        response = await hass.services.async_call(
            _AI_DOMAIN,
            _AI_SERVICE,
            service_data,
            blocking=True,
            return_response=True,
            context=context,
        )
    except ServiceNotFound as err:
        raise ServiceValidationError(
            "No AI Task Generate data action is available. Configure an AI Task "
            "provider that supports image attachments first."
        ) from err
    except HomeAssistantError as err:
        raise ServiceValidationError(
            f"AI food recognition failed: {err}"
        ) from err

    if not isinstance(response, dict) or not isinstance(response.get("data"), dict):
        raise ServiceValidationError(
            "AI Task returned no structured food-recognition data"
        )

    return parse_food_scan_data(
        response["data"],
        camera_entity=camera_entity,
        ai_task_entity=ai_task_entity,
    )
