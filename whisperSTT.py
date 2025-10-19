import argparse
import os
import numpy as np
import speech_recognition as sr
import whisper
import torch
from datetime import datetime, timedelta
from queue import Queue
from time import sleep
import json

# Load / Download model
model = "tiny.en"
audio_model = whisper.load_model(model)

with open('config.json', 'r') as f:
    config = json.load(f)

DEVICE_INDEX_INPUT = config.get("default_mic")

def take_prompt():
    parser = argparse.ArgumentParser()
    # parser.add_argument("--model", default="medium", help="Model to use",
    #                    choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--non_english", action='store_true',
                        help="Don't use the english model.")
    parser.add_argument("--energy_threshold", default=500,
                        help="Energy level for mic to detect.", type=int)
    parser.add_argument("--record_timeout", default=2.3,
                        help="How real time the recording is in seconds.", type=float)
    parser.add_argument("--phrase_timeout", default=2.5,
                        help="How much empty space between recordings before we "
                             "consider it a new line in the transcription.", type=float)
    parser.add_argument("--silence_timeout", default=3.0,
                        help="End workflow if silent for this many seconds.", type=float)
    args = parser.parse_args()

    # 1) List all available microphones
    # for i, name in enumerate(sr.Microphone.list_microphone_names()):
    #     print(f"{i}: {name}")

    # DEVICE_INDEX_INPUT = int(input("Please select the audio device you wish to use: "))

    # The last time a recording was retrieved from the queue.
    phrase_time = None
    # Thread safe Queue for passing data from the threaded recording callback.
    data_queue = Queue()
    # Bytes object which holds audio data for the current phrase
    phrase_bytes = bytes()
    # We use SpeechRecognizer to record our audio because it has a nice feature where it can detect when speech ends.
    recorder = sr.Recognizer()
    recorder.energy_threshold = args.energy_threshold
    # Definitely do this, dynamic energy compensation lowers the energy threshold dramatically to a point where the SpeechRecognizer never stops recording.
    recorder.dynamic_energy_threshold = False
    # select the Microphone
    source = sr.Microphone(device_index=DEVICE_INDEX_INPUT, sample_rate=16000)

    record_timeout = args.record_timeout
    phrase_timeout = args.phrase_timeout

    silence_timeout = args.silence_timeout

    transcription = ['']

    with source:
        recorder.adjust_for_ambient_noise(source)

    def record_callback(_, audio: sr.AudioData) -> None:
        """
        Threaded callback function to receive audio data when recordings finish.
        audio: An AudioData containing the recorded bytes.
        """
        # Grab the raw bytes and push it into the thread safe queue.
        data = audio.get_raw_data()
        data_queue.put(data)

    # Create a background thread that will pass us raw audio bytes.
    # We could do this manually but SpeechRecognizer provides a nice helper.
    print('Recording started')
    recorder.listen_in_background(source, record_callback, phrase_time_limit=record_timeout)

    # Cue the user that we're ready to go.
    print("Model loaded.")

    # Customize the wake word
    wake_word = "buddy"
    awaiting_target = False   # True ⇢ we already heard wake-word and are waiting
    target_sentence = None    # holds the extracted sentence

    while True:
        try:
            now = datetime.utcnow()

            if (data_queue.empty() and phrase_time is not None and
            (now - phrase_time) > timedelta(seconds=silence_timeout)):
                break

            # Pull raw recorded audio from the queue.
            if not data_queue.empty():
                phrase_complete = False
                # If enough time has passed between recordings, consider the phrase complete.
                # Clear the current working audio buffer to start over with the new data.
                if phrase_time and now - phrase_time > timedelta(seconds=phrase_timeout):
                    phrase_bytes = bytes()
                    phrase_complete = True
                # This is the last time we received new audio data from the queue.
                phrase_time = now

                # Combine audio data from queue
                audio_data = b''.join(data_queue.queue)
                data_queue.queue.clear()

                # Add the new audio data to the accumulated data for this phrase
                phrase_bytes += audio_data

                # Convert in-ram buffer to something the model can use directly without needing a temp file.
                # Convert data from 16 bit wide integers to floating point with a width of 32 bits.
                # Clamp the audio stream frequency to a PCM wavelength compatible default of 32768hz max.
                audio_np = np.frombuffer(phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                # Read the transcription.

                # benchmark this part
                result = audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())

                text = result['text'].strip()

                # If we detected a pause between recordings, add a new item to our transcription.
                # Otherwise edit the existing one.
                if phrase_complete:
                    transcription.append(text)
                else:
                    transcription[-1] = text

                '''
                lower = text.lower()

                if awaiting_target:
                    target_sentence = text.strip()
                    awaiting_target = False
                elif wake_word in lower:
                    after = lower.split(wake_word,1)[1].strip().lstrip(", ")
                    if after:
                        target_sentence = after
                    else:
                        awaiting_target = True
                '''

                # Clear the console to reprint the updated transcription.
                os.system('cls' if os.name=='nt' else 'clear')
                for line in transcription:
                    print(line)
                # Flush stdout.
                print('', end='', flush=True)
            else:
                # Infinite loops are bad for processors, must sleep.
                sleep(0.25)
        except KeyboardInterrupt:
            pass
    # Final transcript (joined phrases, trimmed)
    final_text = " ".join(t.strip() for t in transcription if t.strip())
    print("\n\nTranscription:")
    print(final_text)

    return final_text


if __name__ == "__main__":
    take_prompt()
