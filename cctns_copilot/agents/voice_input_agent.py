import speech_recognition as sr
from transformers import pipeline
import pyaudio # Required for microphone access, will add to requirements

class VoiceInputAgent:
    def __init__(self, language='en-IN'):
        """
        Initializes the Voice Input Agent.
        Args:
            language (str): The language for transcription (e.g., 'en-IN' for English, 'te-IN' for Telugu).
        """
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.language = language

        # Initialize primary model (IndicConformer) - Placeholder for actual model loading
        # Actual model loading might require specific paths or Hugging Face model identifiers
        # For English, a model like 'ai4bharat/indicconformer-stt-en' could be used.
        # For Telugu, a specific Telugu STT model from ai4bharat or a multilingual model would be needed.
        # Example: 'ai4bharat/indicconformer-stt-te' if available, or configure a multilingual model.
        self.indic_conformer_model_name = None
        if self.language.startswith('te'):
            # User should specify the correct Telugu model here if different
            self.indic_conformer_model_name = "ai4bharat/indicconformer-stt-multi" # Example, replace with actual Telugu/multilingual model
            print(f"Attempting to load multilingual/Telugu IndicConformer model: {self.indic_conformer_model_name}")
        else:
            self.indic_conformer_model_name = "ai4bharat/indicconformer-stt-en" # Default to English model
            print(f"Attempting to load English IndicConformer model: {self.indic_conformer_model_name}")

        try:
            self.indic_conformer_pipeline = pipeline("automatic-speech-recognition", model=self.indic_conformer_model_name)
            print(f"IndicConformer model ({self.indic_conformer_model_name}) loaded successfully.")
        except Exception as e:
            print(f"Warning: Could not load IndicConformer model ({self.indic_conformer_model_name}). Will rely on Whisper. Error: {e}")
            self.indic_conformer_pipeline = None

        # Initialize fallback model (Whisper Medium)
        try:
            self.whisper_pipeline = pipeline("automatic-speech-recognition", model="openai/whisper-medium")
            print("Whisper Medium model loaded successfully.")
        except Exception as e:
            print(f"Error: Could not load Whisper Medium model. Transcription will not be possible. Error: {e}")
            self.whisper_pipeline = None
            # If Whisper also fails, we should raise an error or handle this critical failure
            raise RuntimeError("Failed to load both primary and fallback speech recognition models.")


    def listen_and_transcribe(self, duration=5):
        """
        Listens for audio input from the microphone and transcribes it.
        Tries primary model first, then fallback if needed.
        Args:
            duration (int): How long to listen for audio in seconds.
        Returns:
            str: The transcribed text, or None if transcription failed.
        """
        if not self.whisper_pipeline and not self.indic_conformer_pipeline:
            print("Error: No speech recognition models loaded.")
            return None

        with self.microphone as source:
            print(f"Listening for {duration} seconds... Speak now!")
            self.recognizer.adjust_for_ambient_noise(source)
            try:
                audio_data = self.recognizer.listen(source, timeout=duration, phrase_time_limit=duration)
            except sr.WaitTimeoutError:
                print("No speech detected within the time limit.")
                return None

        print("Processing audio...")
        audio_bytes = audio_data.get_wav_data()

        transcribed_text = None

        # Try IndicConformer first
        if self.indic_conformer_pipeline:
            try:
                # IndicConformer might expect a specific format or sampling rate.
                # This is a simplified call; actual usage might need preprocessing.
                # The input to the pipeline should be raw audio data (bytes or numpy array).
                # Ensure the model is compatible with the language specified.
                # For multilingual models, you might need to specify the language.
                if self.language.startswith('te') and "indicconformer" in self.indic_conformer_pipeline.model.name_or_path.lower():
                     # This is a guess, actual model might have specific lang codes
                    result = self.indic_conformer_pipeline(audio_bytes, generate_kwargs={"language": "telugu"})
                else:
                    result = self.indic_conformer_pipeline(audio_bytes)

                transcribed_text = result["text"]
                print(f"IndicConformer transcription: {transcribed_text}")
                if transcribed_text:
                    return transcribed_text
            except Exception as e:
                print(f"IndicConformer transcription failed: {e}. Trying Whisper.")

        # Fallback to Whisper if IndicConformer failed or wasn't loaded
        if self.whisper_pipeline:
            try:
                # Whisper can often auto-detect language, but specifying can improve accuracy.
                # The language codes for Whisper might differ (e.g., 'en', 'te').
                whisper_lang_code = self.language.split('-')[0] # 'en' or 'te'
                result = self.whisper_pipeline(audio_bytes, generate_kwargs={"language": whisper_lang_code})
                transcribed_text = result["text"]
                print(f"Whisper transcription: {transcribed_text}")
                return transcribed_text
            except Exception as e:
                print(f"Whisper transcription failed: {e}")
                return None

        return None

if __name__ == '__main__':
    # Example Usage
    # This part will require user interaction and microphone access when run.
    # It's primarily for testing the agent directly.
    print("Initializing VoiceInputAgent...")
    try:
        # For English
        # voice_agent_en = VoiceInputAgent(language='en-IN')
        # print("\nTesting English Transcription:")
        # english_text = voice_agent_en.listen_and_transcribe(duration=5)
        # if english_text:
        #     print(f"Transcribed (English): {english_text}")
        # else:
        #     print("Could not transcribe English input.")

        # For Telugu (Uncomment if IndicConformer for Telugu is configured)
        # Make sure the IndicConformer model specified supports Telugu or use a specific Telugu model
        voice_agent_te = VoiceInputAgent(language='te-IN')
        print("\nTesting Telugu Transcription (ensure your IndicConformer model supports Telugu or Whisper is working):")
        telugu_text = voice_agent_te.listen_and_transcribe(duration=5)
        if telugu_text:
            print(f"Transcribed (Telugu): {telugu_text}")
        else:
            print("Could not transcribe Telugu input.")

    except RuntimeError as e:
        print(f"Could not run example: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during example usage: {e}")

    print("\nNote: If you see errors about model loading, ensure the models are downloaded or accessible.")
    print("For Hugging Face models, you might need to log in with `huggingface-cli login` or have them cached.")
    print("Microphone access is also required.")
