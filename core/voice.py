"""Voice module - STT/TTS (optional, skip if no mic available)"""

def speak(text: str, speed: int = 150):
    """Text-to-speech using pyttsx3 if available"""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', speed)
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass

def listen() -> str:
    """Speech-to-text using speech_recognition if available"""
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.Microphone() as source:
            audio = r.listen(source, timeout=5)
        return r.recognize_google(audio)
    except Exception:
        return ""
