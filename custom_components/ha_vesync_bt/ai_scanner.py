"Home Assistant AI Task bridge for food recognition."

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

import voluptuous as vol

from homeassistant.components import ai_task, conversation
from homeassistant.components.ai_task.const import (
    DATA_COMPONENT,
    DATA_PREFERENCES,
    AITaskEntityFeature,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotFound,
    ServiceValidationError,
)
from homeassistant.helpers.chat_session import async_get_chat_session

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

_IMAGE_MIME_SUFFIX = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _structure(language: str) -> dict[str, Any]:
    """Return the selector-based structured-output schema for AI Task service calls."""
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
                "Concise ENGLISH food/product name, maximum 20 characters. "
                "Always use English regardless of the Home Assistant UI language."
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
                "Short user-facing warning about uncertainty, missing label fields, "
                "conversion, or ambiguity. Write it in Home Assistant UI language "
                f"code {language!r}. Return an empty string when there is no special warning."
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


def _vol_structure(language: str) -> vol.Schema:
    """Return an equivalent Voluptuous schema for direct AI Task entity calls."""
    fields: dict[Any, Any] = {
        vol.Required(
            "identified",
            description=(
                "Return yes only when one edible food or packaged food can be "
                "identified with useful confidence."
            ),
        ): vol.In(["yes", "no"]),
        vol.Required(
            "name",
            description=(
                "Concise ENGLISH food/product name, maximum 20 characters. "
                "Never localize this field."
            ),
        ): str,
        vol.Required(
            "confidence",
            description="Recognition confidence from 0 to 100.",
        ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Required(
            "basis",
            description=(
                "One of nutrition_label, known_food, visual_estimate, unknown."
            ),
        ): vol.In(
            [
                "nutrition_label",
                "known_food",
                "visual_estimate",
                "unknown",
            ]
        ),
        vol.Required(
            "warning",
            description=(
                "Short user-facing uncertainty or conversion warning written in "
                f"Home Assistant UI language code {language!r}, or empty string."
            ),
        ): str,
    }
    for field in NUTRIENT_NAMES:
        fields[
            vol.Required(field, description=_NUTRIENT_DESCRIPTIONS[field])
        ] = vol.All(vol.Coerce(float), vol.Range(min=0))
    return vol.Schema(fields, extra=vol.PREVENT_EXTRA)


def _instructions(language: str, hint: str | None) -> str:
    """Build evidence-conscious food-recognition instructions."""
    hint_text = f"\nUser hint: {hint.strip()}" if hint and hint.strip() else ""
    return f"""Analyze the attached image for VeSync Local BT.

Identify ONE dominant edible food or packaged food that the user is likely
placing on a nutrition scale.

Language contract:
- The `name` field MUST ALWAYS be an ENGLISH food/product name, maximum 20
  characters, regardless of the Home Assistant UI language or the language of
  the user hint. Do not translate the food name.
- The user-facing `warning` field MUST be written in Home Assistant UI language
  code {language!r}. If no warning is needed, return an empty string.
- Machine fields such as `basis` keep their fixed schema values and are not
  translated.

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
        "structure": _structure(hass.config.language),
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


def _write_temp_image(image_data: bytes, suffix: str) -> Path:
    """Write one browser-captured image to an ephemeral temp file."""
    with tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=suffix,
        delete=False,
    ) as temp_file:
        temp_file.write(image_data)
        return Path(temp_file.name)


async def async_recognize_image(
    hass: HomeAssistant,
    *,
    image_data: bytes,
    mime_type: str,
    source: str,
    ai_task_entity: str | None = None,
    hint: str | None = None,
    context: Context | None = None,
) -> FoodScanResult:
    """Run one multimodal AI Task against browser/mobile image bytes."""
    suffix = _IMAGE_MIME_SUFFIX.get(mime_type)
    if suffix is None:
        raise ServiceValidationError(
            f"Unsupported browser image type: {mime_type}"
        )

    preferences = hass.data.get(DATA_PREFERENCES)
    entity_id = ai_task_entity or (
        preferences.gen_data_entity_id if preferences is not None else None
    )
    if entity_id is None:
        raise ServiceValidationError(
            "No AI Task entity was selected and Home Assistant has no preferred "
            "Generate data AI Task."
        )
    if not entity_id.startswith("ai_task."):
        raise ServiceValidationError(
            f"AI Task entity {entity_id!r} is not valid"
        )

    component = hass.data.get(DATA_COMPONENT)
    entity = component.get_entity(entity_id) if component is not None else None
    if entity is None:
        raise ServiceValidationError(
            f"AI Task entity {entity_id!r} was not found"
        )
    if AITaskEntityFeature.GENERATE_DATA not in entity.supported_features:
        raise ServiceValidationError(
            f"AI Task entity {entity_id!r} does not support Generate data"
        )
    if AITaskEntityFeature.SUPPORT_ATTACHMENTS not in entity.supported_features:
        raise ServiceValidationError(
            f"AI Task entity {entity_id!r} does not support image attachments"
        )

    temp_path = await hass.async_add_executor_job(
        _write_temp_image,
        image_data,
        suffix,
    )
    try:
        attachment = conversation.Attachment(
            media_content_id=f"media-source://ha_vesync_bt/{source}",
            mime_type=mime_type,
            path=temp_path,
        )
        with async_get_chat_session(hass) as session:
            result = await entity.internal_async_generate_data(
                session,
                ai_task.GenDataTask(
                    name="VeSync Local BT food scanner",
                    instructions=_instructions(hass.config.language, hint),
                    structure=_vol_structure(hass.config.language),
                    attachments=[attachment],
                ),
                context,
            )
    except HomeAssistantError as err:
        raise ServiceValidationError(
            f"AI food recognition failed: {err}"
        ) from err
    finally:
        await hass.async_add_executor_job(
            lambda: temp_path.unlink(missing_ok=True)
        )

    if not isinstance(result.data, dict):
        raise ServiceValidationError(
            "AI Task returned no structured food-recognition data"
        )

    return parse_food_scan_data(
        result.data,
        camera_entity=source,
        ai_task_entity=entity_id,
    )
