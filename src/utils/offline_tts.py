import pyttsx3

class TextToSpeechEngine:
    def __init__(self, speed: int = 190, volume: int = 1):
        self.__text_to_speech_engine = pyttsx3.init(driverName = 'sapi5', debug = False)

        self.__text_to_speech_engine.setProperty('voice', self.__text_to_speech_engine.getProperty('voices')[1].id)
        self.__text_to_speech_engine.setProperty('rate', speed)
        self.__text_to_speech_engine.setProperty('volume', volume)
    
    def speak(self, msg: str):
        self.__text_to_speech_engine.say(msg)
        self.__text_to_speech_engine.runAndWait()