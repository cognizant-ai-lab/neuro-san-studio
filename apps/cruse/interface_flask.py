import atexit
import os
import queue

# pylint: disable=import-error
import schedule
from flask import Flask
from flask import jsonify
from flask import render_template
from flask_socketio import SocketIO

from apps.cruse.cruse_assistant import cruse
from apps.cruse.cruse_assistant import get_available_systems
from apps.cruse.cruse_assistant import parse_response_blocks
from apps.cruse.cruse_assistant import set_up_cruse_assistant
from apps.cruse.cruse_assistant import tear_down_cruse_assistant

os.environ["AGENT_MANIFEST_FILE"] = "registries/manifest.hocon"
os.environ["AGENT_TOOL_PATH"] = "coded_tools"

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, ping_timeout=360, ping_interval=25)
thread_started = False  # pylint: disable=invalid-name

user_input_queue = queue.Queue()
gui_context_queue = queue.Queue()

cruse_session, cruse_agent_state = set_up_cruse_assistant(get_available_systems()[0])


def cruse_thinking_process():
    """Main permanent agent-calling loop."""
    with app.app_context():
        global cruse_agent_state  # pylint: disable=global-statement
        user_input = ""

        while True:
            socketio.sleep(1)
            try:
                gui_context = gui_context_queue.get_nowait()
            except queue.Empty:
                gui_context = ""

            if user_input or gui_context:

                print(f"USER INPUT:{user_input}\n\nGUI CONTEXT:{gui_context}\n")
                response, cruse_agent_state = cruse(cruse_session, cruse_agent_state, user_input + str(gui_context))
                print(response)

                blocks = parse_response_blocks(response)

                gui_to_emit = []
                speeches_to_emit = []

                for kind, content in blocks:
                    if not content:
                        continue
                    if kind == "gui":
                        gui_to_emit.append(content)
                    elif kind == "say":
                        speeches_to_emit.append(content)

                # fallback if nothing was matched
                if not blocks and response.strip():
                    speeches_to_emit.append(response.strip())

                if gui_to_emit:
                    socketio.emit("update_gui", {"data": "\n".join(gui_to_emit)}, namespace="/chat")

                if speeches_to_emit:
                    socketio.emit("update_speech", {"data": "\n".join(speeches_to_emit)}, namespace="/chat")

            try:
                user_input = user_input_queue.get_nowait()
                if user_input == "exit":
                    break
            except queue.Empty:
                user_input = ""
                socketio.sleep(1)
                continue


@socketio.on("connect", namespace="/chat")
def on_connect():
    """Start background task on connect."""
    global thread_started  # pylint: disable=global-statement
    if not thread_started:
        thread_started = True
        # let socketio manage the green-thread
        socketio.start_background_task(cruse_thinking_process)


@app.route("/")
def index():
    """Return the html."""
    return render_template("index.html")


@socketio.on("user_input", namespace="/chat")
def handle_user_input(json, *_):
    """
    Handles user input.

    :param json: A json object
    """
    user_input = json["data"]
    user_input_queue.put(user_input)
    socketio.emit("update_user_input", {"data": user_input}, namespace="/chat")


@socketio.on("gui_context", namespace="/chat")
def handle_gui_context(json, *_):
    """
    Handles gui context.

    :param json: A json object
    """
    gui_context = json["gui_context"]
    gui_context_queue.put(gui_context)
    socketio.emit("gui_context_input", {"gui_context": gui_context}, namespace="/chat")


def cleanup():
    """Tear things down on exit."""
    print("Bye!")
    tear_down_cruse_assistant(cruse_session)
    socketio.stop()


@app.route("/shutdown")
def shutdown():
    """Shut down process."""
    cleanup()
    return "Capture ended"


@app.after_request
def add_header(response):
    """Add the header."""
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/systems")
def systems():
    """
    Flask route to retrieve a list of available agent systems.

    Returns:
        Response: A JSON response containing a list of system names derived
                  from the manifest file.
    """
    return jsonify(get_available_systems())


def run_scheduled_tasks():
    """
    Continuously runs pending scheduled tasks.

    This function enters an infinite loop where it checks for and executes any tasks
    that are due to run, as defined in the `schedule` module. It pauses for one second
    between iterations to avoid excessive CPU usage.

    Intended to be run as a background thread or greenlet alongside other application logic.
    """
    while True:
        schedule.run_pending()
        socketio.sleep(1)


@socketio.on("new_chat", namespace="/chat")
def handle_new_chat(data, *args):
    """
    Initializes a new chat session with a selected conversational agent.

    This function resets the current Cruse assistant session and sets up a new one
    based on the provided `data`, which can be either a dictionary (with a "system" key)
    or a direct string specifying the agent name. If no valid agent is specified, it
    defaults to the first available system retrieved by `get_available_systems()`.

    Parameters:
    ----------
    data : dict or str
        The input specifying which agent/system to use. Can be a dictionary containing
        a "system" key or a string representing the agent's name.

    *args : tuple
        Additional arguments (currently unused).

    Side Effects:
    ------------
    - Tears down the existing Cruse assistant session.
    - Sets up a new session and updates the global `cruse_session` and `cruse_agent_state`.
    - Prints diagnostic messages to the console.

    Notes:
    -----
    - If no valid agent is found and no available systems are returned, the function exits early.
    - Relies on global variables: `cruse_session`, `cruse_agent_state`.

    """
    del args
    # pylint: disable=global-statement
    global cruse_session, cruse_agent_state

    if isinstance(data, dict):
        selected_agent = data.get("system")
    elif isinstance(data, str):
        selected_agent = data
    else:
        selected_agent = None

    # Fallback to default system if none was provided
    if not selected_agent:
        available_systems = get_available_systems()
        selected_agent = available_systems[0] if available_systems else None

    if not selected_agent:
        print("No available systems to initialize!")
        return

    print(f"Resetting session for new chat... Selected agent is: {selected_agent}")

    tear_down_cruse_assistant(cruse_session)
    cruse_session, cruse_agent_state = set_up_cruse_assistant(selected_agent)

    print("****New chat started****")


# Register the cleanup function
atexit.register(cleanup)

if __name__ == "__main__":
    socketio.run(app, debug=False, port=5001, allow_unsafe_werkzeug=True, log_output=True, use_reloader=False)
