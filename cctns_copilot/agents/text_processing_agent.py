from transformers import pipeline, T5ForConditionalGeneration, T5Tokenizer

class TextProcessingAgent:
    def __init__(self):
        """
        Initializes the Text Processing Agent.
        Loads models for translation and grammar correction.
        """
        # Model for Telugu to English translation
        # Example: "Helsinki-NLP/opus-mt-tc-en" (Telugu Comma to English) - this is a guess, need to find a proper one.
        # A more general approach might be a multilingual T5 or a specific Indic T5 model.
        # For now, using a general T5 and will specify task prefixes.
        # Let's use a standard T5 model that can be prompted for translation and grammar.
        self.t5_model_name = "t5-base" # "t5-small" or "t5-base" are good starting points
        try:
            self.t5_tokenizer = T5Tokenizer.from_pretrained(self.t5_model_name)
            self.t5_model = T5ForConditionalGeneration.from_pretrained(self.t5_model_name)
            print(f"T5 model ({self.t5_model_name}) loaded successfully for translation and grammar.")
        except Exception as e:
            print(f"Error loading T5 model ({self.t5_model_name}): {e}")
            # Fallback or specific grammar model could be added here if T5 fails
            self.t5_tokenizer = None
            self.t5_model = None
            raise RuntimeError(f"Failed to load T5 model: {e}")

        # Optional: Specific grammar correction model (if T5 is not sufficient or for better performance)
        # Example: pipeline("text2text-generation", model="pszemraj/flan-t5-large-grammar-synthesis")
        # For now, we rely on T5 with prompting.
        self.grammar_pipeline = None
        # try:
        #     self.grammar_pipeline = pipeline("text2text-generation", model="pszemraj/flan-t5-large-grammar-synthesis")
        #     print("Grammar correction model loaded successfully.")
        # except Exception as e:
        #     print(f"Warning: Could not load dedicated grammar model. T5 will be used. Error: {e}")


    def correct_grammar(self, text: str, language: str = 'en') -> str:
        """
        Corrects grammar of the given text.
        Uses T5 model with a specific prompt for grammar correction.
        Args:
            text (str): The text to correct.
            language (str): The language of the text (currently primarily supports 'en' for T5 based correction).
        Returns:
            str: The grammar-corrected text.
        """
        if not self.t5_model or not self.t5_tokenizer:
            print("Error: T5 model not loaded. Cannot correct grammar.")
            return text # Return original text if model isn't available

        if language != 'en':
            # Grammar correction for non-English languages with a general T5 model is less straightforward.
            # It might require language-specific models or advanced prompting.
            # For now, we'll skip grammar correction if the text isn't English,
            # assuming translation to English happens first if needed.
            print(f"Grammar correction currently optimized for English. Skipping for language: {language}")
            return text

        # Using T5 for grammar correction with a prefix
        # (inspired by how T5 is used for various tasks)
        prompt = f"grammar: {text}"
        inputs = self.t5_tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
        outputs = self.t5_model.generate(inputs.input_ids, max_length=512, num_beams=4, early_stopping=True)
        corrected_text = self.t5_tokenizer.decode(outputs[0], skip_special_tokens=True)

        print(f"Original for grammar: {text}")
        print(f"Corrected grammar: {corrected_text}")
        return corrected_text

    def translate_to_english(self, text: str, source_language: str) -> str:
        """
        Translates text from the source language to English using T5.
        Args:
            text (str): The text to translate.
            source_language (str): The source language code (e.g., 'te' for Telugu).
        Returns:
            str: The translated English text.
        """
        if not self.t5_model or not self.t5_tokenizer:
            print("Error: T5 model not loaded. Cannot translate.")
            return text # Return original text

        if source_language == 'en':
            return text # Already English

        # T5 requires specific prefixes for translation tasks.
        # Example: "translate Telugu to English: text_to_translate"
        # The exact prefix depends on the T5 model's training.
        # For generic t5-base, we hope this works.
        # Finding a robust list of language names T5 understands can be tricky.
        # "Telugu" is a guess.
        lang_map = {
            'te': 'Telugu'
            # Add other languages if needed
        }
        source_lang_name = lang_map.get(source_language, source_language) # Default to code if name not mapped

        prompt = f"translate {source_lang_name} to English: {text}"

        inputs = self.t5_tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
        outputs = self.t5_model.generate(inputs.input_ids, max_length=512, num_beams=4, early_stopping=True)
        translated_text = self.t5_tokenizer.decode(outputs[0], skip_special_tokens=True)

        print(f"Original for translation ({source_lang_name}): {text}")
        print(f"Translated to English: {translated_text}")
        return translated_text

    def process_text(self, text: str, original_language: str) -> str:
        """
        Processes the transcribed text:
        1. Translates to English if necessary.
        2. Corrects grammar of the (now) English text.
        Args:
            text (str): The transcribed text.
            original_language (str): The language of the transcribed text (e.g., 'en', 'te').
        Returns:
            str: The processed English text.
        """
        processed_text = text
        # Step 1: Translate to English if not already English
        if original_language != 'en':
            print(f"Original language is '{original_language}', translating to English.")
            processed_text = self.translate_to_english(text, original_language)
        else:
            print("Text is already in English. Skipping translation.")

        # Step 2: Correct grammar (of the English text)
        # Assuming grammar correction is desired for English text, whether original or translated.
        print("Performing grammar correction...")
        processed_text = self.correct_grammar(processed_text, language='en') # Correct grammar of English text

        return processed_text

if __name__ == '__main__':
    # Example Usage
    print("Initializing TextProcessingAgent...")
    try:
        agent = TextProcessingAgent()

        # Example 1: English text with a grammatical error
        english_text_error = "what is the crimes in guntur"
        print(f"\nProcessing English text: '{english_text_error}'")
        processed_english = agent.process_text(english_text_error, original_language='en')
        print(f"Final processed English: '{processed_english}'")

        # Example 2: Telugu text (mock translation, as T5 setup for Telugu needs specific model/prompting)
        # Replace with actual Telugu text if a suitable T5 model for Te->En is confirmed.
        # This example will likely not translate well with "t5-base" without specific fine-tuning
        # or a more appropriate multilingual model.
        telugu_text_example = "గుంటూరులో నేరాలు ఏమిటి" # "What are the crimes in Guntur"
        print(f"\nProcessing Telugu text: '{telugu_text_example}'")
        # We expect T5 to try translating this. If it can't, it might return gibberish or the original.
        # The grammar correction will then run on whatever T5 outputs.
        processed_telugu_to_english = agent.process_text(telugu_text_example, original_language='te')
        print(f"Final processed Telugu to English: '{processed_telugu_to_english}'")

        another_english_error = "show me total crime by type for district guntur"
        print(f"\nProcessing another English text: '{another_english_error}'")
        processed_english_2 = agent.process_text(another_english_error, original_language='en')
        print(f"Final processed English 2: '{processed_english_2}'")


    except RuntimeError as e:
        print(f"Could not run TextProcessingAgent example: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print("\nNote: T5 translation quality, especially for Telugu to English with a generic model like 't5-base',")
    print("can be limited. Fine-tuned models (e.g., from Helsinki-NLP or IndicNLP) are recommended for robust translation.")
    print("Grammar correction with generic T5 is also heuristic.")
