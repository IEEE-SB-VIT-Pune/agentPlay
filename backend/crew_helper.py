import asyncio
from crewai import Crew, Agent, Task
from dotenv import load_dotenv
import os
from crewai import LLM

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
os.environ['GEMINI_API_KEY'] = GEMINI_API_KEY if GEMINI_API_KEY else ""

# Initialize LLM
try:
    llm = LLM(model="gemini/gemini-1.5-flash")
except Exception as e:
    llm = None

# --- Translator Agent ---
translator = Agent(
    role="Language Translator",
    goal="Accurately translate text from any language to English while preserving meaning and context.",
    backstory="A multilingual expert with deep linguistic knowledge, ensuring accurate and context-aware translations.",
    verbose=False,
    memory=True,
    allow_delegation=False,
    llm=llm
)

# --- Translation Task ---
translate_task = Task(
    description="Translate the given {text} from any language into English, maintaining the original meaning, tone, and context.",
    expected_output="The text accurately translated into English with no loss of meaning.",
    agent=translator
)

# --- Crew Setup ---
translation_crew = Crew(
    agents=[translator],
    tasks=[translate_task]
)

# --- Optimized Asynchronous Function to Translate Text ---
async def translate_to_english(text):
    """Splits text into 500-word chunks and translates them concurrently."""
    words = text.split()
    chunk_size = 500

    # Create chunks of 500 words
    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
    
    # Create async tasks for each chunk
    tasks = [asyncio.to_thread(translation_crew.kickoff, inputs={'text': chunk}) for chunk in chunks]
    
    # Run all translation tasks in parallel
    results = await asyncio.gather(*tasks)

    # Extract raw translations and join them
    translated_texts = [result.raw for result in results]
    return " ".join(translated_texts)

# --- Asynchronous Function to Count Words and Translate ---
async def count_words_and_translate(text):
    """Counts words and translates in chunk of 500"""
    word_count = len(text.split())
    print(f"Word count: {word_count}")

    if word_count > 500:
        return await translate_to_english(text)  # ✅ Faster due to concurrent execution
    return await translate_to_english(text)

# --- Translator Agent ---
translation_agent = Agent(
    role="Context-Aware Translator",
    goal="Translate the given segment from {source_language} to {target_language} while keeping its meaning the same, "
         "using the whole English transcript as a reference. The translated segment must have the same number of words.",
    backstory="A linguistics expert with deep experience in contextual translation, ensuring accuracy while maintaining structure.",
    verbose=False,
    memory=True,
    allow_delegation=False,
    llm=llm
)

# --- Translation Task ---
translation_task = Task(
    description="Translate the given segment '{segment}' from {source_language} to {target_language} using "
                "the whole transcript '{whole_transcript}' as context which is in english. "
                "Ensure the translated text conveys the same meaning and has the same word count.",
    expected_output="A translated version of the segment in {target_language}, maintaining the same number of words and meaning.",
    agent=translation_agent
)

# --- Crew Setup ---
translation_crew_segment = Crew(
    agents=[translation_agent],
    tasks=[translation_task]
)

# --- Asynchronous Function to Translate Segments ---
async def translate_segment(whole_transcript, segment, source_language, target_language):
    """Translates a segment while preserving meaning and word count using the full transcript as context."""
    result = await asyncio.to_thread(
        translation_crew_segment.kickoff,
        inputs={
            'whole_transcript': whole_transcript,
            'segment': segment,
            'source_language': source_language,
            'target_language': target_language
        }
    )
    return result.raw  # Extracting only the translated output