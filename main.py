import json
import threading
import speech_recognition as sr

import server
from server import get_cwd


def check_config():
    default_config = {
        "gemini": {
            "key": "",
            "model": "gemini-2.5-flash",
        },
        "default_mic": None,
    }

    config = {
        "gemini": {
            "key": "",
            "model": "gemini-2.5-flash",
        },
        "default_mic": None,
    }

    try:
        with open("config.json", "r") as f:
            config = json.load(f)

    except:
        config["gemini"]["key"] = input(
            "Api key: AIzaSyBUhW-5mUza3otdFvFZRXynbqLPOiKWO8o\nPlease enter your gemini api key: "
        )

    if config.get("default_mic") == None:
        while True:
            for i, name in enumerate(sr.Microphone.list_microphone_names()):
                print(f"{i}: {name}")

            user_mic_input = int(input("Please select the default microphone to use: "))

            if user_mic_input >= 0 and user_mic_input < len(
                sr.Microphone.list_microphone_names()
            ):
                config["default_mic"] = user_mic_input
                break

    with open("config.json", "w") as f:
        f.write(json.dumps(config, indent=4))


def main():
    # Start the server
    thread = threading.Thread(target=server.main, daemon=True)
    print("Starting the server...")
    thread.start()

    check_config()

    if input('Do you have an external device that you want to use to trigger the activation? (y/n): ').lower().strip() == 'y':
        import arduino_trigger
        arduino_trigger.start_trigger()
    else:
        import executer
        while True:
            executer.main()

            input('Press ENTER to start listening')


if __name__ == "__main__":
    main()  

# import arduino_trigger

# import json
# import threading
# import speech_recognition as sr

# import server
# from server import get_cwd

# def check_config():
#     default_config = {
#         "gemini": {
#             "key": "",
#             "model": "gemini-2.5-flash",
#         },
#         "default_mic": None,
#     }

#     config = {
#         "gemini": {
#             "key": "",
#             "model": "gemini-2.5-flash",
#         },
#         "default_mic": None,
#     }

#     try:
#         with open('config.json', 'r') as f:
#             config = json.load(f)

#     except:
#         config["gemini"]["key"] = input(
#             "Api key: AIzaSyDhiNrQfuzeISTrUFn8QoFoQMe_ffzSkfc\nPlease enter your gemini api key: "
#         )

#     if config.get("default_mic") == None:
#         while True:
#             for i, name in enumerate(sr.Microphone.list_microphone_names()):
#                 print(f"{i}: {name}")

#             user_mic_input = int(input('Please select the default microphone to use: '))

#             if user_mic_input >= 0 and user_mic_input < len(sr.Microphone.list_microphone_names()):
#                 config['default_mic'] = user_mic_input
#                 break

#     with open('config.json', 'w') as f:
#         f.write(json.dumps(config, indent=4))

# def main():
#     # Start the server
#     # thread = threading.Thread(target=server.main, daemon=True, )
#     # print('Starting the server...')
#     # thread.start()

#     check_config()
#     arduino_trigger.main()

# if __name__ == '__main__':
#     main()
# #
