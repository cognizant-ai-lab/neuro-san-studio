# Gmail Assistant

The **Gmail Assistant** is a task-oriented agentic system designed to help users manage their Gmail accounts efficiently.
It leverages a specialized toolkit of Gmail-related tools—such as searching, reading, drafting, and sending emails—through
a dedicated assistant agent.

This system demonstrates how tool-based delegation can automate and streamline email workflows using natural language commands.

---

## File

[gmail.hocon](../../../registries/tools/gmail.hocon)

---

## Description

At the core of the system is the Gmail Assistant agent, which serves as the primary interface between the user and the
underlying Gmail tools. When a user gives an instruction—such as “find emails from Alice” or “send a follow-up email”—the
agent intelligently routes the request to the appropriate tool in the Gmail Toolkit.

- **Modular Email Management**: Each Gmail operation is encapsulated in a tool, making the system easily extensible and composable.

- **Context-Aware Execution**: The assistant handles multi-step tasks by chaining tool outputs.

- **Natural Language Control**: Users can express email intents conversationally, without needing to know the underlying
API details.

---

## Prerequisites

This agent is **disabled by default**. To test it,

- ```bash
  pip install -U langchain-google-community\[gmail\]
  ```

Here are the package versions from the last successful test (neuro-san==0.6.21):

```
google-api-core==2.28.1
google-api-python-client==2.187.0
google-auth==2.41.1
google-auth-httplib2==0.3.0
google-auth-oauthlib==1.2.3
google-cloud-core==2.5.0
google-cloud-modelarmor==0.3.0
googleapis-common-protos==1.72.0
langchain-google-community==3.0.2
```

- Get `credentials.json` by following the instructions from [authorize_credentials_for_a_desktop_application.](
    https://developers.google.com/workspace/gmail/api/quickstart/python#authorize_credentials_for_a_desktop_application)
    and place it at the top level of the repo.
  
---

## Example Conversation

### Human

```text
Can you check if I received an email from Jane yesterday?
```

### AI (Gmail Assistant)

```text
Yes, you received an email from Jane yesterday at 3:47 PM with the subject "Project Update". Would you like me to summarize
it for you?
```

---

## Architecture Overview

### Frontman Agent: Gmail Assistant

- Main entry point for user instructions related to Gmail.

- Interprets commands and delegates tasks to the Gmail Toolkit.

- Coordinates tool outputs to fulfill complex or multi-step actions.

---

### Tools from toolbox

- #### gmail_handler_no_attachment

  These tools are defined in the `gmail_toolkit`, a langchain toolkit that is implemented via `toolbox` and are called
    as needed by the assistant:

    - Email Search (GmailSearch)
    - Email Reader (GmailGetMessage)
    - Thread Reader (GmailGetThread)
    - Draft Composer (GmailCreateDraft)
    - Email Sender (GmailSendMessage)

  > Note that these tools do not support file attachment.

- #### gmail_handler_with_attachment

    This handler includes a single specialized tool designed specifically to send emails **with file attachments**.

---

## Debugging Hints

When developing or debugging the Gmail Assistant, keep the following in mind:

- Make sure both of the `gmail_handler_no_attachment` and `gmail_handler_with_attachment` are correctly registered and mapped
to the valid tool in toolbox.

- Confirm that the Gmail API credentials and OAuth flow are correctly configured.

- Check that each tool receives the necessary arguments (e.g., query, message_id, thread_id, etc.).

- Look at the assistant's delegation logic—ensure it performs appropriate tool calls in the expected sequence.

- Use logging to verify whether drafts are being created and sent as intended.

---

## Resources

- [LangChain Gmail Toolkit Documentation](https://python.langchain.com/docs/integrations/tools/gmail/)
Overview and usage examples of the Gmail tools from the LangChain ecosystem.

- [Toolbox implemenation](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#toolbox)
Learn how Neuro-SAN integrates tools from langchain including setup, configuration, and tool extension.
