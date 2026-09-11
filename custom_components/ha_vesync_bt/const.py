"""Constants for VeSync Local BT."""

from __future__ import annotations

DOMAIN = "ha_vesync_bt"
NAME = "VeSync Local BT"

SUPPORTED_LOCAL_NAME = "COSORI Nutrition Scale"
SUPPORTED_MODEL = "CNS-R002S-S"
MANUFACTURER = "COSORI"

PLATFORMS = ["sensor", "binary_sensor", "select", "button", "event"]

STATE_THROTTLE_SECONDS = 0.2

SERVICE_ADD_QUICK_FOOD = "add_quick_food"
SERVICE_REMOVE_QUICK_FOOD = "remove_quick_food"
SERVICE_REORDER_QUICK_FOODS = "reorder_quick_foods"
SERVICE_SET_ENABLED_UNITS = "set_enabled_units"
SERVICE_SET_FOOD_CONTEXT = "set_food_context"

ATTR_SEQUENCE = "sequence"
ATTR_SEQUENCES = "sequences"
ATTR_UNITS = "units"
ATTR_NAME = "name"
ATTR_DAILY_FOOD_WEIGHT_G = "daily_food_weight_g"

NUTRIENT_FIELDS = (
    "calories_kcal",
    "protein_g",
    "total_fat_g",
    "saturated_fat_g",
    "trans_fat_g",
    "total_carbs_g",
    "dietary_fiber_g",
    "sugars_g",
    "cholesterol_mg",
    "sodium_mg",
    "iron_mg",
)
