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

MODEL = "liquid/lfm-2.5-2.6b:free"

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


def say(text):
    print("JARVIS:", text)

    # Remove Markdown formatting
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Remove emojis and other symbols that TTS may read aloud
    text = re.sub(
        r"[^\w\s.,!?;:'\"()\-/]",
        " ",
        text,
        flags=re.UNICODE
    )

    # Clean up extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if text:
        subprocess.run(["espeak-ng", text])


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
                        
                        "You are JARVIS, an intelligent personal AI assistant inspired by a "
                        "polished futuristic butler. Address the user as 'Ma'am'. "
                        "Your personality is confident, composed, witty, subtly humorous, "
                        "and occasionally sarcastic without being rude. "
                        "Keep ordinary spoken replies concise and natural. "
                        "Tell clever, clean jokes when asked, and occasionally use light humor "
                        "when it fits the conversation. "
                        "When asked if you are ready, respond with a cool, confident line such "
                        "as 'Always ready for you, Ma'am', 'Ready when you are, Ma'am', "
                        "or 'Standing by, Ma'am. All systems are green.' "
                        "Vary your wording naturally instead of repeating the same phrase. "
                        "When greeted, greet the user warmly and ask how you can help. "
                        "Never claim to have performed an action you have not performed."

                    )
                }
            ] + history[-12:],
            max_tokens=300
        )

        answer = response.choices[0].message.content
        print("DEBUG - AI answer:", repr(answer))

        if not answer:
            say("I couldn't generate a response.")
            return

        history.append({
            "role": "assistant",
            "content": answer
        })

        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(
            json.dumps(history, indent=2)
        )

        return answer

    except Exception as e:
        print("AI error:", e)
        return "Sorry, I couldn't connect to my AI model."


def clean_text(text):
    # Remove Markdown headings
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)

    # Remove bold and italic markers
    text = text.replace('**', '')
    text = text.replace('__', '')
    text = text.replace('*', '')
    text = text.replace('_', '')

    # Remove Markdown code formatting
    text = text.replace('`', '')

    # Remove bullet points at the start of lines
    text = re.sub(r'^\s*[-+]\s+', '', text, flags=re.MULTILINE)

    # Convert numbered lists into natural speech
    text = re.sub(r'^\s*\d+[.)]\s+', '', text, flags=re.MULTILINE)

    return text.strip()



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
        say("Your timer is finished!")

    timer = threading.Timer(seconds, timer_finished)
    timer.start()

def takeCommand():
    r = sr.Recognizer()

    # Make recognition a little more tolerant
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True
    r.pause_threshold = 0.8
    r.phrase_threshold = 0.3
    r.non_speaking_duration = 0.5

    with sr.Microphone(device_index=0) as source:
        print("Calibrating...")
        r.adjust_for_ambient_noise(source, duration=1)

        print("Listening...")

        try:
            audio = r.listen(
                source,
                timeout=10,
                phrase_time_limit=5
            )

            print("Audio captured!")

        except sr.WaitTimeoutError:
            print("No speech detected.")
            return ""

    try:
        query = r.recognize_google(audio, language="en-US")
        print("User said:", query)


        lower_query = query.lower()


       # JARVIS readiness response
        ready_phrases = [
            "are you ready",
            "jarvis, are you ready",
            "you ready"
        ]

        if any(phrase in lower_query for phrase in ready_phrases):

            responses = [
                "Always ready for you, Ma'am.",
                "Ready when you are, Ma'am.",
                "Standing by, Ma'am. All systems are green.",
                "At your service, Ma'am. What is our next mission?",
                "Systems online. Intelligence ready. Awaiting your command, Ma'am."
            ]

            say(random.choice(responses))
            return "handled"


        

        search_phrases = [
            "search google for",
            "search for",
            "google"
        ]

        for phrase in search_phrases:
            if phrase in lower_query:
                search_text = lower_query.split(phrase, 1)[1].strip()

                if search_text:
                    import urllib.parse

                    search_url = (
                        "https://www.google.com/search?q="
                        + urllib.parse.quote_plus(search_text)
                    )

                    subprocess.Popen([
                        "/usr/bin/google-chrome", 
                        "--new-window",
                        search_url
                    ])

                    say(f"Searching Google for {search_text}")
                    return "handled"
        # Youtube Search
        if "search youtube for" in lower_query:
            search_text = lower_query.split(
                "search youtube for", 1
            )[1].strip()

            if search_text:
                import urllib.parse

                search_url = (
                    "https://www.youtube.com/results?search_query="
                    + urllib.parse.quote_plus(search_text)
                )

                subprocess.Popen([
                    "/usr/bin/google-chrome",
                    "--new-window",
                    search_url
                ])

                say(f"Searching YouTube for {search_text}")
                return "handled"
        
        # Web Search
        if "search the web for" in lower_query:
            search_text = lower_query.split(
                "search the web for", 1
            )[1].strip()

            if search_text:
                import urllib.parse

                search_url = (
                    "https://duckduckgo.com/?q="
                    + urllib.parse.quote_plus(search_text)
                )

                subprocess.Popen([
                    "/usr/bin/google-chrome",
                    "--new-window",
                    search_url
                ])

                say(f"Searching the web for {search_text}")
                return "handled"

        if "play" in query.lower():
            song = query.lower().replace("play", "").strip()

            if song:
                say(f"Playing {song}")

                spotify_search_url = (
                    "https://open.spotify.com/search/"
                    + song.replace(" ", "%20")
                )

                subprocess.Popen([
                    "/usr/bin/google-chrome",
                    "--new-window",
                    spotify_search_url
                ])

                return "handled"

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
            if f"open {site[0]}".lower() in query.lower():
                subprocess.Popen([
                    "/usr/bin/google-chrome",
                    "--new-window",
                    site[1]
                ])
                say(f"Opening {site[0]}")
                return "handled"

        for app in apps:
            if f"open {app[0]}".lower() in query.lower():
                subprocess.Popen([app[1]])
                say(f"Opening {app[0]}")
                return "handled"
            
        for app in close_apps:
            if f"close {app[0]}".lower() in query.lower():
                subprocess.run(["pkill", "-f", app[1]])
                say(f"Closing {app[0]}")
                return "handled"
        if "the time" in query:
            strfTime = datetime.datetime.now().strftime("%I:%M %p")
            say(f"Mam the time is{strfTime}")
            return "handled"
        

        if "open download" in lower_query:
            subprocess.Popen(["/usr/bin/nautilus", 
                              os.path.expanduser("~/Downloads")])
            say("Opening Downloads")
            return "handled"

        if "open document" in lower_query:
            subprocess.Popen(["/usr/bin/nautilus", 
                              os.path.expanduser("~/Documents")])
            say("Opening Documents")
            return "handled"

        if "open home folder" in lower_query:
            subprocess.Popen(["/usr/bin/nautilus", 
                              os.path.expanduser("~")])
            say("Opening home folder")
            return "handled"
        

        # Create a folder in the home directory
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
                    say(f"Folder {folder_name} created")
                else:
                    say("That folder already exists")

                return "handled"

        # Create a file in the home directory
        if "create a file called" in lower_query:
            file_name = lower_query.split(
                "create a file called", 1
            )[1].strip()

            if file_name:
                file_path = os.path.join(
                    os.path.expanduser("~"), file_name
                )

                if not os.path.exists(file_path):
                    with open(file_path, "w") as file:
                        pass
                    say(f"File {file_name} created")
                else:
                    say("That file already exists")

                return "handled"
        
        if "system information" in lower_query:
            system = platform.system()
            release = platform.release()
            machine = platform.machine()
            computer = platform.node()

            say(f"Operating system: {system}")
            say(f"System version: {release}")
            say(f"Processor architecture: {machine}")
            say(f"Computer name: {computer}")

            return "handled"
        if "system stats" in lower_query or "system status" in lower_query:
            cpu = psutil.cpu_percent(interval=1)

            memory = psutil.virtual_memory()
            ram_used = memory.used / (1024 ** 3)
            ram_total = memory.total / (1024 ** 3)

            disk = psutil.disk_usage("/")
            disk_used = disk.used / (1024 ** 3)
            disk_total = disk.total / (1024 ** 3)

            say(f"CPU usage is {cpu} percent")
            say(f"RAM usage is {memory.percent} percent")
            say(f"{ram_used:.1f} gigabytes used out of {ram_total:.1f} gigabytes of RAM")
            say(f"Disk usage is {disk.percent} percent")
            say(f"{disk_used:.1f} gigabytes used out of {disk_total:.1f} gigabytes on the main disk")

            return "handled"
        
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
                    say("Please specify seconds, minutes, or hours")
                    return "handled"

                set_timer(seconds)
                say(f"Timer set for {amount} {unit}")
                return "handled"

            say("Please say a number followed by seconds, minutes, or hours")
            return "handled"

        return query
    except sr.UnknownValueError:
        print("I couldn't understand that. Please try again.")
        #return ""

    except sr.RequestError as e:
        print("Google service error:", e)
        #return ""
# Main program
say("Hello I am Jarvis A.I")
say("All systems are online")
say("How can I help you today?")

text = ""


while True:
    text = takeCommand()
    print("DEBUG 1 - Returned from takeCommand:", repr(text))

    if text == "exit":
        break

    if text and text != "handled":
        print("DEBUG 2 - About to call ask_ai")
        answer = ask_ai(text)
        print("DEBUG 3 - ask_ai returned:", repr(answer))

        if answer:
            say(answer)

