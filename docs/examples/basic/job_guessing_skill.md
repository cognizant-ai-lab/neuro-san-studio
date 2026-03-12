# Job Guessing Skill

The **Job Guessing Skill** agent network is a demonstration network designed to showcase how the
[`AgentSkillsMiddleware`](../../../middleware/agent_skills_middleware.py) implements the
[Agent Skills specification](https://agentskills.io/specification)
with progressive disclosure and multi-file skill loading.

---

## File

[job_guessing_skill.hocon](../../../registries/basic/job_gussing_skill.hocon)

---

## Description

The Job Guessing Skill agent network provides a practical example of how an agent can use the `AgentSkillsMiddleware`
to load and utilize skills following the Agent Skills specification.

The network demonstrates:
- **Progressive disclosure**: Skill metadata loaded first, full content on demand
- **Multi-file skills**: Loading additional resources (LOCATION.md, SALARY.md) referenced in SKILL.md
- **Token optimization**: Optional content summarization to save context space
- **Security validation**: Path/URL validation to prevent SSRF and path traversal attacks

The agent can determine a person's career, location, and salary based on their name using a simple mapping skill
with additional resource files.

Note: The following skills are intended for testing only.
Personal or sensitive information should not be included in agent skills.

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

### Environment Variables
```bash
OPENAI_API_KEY=your-api-key-here
ANTHROPIC_API_KEY=your-api-key-here
```

or any API key of your preferred providers.

---

## Example Conversation

### Human
```text
What does Bob do for a living?
```

The agent will use the `name-analytics` skill to determine Bob's career.

### AI
```text
I'll check the name analytics skill for information about Bob.

[loads skill content]

Bob is a physicist.
```

### Human
```text
Where does he work and what's his salary?
```

The agent will load additional resources (LOCATION.md and SALARY.md) to provide complete information.

### AI
```text
[loads LOCATION.md and SALARY.md]

Bob works in San Francisco and earns $300,000 per year.
```

---

## Architecture Overview

### Agent: name_assistant

- **Entry point** for user queries about names and careers
- Uses `AgentSkillsMiddleware` with progressive disclosure pattern
- Can load skill content and additional resources on demand

### Middleware: AgentSkillsMiddleware

The middleware manages skill lifecycle:

1. **Initialization** (`abefore_agent`): 
   - Creates HTTP session
   - Scans skill sources for SKILL.md files
   - Caches skill metadata (name, description, path)

2. **System Prompt Injection** (`awrap_model_call`):
   - Adds available skills list to system prompt
   - Provides usage instructions following Agent Skills spec

3. **Tool Execution** (`awrap_tool_call`):
   - Optionally replaces skill content with summary (if `keep_skill_in_context=False`)
   - Saves tokens in long conversations

4. **Cleanup** (`aafter_agent`):
   - Closes HTTP session after agent execution

### Tools Provided

- `get_full_skill_content`: Load complete SKILL.md with instructions
- `load_skill_resource_local`: Load additional files from local filesystem
- `load_skill_resource_remote`: Load additional files from remote URLs

### Skill Structure
```
skills/tests/job_guessing/
├── SKILL.md              # Main skill file with YAML frontmatter
├── location/
│   └── LOCATION.md       # Additional resource (name → location mapping)
└── SALARY.md             # Additional resource (name → salary mapping)
```

---

## Configuration Options

### `keep_skill_in_context`

Controls token usage vs. cross-skill synthesis:

**When set to `false` (default, recommended):**
- Skill content replaced with "[Loaded and applied]" summary after use
- Saves significant tokens in long conversations
- Agent may re-load skills if needed (rare)
- **Best for**: Most use cases, token-constrained environments

**When set to `true`:**
- Skill content remains in chat history after loading
- Agent can reference and combine information from multiple skills
- Higher token usage but fewer redundant tool calls
- **Best for**: Complex tasks requiring cross-referencing multiple skills

---

## Debugging Hints

### Common Issues

**Skills not loading:**
- Check that `skill_sources` paths are correct
- Verify SKILL.md files have valid YAML frontmatter
- Check logs for validation errors

**HTTP timeout errors:**
- Increase `http_timeout` in middleware configuration
- Check network connectivity to remote skill sources
- Verify remote URLs are accessible

**Path validation errors:**
- Ensure resource paths are under configured `skill_sources`
- Check for path traversal attempts (../) in logs
- Verify file paths match skill directory structure

**Agent not using skills:**
- Check system prompt injection in debug logs
- Verify skill descriptions match user query intent
- Ensure tools are registered correctly

---

## Resources

- [Agent Skills Specification](https://agentskills.io/specification)    
Complete format specification for SKILL.md files and skill structure

- [Agent Network Hocon specification](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#middleware)     
How to define middleware instances in agent network configurations

- [AgentMiddleware Overview](https://docs.langchain.com/oss/python/langchain/middleware/overview)   
General overview of the middleware pattern in LangChain

- [Progressive Disclosure Pattern](https://agentskills.io/specification#progressive-disclosure)     
Best practices for structuring skills with metadata → instructions → resources

---
