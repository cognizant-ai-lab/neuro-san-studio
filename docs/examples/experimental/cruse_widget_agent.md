# CRUSE Widget Agent

The **CRUSE Widget Agent** is a specialized agent designed to generate context-aware interactive widgets for the CRUSE (Context Reactive User Experience) Interface in nsflow. It analyzes conversation context to determine when users need to provide structured input, then creates appropriate JSON schema definitions for dynamic form widgets.

The widget agent transforms user interactions by providing:
- **Structured Data Collection** - Rich form inputs instead of natural language
- **Context-Aware Forms** - Widgets tailored to user intent and conversation flow
- **Professional UI** - Automatically generated, production-ready form components
- **Validation** - Built-in field validation and error handling

The CRUSE Interface is available at `/cruse` in nsflow and displays these widgets inline within the chat conversation.

---

## Files

- **Agent Definition**: [cruse_widget_agent.hocon](../registries/cruse_widget_agent.hocon)
- **Coded Tool**: [widget_template_provider.py](../coded_tools/cruse_widget_agent/widget_template_provider.py)

---

## Description

The CRUSE Widget Agent analyzes conversation context to generate appropriate JSON schema definitions for dynamic widgets. These widgets appear inline in the chat interface, allowing users to input data through rich UI components.

### Supported Field Types

The agent supports a comprehensive set of field types:
- **Text inputs**: Single-line text, multi-line textarea
- **Numbers**: Integer/decimal inputs, sliders, ratings
- **Selections**: Dropdowns, radio buttons, multi-select, checkboxes
- **Dates**: Date pickers with optional constraints
- **Files**: Drag-and-drop file upload with validation
- **Booleans**: Toggle switches, checkboxes

### Context-Aware Generation

Widget generation is **context-aware**, meaning the agent:
- Identifies when structured input is needed from conversation flow
- Selects appropriate field types based on data requirements
- Chooses contextually meaningful icons from Material Design Icons
- Applies proper validation rules (required fields, min/max, patterns)
- Provides helpful descriptions and examples

### When Widgets Appear

Widgets are displayed when:
- User requests a specific action (time off, expense report, booking)
- Conversation hints at options for selection
- Main agent determines structured input is more appropriate than natural language

Widgets are **NOT** displayed when:
- User is having casual conversation
- No structured input is needed
- Natural language is more appropriate

---

## Example Conversations

### Example 1: Time Off Request

**Human**: "I need to request time off"
**Main Agent**: In order to request time-off, you need to provide information such as start date, end date, type of vacation and reason.

**Main Agent** -> **Widget Agent**:
```json
{
  "human_message": "User: I need to request time off",
  "ai_message": "In order to request time-off, you need to provide information such as start date, end date, type of vacation and reason."
}
```

**AI (cruse_widget_agent)**:
```json
{
  "title": "Time Off Request",
  "description": "Submit your time off request for manager approval",
  "icon": "BeachAccess",
  "color": "#1976d2",
  "schema": {
    "type": "object",
    "title": "Time Off Request Form",
    "properties": {
      "startDate": {
        "type": "string",
        "format": "date",
        "title": "Start Date",
        "description": "First day of time off"
      },
      "endDate": {
        "type": "string",
        "format": "date",
        "title": "End Date",
        "description": "Last day of time off"
      },
      "type": {
        "type": "string",
        "title": "Leave Type",
        "enum": ["Vacation", "Sick Leave", "Personal Day", "Other"]
      },
      "reason": {
        "type": "string",
        "title": "Reason",
        "description": "Brief explanation for time off request",
        "x-ui": {"widget": "textarea"}
      }
    },
    "required": ["startDate", "endDate", "type"]
  }
}
```

### Example 2: Expense Report

**Human**: "Help me report an expense"
**Main Agent**: I can help with expense report. Be ready with the expense date, category, amount, description and a receipt.

**AI (cruse_widget_agent)**:
```json
{
  "title": "Expense Report",
  "description": "Submit an expense for reimbursement",
  "icon": "Receipt",
  "color": "#10b981",
  "schema": {
    "type": "object",
    "properties": {
      "date": {
        "type": "string",
        "format": "date",
        "title": "Expense Date",
        "description": "Date the expense was incurred"
      },
      "category": {
        "type": "string",
        "title": "Category",
        "enum": ["Travel", "Meals", "Office Supplies", "Software", "Other"]
      },
      "amount": {
        "type": "number",
        "title": "Amount",
        "description": "Expense amount in USD",
        "minimum": 0,
        "maximum": 10000
      },
      "description": {
        "type": "string",
        "title": "Description",
        "description": "Brief description of the expense",
        "x-ui": {"widget": "textarea"}
      },
      "receipt": {
        "type": "string",
        "title": "Receipt",
        "description": "Upload receipt image or PDF",
        "x-ui": {
          "widget": "file",
          "accept": ".pdf,.jpg,.jpeg,.png",
          "maxFiles": 1,
          "maxSize": 26214400
        }
      }
    },
    "required": ["date", "category", "amount", "receipt"]
  }
}
```

---

## Material Design Icons

The widget agent has access to the full [Material Design Icons library](https://github.com/google/material-design-icons/blob/master/font/MaterialIcons-Regular.codepoints) with 2,000+ icons.

### Icon Naming Convention
- Library uses `snake_case` (e.g., `beach_access`, `flight_takeoff`)
- Frontend expects `PascalCase` (e.g., `BeachAccess`, `FlightTakeoff`)
- The agent converts automatically when selecting icons

---

## Architecture Overview

### Frontman Agent: `widget_generator`

The widget generator serves as the single entry point for all widget generation requests.

**Key Responsibilities:**
- Analyze conversation context to understand user intent
- Determine if a widget is actually needed (returns `{"display": false}` if not)
- Identify required fields and appropriate field types
- Select contextually meaningful icons from Material Design Icons
- Apply validation rules (required, min/max, patterns)
- Generate valid JSON schemas for frontend rendering

### Functional Tools

**`template_provider`** ([widget_template_provider.py](../coded_tools/cruse_widget_agent/widget_template_provider.py))

Provides comprehensive widget resources:
- Base widget schema template with placeholders
- Field type examples for all supported inputs
- Material Design Icons library reference with creative guidance
- Validation patterns and UI hints
- Accepts `request_type`: `"template"`, `"examples"`, `"icons"`, or `"full"`

---

## Environment Configuration

Configure the widget agent via environment variables (future):

```bash
# CRUSE Plugin - Enable/disable CRUSE interface
NSFLOW_PLUGIN_CRUSE=true

# Widget Agent Name - Customize if needed
NSFLOW_CRUSE_WIDGET_AGENT_NAME=cruse_widget_agent
```

If `NSFLOW_PLUGIN_CRUSE=false`, the CRUSE interface is hidden and widgets don't appear.

---

## Debugging Hints

### Issue: Widget not displaying (for a frontend component)

**Symptoms**: No widget appears after agent call

**Diagnosis:**
- Check that schema has `"display": true` (or field not present)
- Verify JSON schema is valid (use jsonschema validator)
- Ensure required fields array contains valid property names
- Check browser console for json-edit-react errors

**Solutions:**
```javascript
// Validate schema structure
const Ajv = require('ajv');
const ajv = new Ajv();
const valid = ajv.validate(widgetSchema.schema, {});
console.log(valid, ajv.errors);

// Check widget display flag
console.assert(widgetSchema.display !== false, 'Widget display is false');
```

### Issue: Icon not displaying

**Symptoms**: Generic icon shown instead of specified one

**Diagnosis:**
- Verify icon name is in PascalCase (not snake_case)
- Check Material Design Icons library for valid names
- Frontend dynamically imports icons, so any valid MUI icon works
- Fallback to generic icon if name invalid

**Solutions:**
```javascript
// Test icon loading
import * as Icons from '@mui/icons-material';
const Icon = Icons['BeachAccess'];
console.log(Icon ? 'Icon exists' : 'Icon not found');
```

### Test Agent Directly

```bash
# Test widget generation (assuming you are using port 4173 here)
curl -X POST http://localhost:4173/api/v1/oneshot/chat \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "cruse_widget_agent",
    "message": "{\"conversation_context\": \"User: I need to request time off\"}"
  }'
```

---
