# CRUSE -  Interface

CRUSE (Context-React User Experience) is a dynamic interface for interacting with agent networks. It supports **dynamic form widgets**, offers visual tools like a **floating panel** for logs and agent flow, and features **dynamic AI-generated themes** that give each agent network a unique visual identity and organizes your conversations into **threads**.

---

## Getting Started

1. Navigate to the **Cruse** page from the top navigation bar.
2. Select an agent network from the **sidebar dropdown**.
3. A new thread is created automatically. Start typing your message and press **Enter** to send.

---

## Threads

Threads are saved conversations. Each thread belongs to a specific agent network.

- **Create**: Click the **+ New Thread** button in the sidebar.
- **Switch**: Click any thread in the sidebar list to load it.
- **Delete**: Hover over a thread and click the trash icon.
- **Delete All**: Open **Settings** (gear icon) at the bottom of the sidebar and choose **Delete All Threads**.

Thread titles are auto-generated from your first message.

---

## Chat

- Type a message in the input area and press **Enter** to send (Shift+Enter for a new line).
- AI responses appear on the left; your messages appear on the right.
- A **thinking indicator** shows elapsed time while the agent is processing.
- **Sample queries** are shown at the top of a new thread to help you get started. Click one to send it instantly.

---

## Widgets

Some agent responses include interactive **widget cards** - small forms embedded in the chat.

- Fill in the fields and click **Submit** to send your input back to the agent.
- Required fields are marked - the form won't submit until they are filled.
- Use the **copy** button on a widget to copy its data as JSON.
- Widgets can be collapsed or expanded by clicking their header.

---

## Floating Panel

A collapsible panel at the bottom-right corner with two tabs:

- **Logs**: Shows real-time execution logs from the agent network.
- **Flow**: Displays a visual graph of the agent network and how agents connect.

Toggle it from **Settings > Show Floating Menu**. You can resize it by dragging the corner handle, and pin it open so it doesn't close when you click elsewhere.

---

## Themes

Cruse supports dynamic visual themes that change the background and overall look.

To customize:

1. Open **Settings** (gear icon) in the sidebar.
2. Optionally enter a prompt describing the theme you want (e.g., "ocean sunset").
3. Click the **refresh** button to generate a new theme.
4. Adjust **Glass Effect** sliders to control the transparency and blur of the chat panels.

Check **Modify Background** to evolve the current theme rather than generating a brand new one.

---

## Good to Know

- When you select a new agent network for the first time, wait a few seconds before interacting - the dynamic theme may take a moment to load.
- The sidebar can be collapsed to icon-only mode for more chat space.
- The last 10 messages in a thread are sent as context with each new message, so the agent remembers your conversation.
- Threads and settings are saved automatically - you can close the browser and come back later.
