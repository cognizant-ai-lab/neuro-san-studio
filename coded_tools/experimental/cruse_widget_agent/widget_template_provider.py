# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

import asyncio
import json
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool


class WidgetTemplateProvider(CodedTool):
    """
    CodedTool implementation which provides comprehensive JSON schema templates
    for generating dynamic widgets based on conversation context.
    """

    # Comprehensive widget schema template
    WIDGET_SCHEMA_TEMPLATE = {
        "title": "<WIDGET_TITLE>",
        "description": "<WIDGET_DESCRIPTION>",
        "icon": "<ICON_NAME>",  # Optional: e.g., "CalendarMonth", "AccountCircle", "Schedule", "Work", etc.
        "color": "<PRIMARY_COLOR>",  # Optional: hex color e.g., "#1976d2", "#9c27b0"
        "schema": {
            "type": "object",
            "title": "<FORM_TITLE>",
            "description": "<FORM_DESCRIPTION>",
            "properties": {
                # Example fields - agent should replace with actual fields based on context
                "field_name": {
                    "type": "string",  # or "number", "integer", "boolean", "array"
                    "title": "<FIELD_LABEL>",
                    "description": "<FIELD_HELP_TEXT>",
                    "examples": ["<PLACEHOLDER_EXAMPLE>"],
                    # Optional string constraints
                    "minLength": 1,
                    "maxLength": 100,
                    "pattern": "<REGEX_PATTERN>",
                    # For select/dropdown (use enum)
                    # "enum": ["option1", "option2", "option3"],
                    # For number fields
                    # "minimum": 0,
                    # "maximum": 100,
                    # "multipleOf": 1,
                    # For date fields
                    # "format": "date",  # or "date-time"
                    # Custom UI hints (optional)
                    # "x-ui": {
                    #     "widget": "textarea",  # or "slider", "rating", "radio", "checkbox"
                    #     "minDate": "2024-01-01",  # for date fields
                    #     "maxDate": "2024-12-31"   # for date fields
                    # }
                }
            },
            "required": ["field_name"],  # List of required field names
        },
    }

    # Widget type examples for reference
    WIDGET_TYPE_EXAMPLES = {
        "text_field": {
            "type": "string",
            "title": "Name",
            "description": "Enter your full name",
            "examples": ["John Doe"],
            "minLength": 2,
            "maxLength": 100,
        },
        "textarea_field": {
            "type": "string",
            "title": "Comments",
            "description": "Additional notes or comments",
            "x-ui": {"widget": "textarea"},
        },
        "number_field": {
            "type": "number",
            "title": "Amount",
            "description": "Enter amount",
            "minimum": 0,
            "maximum": 10000,
        },
        "boolean_field": {
            "type": "boolean",
            "title": "I agree to terms",
            "description": "Check to agree to terms and conditions",
        },
        "checkbox_field": {"type": "boolean", "title": "Subscribe to newsletter", "x-ui": {"widget": "checkbox"}},
        "select_field": {
            "type": "string",
            "title": "Department",
            "description": "Select your department",
            "enum": ["Engineering", "Sales", "Marketing", "HR"],
        },
        "radio_field": {
            "type": "string",
            "title": "Priority",
            "enum": ["Low", "Medium", "High"],
            "x-ui": {"widget": "radio"},
        },
        "multiselect_field": {
            "type": "array",
            "title": "Skills",
            "description": "Select all that apply",
            "items": {"type": "string", "enum": ["Python", "JavaScript", "Java", "C++"]},
        },
        "date_field": {
            "type": "string",
            "format": "date",
            "title": "Start Date",
            "description": "Select start date",
            "x-ui": {"minDate": "2024-01-01", "maxDate": "2025-12-31"},
        },
        "slider_field": {
            "type": "number",
            "title": "Rating",
            "minimum": 0,
            "maximum": 10,
            "multipleOf": 1,
            "x-ui": {"widget": "slider"},
        },
        "rating_field": {
            "type": "number",
            "title": "Satisfaction",
            "minimum": 1,
            "maximum": 5,
            "x-ui": {"widget": "rating"},
        },
        "file_upload_single": {
            "type": "string",
            "title": "Upload Document",
            "description": "Upload a file",
            "x-ui": {
                "widget": "file",
                "accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png,.csv,.txt,.json,.hocon",
                "maxFiles": 1,
                "maxSize": 26214400,  # 25MB in bytes
            },
        },
        "file_upload_multiple": {
            "type": "array",
            "items": {"type": "string"},
            "title": "Upload Files",
            "description": "Upload multiple files",
            "x-ui": {
                "widget": "file",
                "accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png,.csv,.txt,.json,.hocon",
                "maxFiles": 5,
                "maxSize": 26214400,  # 25MB in bytes per file
            },
        },
    }

    # Icon guidance with creative examples
    ICON_GUIDANCE = {
        "icon_library": """Full Material Design Icons library available at:
        https://github.com/google/material-design-icons/blob/master/font/MaterialIcons-Regular.codepoints""",
        "naming_convention": """Icons use snake_case in the library but should be converted to PascalCase
        (e.g., 'beach_access' → 'BeachAccess', 'flight_takeoff' → 'FlightTakeoff')""",
        "creative_examples": {
            "Vacation & Time Off": ["BeachAccess", "Surfing", "Pool", "AcUnit", "WbSunny", "Flight", "Luggage"],
            "Travel & Transportation": [
                "FlightTakeoff",
                "FlightLand",
                "Luggage",
                "Hotel",
                "DirectionsCar",
                "Train",
                "Sailboat",
            ],
            "Food & Dining": [
                "Restaurant",
                "LocalCafe",
                "Cake",
                "LocalPizza",
                "Icecream",
                "EmojiFoodBeverage",
                "RamenDining",
            ],
            "Health & Wellness": [
                "FitnessCenter",
                "Spa",
                "SelfImprovement",
                "Psychology",
                "Favorite",
                "LocalHospital",
                "Healing",
            ],
            "Finance & Banking": [
                "AccountBalance",
                "Savings",
                "TrendingUp",
                "MonetizationOn",
                "CreditCard",
                "Receipt",
                "AttachMoney",
            ],
            "Home & Living": ["Weekend", "Bed", "Shower", "KitchenOutlined", "Chair", "DoorFront", "Checkroom"],
            "Entertainment": [
                "Theaters",
                "Museum",
                "Casino",
                "SportsEsports",
                "MusicNote",
                "Celebration",
                "Nightlife",
            ],
            "Nature & Outdoors": ["Park", "Hiking", "NaturePeople", "Forest", "Landscape", "Pets", "Eco"],
            "Shopping & Retail": [
                "ShoppingBag",
                "Storefront",
                "LocalOffer",
                "Loyalty",
                "CardGiftcard",
                "ShoppingCart",
            ],
            "Work & Productivity": [
                "WorkOutline",
                "Apartment",
                "BusinessCenter",
                "Laptop",
                "Badge",
                "Groups",
                "Assignment",
            ],
            "Communication": ["Forum", "Chat", "Call", "VideoCall", "Email", "Feedback", "Announcement"],
            "Events & Celebrations": [
                "Celebration",
                "Cake",
                "CardGiftcard",
                "Redeem",
                "LocalActivity",
                "ConfirmationNumber",
            ],
            "Education": ["School", "AutoStories", "Science", "Calculate", "HistoryEdu", "Psychology", "MenuBook"],
            "Technology": ["Devices", "Computer", "PhoneIphone", "DeveloperMode", "Cloud", "Storage", "Terminal"],
            "Security & Safety": [
                "Security",
                "Shield",
                "Lock",
                "Fingerprint",
                "VerifiedUser",
                "AdminPanelSettings",
                "GppGood",
            ],
            "Documents & Files": [
                "Description",
                "Folder",
                "UploadFile",
                "CloudUpload",
                "FileCopy",
                "AttachFile",
                "PictureAsPdf",
            ],
        },
        "selection_principles": [
            "Choose icons that capture the ESSENCE of the request, not just literal meaning",
            "For vacation requests, prefer 'BeachAccess' or 'Luggage' over generic 'CalendarMonth'",
            "For expense reports, prefer 'Receipt' or 'AccountBalance' over generic 'AttachMoney'",
            "For meeting rooms, prefer 'MeetingRoom' over generic 'Room'",
            "For sick leave, prefer 'LocalHospital' or 'Healing' over generic 'CalendarMonth'",
            "Be creative and contextual - make the icon visually appealing and memorable",
            "The frontend dynamically resolves any valid Material Design icon name",
        ],
    }

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Provides widget schema template and examples.

        :param args: An argument dictionary whose keys are the parameters
            to the coded tool and whose values are the values passed for
            them by the calling agent. This dictionary is to be treated as
            read-only.

            The argument dictionary can contain:
                "request_type": "template" | "examples" | "icons" | "full"

        :param sly_data: A dictionary whose keys are defined by the agent
            hierarchy, but whose values are meant to be kept out of the
            chat stream.

        :return: JSON string containing requested information
        """
        request_type = args.get("request_type", "full")

        result = {}

        if request_type in ["template", "full"]:
            result["template"] = self.WIDGET_SCHEMA_TEMPLATE

        if request_type in ["examples", "full"]:
            result["widget_type_examples"] = self.WIDGET_TYPE_EXAMPLES

        if request_type in ["icons", "full"]:
            result["icon_guidance"] = self.ICON_GUIDANCE

        if request_type == "full":
            result["instructions"] = {
                "overview": "Generate widget definitions by filling in the template based on conversation context",
                "widget_types": [
                    "text - Single-line text input (default for string type)",
                    "textarea - Multi-line text input (use x-ui.widget: 'textarea')",
                    "number - Numeric input (type: number or integer)",
                    "boolean - Toggle switch (type: boolean)",
                    "checkbox - Checkbox input (type: boolean with x-ui.widget: 'checkbox')",
                    "select - Dropdown selection (use enum array)",
                    "radio - Radio button group (use enum with x-ui.widget: 'radio')",
                    "multiselect - Multiple selection (type: array with items.enum)",
                    "date - Date picker (format: 'date' or 'date-time')",
                    "slider - Range slider (number with minimum, maximum, multipleOf)",
                    "rating - Star rating (number with x-ui.widget: 'rating')",
                    "file - File upload with drag-and-drop (use x-ui.widget: 'file' with accept, maxFiles, maxSize)",
                ],
                "key_points": [
                    "Replace <PLACEHOLDERS> with actual values from conversation",
                    "Remove example comments and unused optional fields",
                    "Use appropriate field types based on data requirements",
                    "Set 'required' array for mandatory fields",
                    "Choose meaningful icons and colors that match the context",
                    "Provide helpful descriptions and examples for clarity",
                    "Field descriptions are shown as help text once - avoid redundancy",
                    "Use format: 'date' for date pickers (no additional validation needed)",
                    "Only add validation (minDate, maxDate) when business logic requires it",
                    "Icons are displayed prominently - choose ones that match the widget purpose",
                ],
            }

        return json.dumps(result, indent=2)

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
