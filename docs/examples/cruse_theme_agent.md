# CRUSE Theme Agent

The **CRUSE Theme Agent** is a specialized agent designed to generate context-aware visual themes for the CRUSE (Context Reactive User Experience) Interface in nsflow. It analyzes agent metadata to create dynamic or static background themes that match the agent's domain and purpose.

The theme agent transforms the user experience by providing:
- **Visual Identity** - Each agent gets a unique, domain-appropriate background
- **Dynamic Patterns** - css-doodle generative patterns for engaging visuals
- **Professional Polish** - Automatically generated, production-ready backgrounds
- **Context Awareness** - Themes that reflect the agent's industry and purpose

The CRUSE Interface is available at `/cruse` in nsflow and renders these themes.

---

## Files

- **Agent Definition**: [cruse_theme_agent.hocon](../registries/cruse_theme_agent.hocon)
- **Coded Tool**: [theme_template_provider.py](../coded_tools/cruse_theme_agent/theme_template_provider.py)
- **Constants**: [cruse_theme_constants.py](../coded_tools/cruse_theme_agent/cruse_theme_constants.py)

---

## Description

The CRUSE Theme Agent analyzes agent metadata (including agent's connectivity graph, description, tags, and sample queries) to generate visually appropriate background themes. It supports two types of backgrounds:

### Dynamic Backgrounds (css-doodle)
- Uses [css-doodle](https://css-doodle.com/), a web component for drawing patterns with CSS
- Generates procedural, generative patterns using CSS-only techniques
- Lightweight and performant (no canvas/WebGL)
- Supports animations, randomization, and complex patterns
- Examples: neural networks, geometric tech patterns, organic dots, data waves

### Static Backgrounds (CSS Gradients)
- Uses native CSS gradients (linear, radial, conic)
- Smooth, professional color transitions
- Zero dependencies, minimal overhead
- Perfect for formal business contexts

The agent uses a **template-based approach** with domain-specific patterns.

---

## Example Conversation

### Human: 
```text
"generate a dynamic theme for Airline policy assistant",
```

### AI (cruse_theme_agent)
```json
{
  "type": "css-doodle",
  "grid": "12x8",
  "seed": "agent:airline_policy",
  "rules": ":doodle { @grid: 12x8 / 100vmax; background: linear-gradient(135deg, #0c4a6e 0%, #1e3a8a 100%); } :before { content: ''; @size: 100%; @place: center; background: radial-gradient(ellipse at 30% 20%, rgba(56, 189, 248, 0.15), transparent 60%), radial-gradient(ellipse at 70% 80%, rgba(96, 165, 250, 0.1), transparent 55%); } :after { content: ''; @size: @rand(8%, 16%); @place: @rand(100%) @rand(100%); background: rgba(96, 165, 250, 0.08); border-radius: 50%; transform: translate(@rand(-50%, 50%), @rand(-50%, 50%)) scale(@rand(0.8, 1.3)); }",
  "vars": {
    "--bg": "#0c4a6e",
    "--accent": "#38bdf8",
    "--accent-soft": "#60a5fa"
  }
}
```
---

## Architecture Overview

### Frontman Agent: `theme_generator`

The theme generator serves as the single entry point for all theme generation requests.

**Key Responsibilities:**
- Analyze agent metadata (connectivity graph, description, tags, sample queries)
- Parse agent domain and determine appropriate visual style
- Select or customize background patterns from template library
- Apply color psychology based on domain
- Generate valid JSON schemas for frontend rendering

### Functional Tools

**`template_provider`** ([theme_template_provider.py](../coded_tools/cruse_theme_agent/theme_template_provider.py))

Provides comprehensive background resources:
- Pre-built css-doodle templates for common domains
- CSS gradient patterns and color schemes
- Color psychology reference for domain-specific palettes
- css-doodle syntax guidance and examples
- Accepts `request_type`: `"css-doodle"`, `"gradient"`, `"colors"`, or `"full"`

**Template Constants** ([cruse_theme_constants.py](../coded_tools/cruse_theme_agent/cruse_theme_constants.py))
- `CSS_DOODLE_TEMPLATES` - 11 pre-built patterns for common domains
- `GRADIENT_TEMPLATES` - Static gradient examples
- `COLOR_PALETTES` - Domain-specific color schemes with psychology notes

---

## Environment Configuration

Configure the theme agent via environment variables (future):

```bash
# CRUSE Plugin - Enable/disable CRUSE interface
NSFLOW_PLUGIN_CRUSE=true

# Theme Agent Name - Customize if needed
NSFLOW_CRUSE_THEME_AGENT_NAME=cruse_theme_agent
```

If `NSFLOW_PLUGIN_CRUSE=false`, the CRUSE interface is hidden.

---

## Debugging Hints

### Issue: css-doodle syntax errors (for a frontend component)

**Symptoms**: Console errors, blank background

**Diagnosis:**
- Review agent instructions for correct css-doodle syntax
- Test rules at https://css-doodle.com playground
- Ensure variables defined in `vars` before using in `rules`
- Check for unescaped quotes in rules string

**Solutions:**
```javascript
// Test individual rules
<css-doodle>
  @grid: 10;
  background: red;
</css-doodle>

// Verify variable usage
<css-doodle>
  :doodle {
    --color: blue;
  }
  background: var(--color);
</css-doodle>
```

### Issue: Colors not as expected

**Symptoms**: Colors don't match domain expectations

**Diagnosis:**
- Review COLOR_PALETTES in cruse_theme_constants.py
- Check if domain-specific colors exist
- Verify agent correctly identified domain

**Solutions:**
- Add domain-specific colors to COLOR_PALETTES
- Update agent instructions with color psychology guidance
- Provide user prompt to override colors

### Test Agent Directly

```bash
# Test theme generation (assuming you are using port 4173 here)
curl -X POST http://localhost:4173/api/v1/oneshot/chat \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "cruse_theme_agent",
    "message": "{\"agent_details\": {\"metadata\": {\"description\": \"Financial advisor\", \"tags\": [\"finance\", \"banking\"]}}, \"background_type\": \"dynamic\"}"
  }'
```

---

## References

### External Documentation
- [css-doodle Official Docs](https://css-doodle.com/) - Complete reference for css-doodle syntax
- [css-doodle GitHub](https://github.com/css-doodle/css-doodle) - Source code and examples
- [CSS Gradients MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/gradient) - CSS gradient reference

---
