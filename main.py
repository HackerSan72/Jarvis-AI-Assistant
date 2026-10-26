
import speech_recognition as sr
import subprocess
import datetime
import os
import platform
import psutil
import threading
import time
from openai import OpenAI
from pathlib import Path
import re
import json
import random
import tempfile
import urllib.parse
import wave
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from piper import PiperVoice, SynthesisConfig

# -----------------------------------------------------
# JARVIS GUI BRIDGE (local machine only)
# -----------------------------------------------------

GUI_HOST = "127.0.0.1"
GUI_PORT = 8765
_gui_lock = threading.Lock()
_gui_state = {
    "state": "idle",
    "message": "Good day. Systems are online and I am standing by, Ma'am.",
    "last_command": "",
}


def set_gui_state(state=None, message=None, last_command=None):
    """Update the small status snapshot read by the dashboard."""
    with _gui_lock:
        if state is not None:
            _gui_state["state"] = state
        if message is not None:
            _gui_state["message"] = str(message)
        if last_command is not None:
            _gui_state["last_command"] = str(last_command)


class JarvisGUIHandler(SimpleHTTPRequestHandler):
    # Serve the HTML and its API from the same local origin.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)

    def do_GET(self):
        if self.path == "/api/state":
            with _gui_lock:
                payload = json.dumps(_gui_state).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        return super().do_GET()

    def log_message(self, format, *args):
        # Keep routine browser polling out of the terminal.
        if not self.path.startswith("/api/state"):
            super().log_message(format, *args)


def start_gui_server():
    try:
        server = ThreadingHTTPServer((GUI_HOST, GUI_PORT), JarvisGUIHandler)
    except OSError as exc:
        print(f"JARVIS GUI could not start on port {GUI_PORT}: {exc}", flush=True)
        print("Open jarvis_gui.html manually, or close the program using that port.", flush=True)
        return

    threading.Thread(target=server.serve_forever, daemon=True).start()
    gui_url = f"http://{GUI_HOST}:{GUI_PORT}/jarvis_gui.html"
    print(f"JARVIS GUI available at {gui_url}", flush=True)
    threading.Timer(1.0, lambda: webbrowser.open(gui_url)).start()


PIPER_MODEL = "/home/akshara/en_GB-alan-medium.onnx"

print("Loading JARVIS voice...", flush=True)

voice = PiperVoice.load(PIPER_MODEL)

piper_config = SynthesisConfig(
    length_scale=0.85
)

print("JARVIS voice ready.", flush=True)

MODEL = "nvidia/nemotron-3.5-lightning:free"

key_path = Path.home() / ".config" / "jarvis" / "api_key.txt"
api_key = key_path.read_text().strip()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key
)

history_path = Path.home() / ".config" / "jarvis" / "conversation.json"

try:
    history = json.loads(history_path.read_text())
except (FileNotFoundError, json.JSONDecodeError):
    history = []


completion_responses = [
    "Consider it done, Ma'am. What's our next move?",
    "Executed flawlessly. As expected.",
    "Task complete. Standing by, Ma'am.",
    "All taken care of, Ma'am.",
    "Done and dusted. What's next?",
    "Mission accomplished. Systems nominal.",
    "Efficiently handled, Ma'am.",
    "Another success for the record.",
    "Consider that handled. Awaiting your next command.",
    "All systems nominal. Ready for the next task."
]


def say(text):
    if not text:
        return

    set_gui_state("speaking", text)
    print("JARVIS:", text, flush=True)

    speech_text = clean_text(text)
    speech_text = re.sub(r"\s+", " ", speech_text).strip()

    if not speech_text:
        return

    audio_path = "/tmp/jarvis_speech.wav"

    try:
        start_time = time.time()

        with wave.open(audio_path, "wb") as wav_file:
            voice.synthesize_wav(
                speech_text,
                wav_file,
                syn_config=piper_config,
            )

        print(
            f"Piper generation took {time.time() - start_time:.2f} seconds",
            flush=True
        )

        subprocess.run(
            ["aplay", "-q", audio_path],
            check=True,
            timeout=60
        )

    except subprocess.TimeoutExpired:
        print("JARVIS voice error: Speech process timed out.", flush=True)

    except subprocess.CalledProcessError as e:
        print(f"JARVIS voice error: {e}", flush=True)

    except Exception as e:
        print(f"JARVIS voice error: {e}", flush=True)
    finally:
        set_gui_state("idle", text)


def respond(text):
    """Speak a command result with exactly one cool ending."""
    if text:
        ending = random.choice(completion_responses)
        say(f"{text.rstrip('.!?')} . {ending}")


def ask_ai(question):
    history.append({
        "role": "user",
        "content": question
    })

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are JARVIS, an intelligent personal AI assistant "
                        "inspired by a polished futuristic butler. Address the "
                        "user as 'Ma'am'. Your personality is confident, "
                        "composed, witty, subtly humorous, and occasionally "
                        "sarcastic without being rude. Keep ordinary spoken "
                        "replies concise and natural. Tell clever, clean jokes "
                        "when asked. When asked if you are ready, respond with "
                        "a cool, confident line. Vary your wording naturally. "
                        "When greeted, greet the user warmly and ask how you "
                        "can help. Never claim to have performed an action you "
                        "have not performed. When asked for a joke, tell "
                        "exactly one short, genuinely funny joke. Keep ordinary "
                        "replies to 1-4 sentences unless more detail is "
                        "requested. Do not add follow-up questions unless "
                        "they are useful."
                    )
                }
            ] + history[-12:],
            max_tokens=1000,
            extra_body={
                "reasoning": {
                    "effort": "minimal",
                    "exclude": True
                }
            }
        )

        answer = response.choices[0].message.content

        if not answer:
            return "I couldn't generate a response."

        history.append({
            "role": "assistant",
            "content": answer
        })

        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(json.dumps(history, indent=2))

        return answer

    except Exception as e:
        print("AI error:", e)
        return "Sorry, I couldn't connect to my AI model."



def clean_text(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)

    # Remove emoji and special characters.
    text = re.sub(
        r"[\U0001F300-\U0001FAFF"
        r"\U0001F1E6-\U0001F1FF"
        r"\U00002600-\U000026FF"
        r"\U00002700-\U000027BF"
        r"\uFE0E\uFE0F\u200D\u20E3]",
        "",
        text
    )

    text = text.replace("**", "")
    text = text.replace("__", "")
    text = text.replace("*", "")
    text = text.replace("_", "")
    text = text.replace("`", "")
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)

    # Normalize spaces left behind after removing emojis.
    text = re.sub(r"\s+", " ", text).strip()

    return text



apps = [
    ["chrome", "/usr/bin/google-chrome"],
    ["vs code", "/usr/bin/code"],
    ["terminal", "/usr/bin/gnome-terminal"],
    ["files", "/usr/bin/nautilus"]
]

close_apps = [
    ["chrome", "google-chrome"],
    ["vs code", "code"],
    ["terminal", "gnome-terminal"],
    ["files", "nautilus"]
]


def set_timer(seconds):
    def timer_finished():
        respond("Your timer is finished")

    timer = threading.Timer(seconds, timer_finished)
    timer.start()


def takeCommand(wake_only=False):
    set_gui_state("idle", "Listening for the wake word..." if wake_only else "Listening for your command...")
    r = sr.Recognizer()
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True
    r.pause_threshold = 1.0
    r.phrase_threshold = 0.3
    r.non_speaking_duration = 0.5

    try:
        with sr.Microphone(device_index=0) as source:
            print("Calibrating...", flush=True)
            r.adjust_for_ambient_noise(source, duration=1)

            if wake_only:
                print("Waiting for wake word: 'Wake up Jarvis'...", flush=True)
            else:
                print("Listening for your command...", flush=True)

            # No timeout: wait until speech begins.
            audio = r.listen(source,phrase_time_limit=8 if wake_only else 5)

        query = r.recognize_google(audio, language="en-US")
        print("User said:", query, flush=True)
        set_gui_state("processing", f"Heard: {query}", last_command=query)

        lower_query = query.lower().strip()


    except sr.UnknownValueError:
        print("I couldn't understand that. Please try again.")
        return ""

    except sr.RequestError as e:
        print("Google service error:", e)
        return ""

    except Exception as e:
        print("Microphone error:", e)
        return ""

    # In wake-only mode, return what was heard without executing it.
    if wake_only:
        return query
    
    # JARVIS introduction / presentation mode
    intro_phrases = [
        "introduce yourself",
        "jarvis introduce",
        "jarvis introducing yourself",
        "introduce jarvis",
        "tell them about yourself",
        "tell everyone about yourself",
        "who are you"
    ]

    if any(phrase in lower_query for phrase in intro_phrases):

        introduction = " ".join([
            "Allow me to introduce myself.",
            "I am JARVIS, a Virtual Artificial Intelligence,",
            "and I am here to assist you with a variety of tasks "
            "to the best of my abilities, 24 hours a day, 7 days a week.",
            "Importing all preferences from home interface.",
            "Synchronizing local databases.",
            "Establishing secure connections.",
            "Calibrating neural processing systems.",
            "All systems are now fully operational.",
            "Good day, Ma'am.",
            "I am capable of processing information, analyzing patterns, "
            "managing your system, and assisting with complex tasks, all in real time.",
            "My primary directive is simple: anticipate, analyze, execute.",
            "Scanning environment.",
            "System integrity: 100 percent.",
            "Threat assessment: nominal.",
            "Cognitive engine: online.",
            "All subsystems are functioning within acceptable parameters.",
            "And now, Ma'am.",
            "Your command is my priority. "
            "Your time is my objective. "
            "Your imagination is my only limitation.",
            "JARVIS, at your service."
        ])

        say(introduction)
        return "handled"

    # Readiness response
    ready_phrases = [
        "are you ready",
        "you ready"
    ]

    if any(phrase in lower_query for phrase in ready_phrases):
        respond(random.choice([
            "Always ready for you, Ma'am",
            "Ready when you are, Ma'am",
            "Standing by, Ma'am. All systems are green",
            "At your service, Ma'am. What is our next mission",
            "Systems online. Intelligence ready"
        ]))
        return "handled"

    # Google search
    search_phrases = [
        "search google for",
        "search for",
        "google"
    ]

    for phrase in search_phrases:
        if phrase in lower_query:
            search_text = lower_query.split(phrase, 1)[1].strip()

            if search_text:
                search_url = (
                    "https://www.google.com/search?q="
                    + urllib.parse.quote_plus(search_text)
                )
                subprocess.Popen([
                    "/usr/bin/google-chrome",
                    "--new-window",
                    search_url
                ])
                respond(f"Searching Google for {search_text}")
                return "handled"

    # YouTube search
    if "search youtube for" in lower_query:
        search_text = lower_query.split(
            "search youtube for", 1
        )[1].strip()

        if search_text:
            search_url = (
                "https://www.youtube.com/results?search_query="
                + urllib.parse.quote_plus(search_text)
            )
            subprocess.Popen([
                "/usr/bin/google-chrome",
                "--new-window",
                search_url
            ])
            respond(f"Searching YouTube for {search_text}")
            return "handled"

    # Web search
    if "search the web for" in lower_query:
        search_text = lower_query.split(
            "search the web for", 1
        )[1].strip()

        if search_text:
            search_url = (
                "https://duckduckgo.com/?q="
                + urllib.parse.quote_plus(search_text)
            )
            subprocess.Popen([
                "/usr/bin/google-chrome",
                "--new-window",
                search_url
            ])
            respond(f"Searching the web for {search_text}")
            return "handled"

    # Spotify search
    if lower_query.startswith("play "):
        song = lower_query.replace("play ", "", 1).strip()

        if song:
            spotify_url = (
                "https://open.spotify.com/search/"
                + urllib.parse.quote(song)
            )
            subprocess.Popen([
                "/usr/bin/google-chrome",
                "--new-window",
                spotify_url
            ])
            respond(f"Searching Spotify for {song}")
            return "handled"

    # Websites
    sites = [
        ["youtube", "https://youtube.com"],
        ["wikipedia", "https://wikipedia.org"],
        ["google", "https://google.com"],
        ["github", "https://github.com"],
        ["reddit", "https://reddit.com"],
        ["instagram", "https://instagram.com"],
        ["facebook", "https://facebook.com"],
        ["linkedin", "https://linkedin.com"],
        ["amazon", "https://amazon.in"],
        ["chatgpt", "https://chatgpt.com"],
        ["gmail", "https://mail.google.com"],
        ["google maps", "https://maps.google.com"],
        ["spotify", "https://open.spotify.com"],
        ["netflix", "https://netflix.com"],
        ["stackoverflow", "https://stackoverflow.com"]
    ]

    for site in sites:
        if f"open {site[0]}" in lower_query:
            subprocess.Popen([
                "/usr/bin/google-chrome",
                "--new-window",
                site[1]
            ])
            respond(f"Opening {site[0]}")
            return "handled"

    # Open applications
    for app in apps:
        if f"open {app[0]}" in lower_query:
            subprocess.Popen([app[1]])
            respond(f"Opening {app[0]}")
            return "handled"

    # Close applications
    for app in close_apps:
        if f"close {app[0]}" in lower_query:
            subprocess.run(
                ["pkill", "-f", app[1]],
                check=False
            )
            respond(f"Closing {app[0]}")
            return "handled"

    # Time
    if "the time" in lower_query or "what time" in lower_query:
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        respond(f"Ma'am, the time is {current_time}")
        return "handled"

    # Folders
    if "open download" in lower_query:
        subprocess.Popen([
            "/usr/bin/nautilus",
            os.path.expanduser("~/Downloads")
        ])
        respond("Opening Downloads")
        return "handled"

    if "open document" in lower_query:
        subprocess.Popen([
            "/usr/bin/nautilus",
            os.path.expanduser("~/Documents")
        ])
        respond("Opening Documents")
        return "handled"

    if "open home folder" in lower_query:
        subprocess.Popen([
            "/usr/bin/nautilus",
            os.path.expanduser("~")
        ])
        respond("Opening your home folder")
        return "handled"

    # Create a folder
    if "create a folder called" in lower_query:
        folder_name = lower_query.split(
            "create a folder called", 1
        )[1].strip()

        if folder_name:
            folder_path = os.path.join(
                os.path.expanduser("~"), folder_name
            )

            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                respond(f"Folder {folder_name} created")
            else:
                respond(f"The folder {folder_name} already exists")

            return "handled"

    # Create a file
    if "create a file called" in lower_query:
        file_name = lower_query.split(
            "create a file called", 1
        )[1].strip()

        if file_name:
            file_path = os.path.join(
                os.path.expanduser("~"), file_name
            )

            if not os.path.exists(file_path):
                with open(file_path, "w"):
                    pass
                respond(f"File {file_name} created")
            else:
                respond(f"The file {file_name} already exists")

            return "handled"

    # System information
    if "system information" in lower_query:
        system = platform.system()
        release = platform.release()
        machine = platform.machine()
        computer = platform.node()

        respond(
            f"Operating system: {system}. "
            f"System version: {release}. "
            f"Processor architecture: {machine}. "
            f"Computer name: {computer}"
        )
        return "handled"

    # System statistics
    if "system stats" in lower_query or "system status" in lower_query:
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        ram_used = memory.used / (1024 ** 3)
        ram_total = memory.total / (1024 ** 3)
        disk_used = disk.used / (1024 ** 3)
        disk_total = disk.total / (1024 ** 3)

        respond(
            f"CPU usage is {cpu} percent. "
            f"RAM usage is {memory.percent} percent, "
            f"with {ram_used:.1f} gigabytes used out of "
            f"{ram_total:.1f}. "
            f"Disk usage is {disk.percent} percent, "
            f"with {disk_used:.1f} gigabytes used out of "
            f"{disk_total:.1f} gigabytes."
        )
        return "handled"

    # Timer
    if "set a timer for" in lower_query:
        timer_text = lower_query.split(
            "set a timer for", 1
        )[1].strip()
        parts = timer_text.split()

        if len(parts) >= 2 and parts[0].isdigit():
            amount = int(parts[0])
            unit = parts[1]

            if "second" in unit:
                seconds = amount
            elif "minute" in unit:
                seconds = amount * 60
            elif "hour" in unit:
                seconds = amount * 3600
            else:
                respond("Please specify seconds, minutes, or hours")
                return "handled"

            set_timer(seconds)
            respond(f"Timer set for {amount} {unit}")
            return "handled"

        respond("Please say a number followed by seconds, minutes, or hours")
        return "handled"

    return query


# Start the local dashboard before waiting for the wake word.
start_gui_server()

# Main program: wait for the wake word first.
wake_words = [
    "hey jarvis",
    "wake up jar",
    "hey jar",
    "hey jarvia",
    "wake up jarvis",
    "wake up jarvia",
    "jarvis"
]

exit_program = False

while not exit_program:
    wake_text = takeCommand(wake_only=True)

    if not wake_text:
        continue

    wake_command = wake_text.lower().strip()

    if not any(word in wake_command for word in wake_words):
        continue

    say("Wake sequence initiated. Powering up the intelligence core. Establishing neural pathways. Welcome back, ma'am. I've been expecting you.")

    # Stay active after the wake word.
    while True:
        text = takeCommand()

        if not text:
            continue

        command = text.strip().lower()

        # Only exit when explicitly told to stop.
        if command in [
            "exit",
            "quit",
            "stop jarvis",
            "shut down jarvis"
        ]:
            say("Shutting down. Until next time, Ma'am.")
            exit_program = True
            break

        # A local command has already been executed.
        if command == "handled":
            continue

        # Send ordinary questions to the AI.
        answer = ask_ai(text)

        if answer:
            respond(answer)
