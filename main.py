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

#for index, name in enumerate(sr.Microphone.list_microphone_names()):
 #   print(index, name)

def say(text):
    print("JARVIS:", text)
    subprocess.run(["espeak-ng", text])

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
        
        if "search youtube for" in lower_query:
            search_text = lower_query.split(
                "search youtube for", 1
            )[1].strip()
        

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

    if text == "exit":
        break
    if text and text != "handled":
        say(text)
