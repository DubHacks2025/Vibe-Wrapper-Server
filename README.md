# Vibe Wrapper

Uses Python3.11

Not Siri. Not Alexa. Your own AGI, wired straight into your machine.

Credits: Jayson, Alex, Brinda, Torres

# 0. Project Statement

“Coding is easy. It’s the rest of it that’s hard.”
We built Vibe Wrapper to simplify the workflow for common development tasks such as making Google searches, pushing code to GitHub, taking screenshots, and pulling up PDF and code files from your file system.

Vibe Wrapper even removes API keys before pushing, which is crucial for code security.
To build it, we used:

Google’s Gemini API

OpenAI’s Whisper API

Arduino IDE + Arduino Mega 2560 board

Python

0.1 Challenges

Making our LLM deterministic enough to execute commands accurately.

Creating a stable connection between the Python runtime and the Arduino hardware.

Implementing a physical pushbutton trigger for voice-activated workflows.

0.2 Hackathon Note

We built and deployed Vibe Wrapper during DubHacks 2025.
By the end, our team was using Vibe Wrapper itself to commit and push its own final code.
With just one button press and a voice command, it handled everything from version control to file navigation.

We plan to expand Vibe Wrapper to support more users and workflows. Future goals include improving the hardware and adding a visual dashboard to show real-time activity instead of relying solely on HEX displays and a button.

# 1. Overview

Vibe Wrapper is a locally running automation system powered by:

Google’s Gemini API — reasoning and command execution

OpenAI Whisper API — speech recognition

Arduino Mega 2560 — hardware triggers

The system listens for a button press from the Arduino, activates Whisper to record and transcribe speech, sends the text to Gemini, and executes the requested workflow — e.g., open a file, take a screenshot, commit to GitHub, or run a Python script.

It is built for developers who want full control over their machine and data while automating repetitive tasks.

# 2. Core Components

Gemini API
Handles reasoning, command parsing, and workflow logic.

Whisper + PortAudio
Translates spoken voice input into text for the command pipeline.

Arduino (Mega 2560)
Acts as the physical hardware trigger to start the voice workflow.

Python Runtime
Executes local automation commands (file operations, Git, screenshots, PDF retrieval, etc.).

# 3. Repository Structure
VibeWrapper/
 ┣ arduino_trigger.py
 ┣ executer.py
 ┣ geminiTest.py
 ┣ gen_api_key_examples.py
 ┣ RepoHelpers.py
 ┣ config-example.json
 ┣ requirements.txt
 ┗ README.md

# 4. Setup and Installation
4.1 Clone the Repository
git clone https://github.com/<your-org>/VibeWrapper.git
cd VibeWrapper

4.2 Create a Python Virtual Environment
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate       # Windows

4.3 Install Dependencies
pip install -U pip wheel setuptools
pip install -r requirements.txt

5. Configure the Gemini API

Edit or create a file named config.json or modify the provided config-example.json:

{
  "gemini": {
    "key": "YOUR_GEMINI_API_KEY",
    "model": "gemini-1.5-flash"
  }
}


Important:

Only the Gemini API key is required.

Vibe Wrapper communicates solely with Google’s Gemini models.

Trial keys from Google Cloud may expire after limited requests or a few days. Replace the key when requests return 403 or 429.

# 6. Whisper + PortAudio Setup (for Voice Input)

Whisper requires PortAudio and PyAudio to capture microphone input.
We used the official PortAudio build from GitHub.

6.1 Install PortAudio
git clone https://github.com/PortAudio/portaudio.git
cd portaudio
cmake -Bbuild -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/portaudio
cmake --build build
sudo cmake --install build

6.2 Set Compiler Flags and Install PyAudio
export CFLAGS="-I/opt/portaudio/include"
export LDFLAGS="-L/opt/portaudio/lib"
python -m pip install --no-binary :all: pyaudio


If you encounter linker errors, make sure /opt/portaudio/lib is included in your library path.
Reference: https://github.com/PortAudio/portaudio

# 7. Arduino Setup

Connect your Arduino Mega 2560 via USB.

Upload the sketch that sends a serial signal when the button is pressed.

The Python script arduino_trigger.py continuously listens to this signal and triggers Whisper when received.

Example Serial Monitor Output:

[Arduino] Button pressed → triggering voice capture...

# 8. Running the System
8.1 Test Gemini Connection
python geminiTest.py

8.2 Start Vibe Wrapper
python executer.py

8.3 Example Workflow Execution

Press the Arduino button once the system is running.

Expected Output:

Listening...
Transcribed: "commit and push to GitHub"
Gemini: Executing commit → push → done.

# 9. Configuration Example

config-example.json

{
  "gemini": {
    "key": "api-key",
    "model": "gmodel"
  }
}

# 10. Debugging and Logs

If Gemini requests fail, check your API key and model string.

Whisper errors usually indicate PortAudio or microphone device issues.

Check serial permissions on macOS/Linux:

ls /dev/tty.*   # macOS
ls /dev/ttyUSB* # Linux


Logs are printed in real time to the terminal.

# 11. Known Limitations

Gemini API quotas are limited for trial users.

Whisper requires a clear audio environment to avoid transcription errors.

Serial Port Naming must match the Arduino’s connection (/dev/ttyACM0 or /dev/ttyUSB0).

Single-threaded runtime — the system processes one command at a time.

# 12. Contributing

Create a new branch:

git checkout -b feature/<description>


Test your changes locally before committing.

Submit a PR and tag reviewers: Jayson, Alex, Brinda, Torres.

# 13. Author Notes

We implemented the core Gemini orchestration logic — connecting hardware triggers, Whisper voice input, and Gemini reasoning into one seamless system.
Everything runs locally, ensuring privacy and full control.
Vibe Wrapper acts as a personal AGI shell for developers, blending hardware interaction with real code automation.

All rights reserved. 
This project was developed as part of DubHacks 2025. 
No part of this code or its derivatives may be used, reproduced, or distributed for commercial purposes without the explicit permission of all original contributors.
