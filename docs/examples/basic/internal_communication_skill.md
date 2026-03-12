# Internal Communication Skill

The **Internal Communication Skill** agent network demonstrates how
[`AgentSkillsMiddleware`](../../../middleware/agent_skills_middleware.py) can manage a multi-file skill with branching
workflows, where the agent dynamically selects the appropriate communication format (3P updates, newsletters, FAQs, or
general communications) based on the user's request and follows format-specific guidelines.

---

## File

[internal_communication_skill.hocon](../../../registries/basic/internal_communication_skill.hocon)

---

## Description

The Internal Communication Skill agent network showcases a real-world skill structure where:
- **Single entry point (SKILL.md)** routes to different communication formats
- **Multiple example files** (`examples/` directory) provide format-specific instructions
- **Dynamic workflow selection** based on communication type identification
- **Tool integration guidance** for pulling data from Slack, Google Drive, Email, Calendar

The agent can write various internal communications following company-specific formats:
- **3P Updates** (Progress, Plans, Problems) - Weekly team status reports
- **Company Newsletters** - Company-wide announcements and highlights
- **FAQ Responses** - Answering frequently asked questions
- **General Communications** - Other internal messaging needs

---

## ⚠️ Security Warning

**Skill loading from remote URLs introduces security risks in production environments:**

### Network-Based Risks

- **SSRF (Server-Side Request Forgery)**: The agent can fetch arbitrary URLs if not properly restricted
- **Path Traversal**: Local file system access without validation can expose sensitive files
- **Data Exfiltration**: Remote URL fetching could leak data to attacker-controlled endpoints

### Skill Content Risks

**Be cautious when using skills from the internet.** They may contain:
- **Malicious scripts**: Untrusted code that could compromise your system
- **Unavailable tools**: References to tools or resources not present in your environment
- **Malicious instructions**: Prompts designed to manipulate agent behavior

**Always review skill contents carefully before using them in your agent.** Inspect:
- SKILL.md for unexpected instructions or tool references
- Any referenced scripts in `scripts/` directories
- External URLs or resources referenced in skill files

### Mitigations Implemented

- URL/path validation restricts loading to configured `skill_sources` only
- HTTP timeouts prevent hanging on unresponsive servers
- Shared session management reduces connection overhead

### For Production Use

- **Use local filesystem skills only**, or
- **Whitelist specific remote domains/repositories** (e.g., only allow official repositories)
- **Review all remote skills** before adding to `skill_sources`
- **Run in sandboxed environments** with network egress controls
- **Monitor and log all skill resource fetches**
- **Implement code review** for any skills with `scripts/` directories

---

## Prerequisites

This agent network requires the following setup:

```bash
OPENAI_API_KEY=your-api-key-here
ANTHROPIC_API_KEY=your-api-key-here
```

or any API key of your preferred providers.

### Optional Tool Integrations

For full functionality, configure access to:
- **Slack API** - For reading messages and channels
- **Google Drive API** - For accessing documents
- **Email (IMAP/Exchange)** - For reading company emails
- **Calendar API** - For meeting information

*Note: The skill works without these integrations by asking the user to provide information directly.*

---

## Example Conversations

### Example 1: 3P Update

#### Human
```text
Write a 3P update for the engineering team for this week.
```

#### AI
```text
I'll help you write a 3P update. Let me load the 3P update guidelines.

[loads examples/3p-updates.md]

Before I draft this, I need to clarify:
- What is the specific team name? (e.g., "Mobile Engineering", "Backend Team")
- Do you have access to Slack/Drive/Email, or would you like to provide the information directly?
```

#### Human
```text
It's the Mobile Team. Here's what we did:
- Shipped the new onboarding flow
- Fixed 15 critical bugs
- Started work on the payment integration
```

#### AI
```text
📱 Mobile Team (Dec 4-8, 2024)

Progress: Shipped new onboarding flow to production, resolved 15 critical bugs affecting user experience

Plans: Begin payment integration work, continue bug fixes for upcoming release

Problems: None at this time
```

### Example 2: Company Newsletter

#### Human
```text
Create this week's company newsletter.
```

#### AI
```text
I'll create a company newsletter. Let me load the newsletter guidelines.

[loads examples/company-newsletter.md]

To create a comprehensive newsletter, I can pull information from:
- Slack announcements
- Recent Google Drive documents
- Company-wide emails
- Calendar events

Do you have these tools connected, or would you like to provide highlights directly?
```

### Example 3: FAQ Response

#### Human
```text
Answer the FAQ: When is the new office opening?
```

#### AI
```text
[loads examples/faq-answers.md]

*Question*: When is the new office opening?

*Answer*: The new San Francisco office is scheduled to open on January 15, 2025, with move-in
beginning the week of January 8.
```

---

## Architecture Overview

### Agent: comms_assistant

- **Entry point** for internal communication requests
- Uses `AgentSkillsMiddleware` to load the `internal-comms` skill
- Dynamically selects appropriate communication format based on request

### Middleware: AgentSkillsMiddleware

Manages the multi-file skill structure:

1. **Initialization** (`abefore_agent`):
   - Loads SKILL.md metadata
   - Caches skill content for quick access

2. **System Prompt Injection** (`awrap_model_call`):
   - Adds available communication formats to system prompt
   - Provides workflow instructions

3. **Resource Loading**:
   - Agent loads appropriate example file (e.g., `examples/3p-updates.md`)
   - Follows format-specific instructions

4. **Cleanup** (`aafter_agent`):
   - Closes HTTP session

### Skill Structure
```
skills/internal-comms/
├── SKILL.md                    # Main skill file with routing logic
├── LICENSE.txt                 # License information
└── examples/
    ├── 3p-updates.md          # Progress/Plans/Problems format
    ├── company-newsletter.md  # Newsletter format
    ├── faq-answers.md         # FAQ response format
    └── general-comms.md       # Catch-all format
```

### Workflow

1. **User requests** internal communication
2. **Agent identifies type** (3P, newsletter, FAQ, or general)
3. **Agent loads** appropriate example file using `load_skill_resource_local`
4. **Agent follows** format-specific instructions
5. **Agent gathers** information (via tools or user input)
6. **Agent drafts** communication following guidelines

---

## Configuration Options

### `keep_skill_in_context`

**Recommended setting**: `false` for this skill

Since communication formats are loaded dynamically based on request type, keeping full skill content in context isn't
necessary. The agent can reload the appropriate format file if needed.

---

## Debugging Hints

### Common Issues

**Agent not selecting correct format:**
- Check that request clearly indicates communication type
- Review system prompt injection for format list
- Verify all example files exist in `examples/` directory

**Tool integration failures:**
- Ensure required API credentials are configured
- Check tool permissions and scopes
- Verify network access to external services
- Review tool call logs for authentication errors

**Format not followed:**
- Verify the correct example file was loaded
- Check that example file contains complete formatting instructions
- Ensure agent is following "strict formatting" guidelines from the file

**Missing context:**
- If tools aren't available, agent should ask user for information
- Check that fallback prompts are working ("ask the user directly")

---

## Resources

- [Internal Communication Skill](https://github.com/anthropics/skills/tree/main/skills/internal-comms)  
Skill directory

- [Agent Skills Specification](https://agentskills.io/specification)    
Format specification for SKILL.md files

- [Progressive Disclosure Pattern](https://agentskills.io/specification#progressive-disclosure)     
Best practices for multi-file skills

- [Agent Network Hocon specification](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#middleware)     
Middleware configuration in agent networks

---
