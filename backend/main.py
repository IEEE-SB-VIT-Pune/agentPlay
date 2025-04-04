import time
from quart import Quart, request, jsonify, send_file
from quart_cors import cors
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from mistralai import Mistral
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import aiohttp
from mtranslate import translate
import json
import os
import edge_tts
from crew_helper import count_words_and_translate, translate_segment
import asyncio
from collections import defaultdict
import base64
import faiss
import os
import yt_dlp
import torch
# from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains.question_answering import load_qa_chain
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from crewai import Agent, Task, Crew, LLM, Process
from crewai_tools import SerperDevTool
import traceback  # ✅ Added traceback import




# Voice configurations
VOICE_CONFIGS = {
    'en': "en-US-JennyNeural",
    'hi': "hi-IN-SwaraNeural",
    'es': "es-MX-JorgeNeural",
    'fr': "fr-FR-HenriNeural",
    'de': "de-DE-KillianNeural",
    'ja': "ja-JP-KeitaNeural",
    'ko': "ko-KR-SunHiNeural",
    'zh': "zh-CN-XiaoxiaoNeural",
    'it': "it-IT-DiegoNeural",
    'pt': "pt-BR-AntonioNeural",
    'ru': "ru-RU-DmitryNeural",
    'nl': "nl-NL-MaartenNeural",
    'tr': "tr-TR-AhmetNeural",
    'pl': "pl-PL-MarekNeural",
    'id': "id-ID-ArdiNeural",
    'th': "th-TH-NiwatNeural",
    'vi': "vi-VN-HoaiMyNeural"
}

LANGUAGE_MAP = {
    'en': "English",
    'hi': "Hindi",
    'es': "Spanish",
    'fr': "French",
    'de': "German",
    'ja': "Japanese",
    'ko': "Korean",
    'zh': "Chinese (Mandarin)",
    'it': "Italian",
    'pt': "Portuguese (Brazilian)",
    'ru': "Russian",
    'nl': "Dutch",
    'tr': "Turkish",
    'pl': "Polish",
    'id': "Indonesian",
    'th': "Thai",
    'vi': "Vietnamese"
}


# Rate limiting settings 
RATE_LIMIT_DELAY = 2  # Delay in seconds between API requests
MAX_RETRIES = 3  # Maximum number of retries for failed requests
MAX_CONCURRENT_REQUESTS = 2  # Limit the number of concurrent requests 

# function to format timestamp
def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds+1:02d}"

# function to translate text into target language
async def translate_text_async(text, target_language):
    """Translate text asynchronously using mtranslate."""
    try:
        # Create a small delay to avoid rate limits
        await asyncio.sleep(0.2)
        # Run the synchronous translate function in a thread pool
        translated_text = await asyncio.to_thread(translate, text, target_language)
        return translated_text
    except Exception as e:
        print(f"Translation error: {str(e)}")
        return text

async def process_transcript(transcript_original, whole_transcript, video_id, source_lang, target_lang, segment_no):
    segment_no = int(segment_no)
    path = f"data/{video_id}"
    os.makedirs(path, exist_ok=True)

    path = f"data/{video_id}/segment_{segment_no:04d}.mp3"
    
    # Find the segment index
    segment_index = next((i for i, seg in enumerate(transcript_original) if seg['Segment'] == segment_no), None)
    if segment_index is None:
        print(f"❌ Segment {segment_no} not found.")
        return []

    # Define context range
    start_index = max(0, segment_index - 5)
    end_index = min(len(transcript_original), segment_index + 11)
    print("start_index"+str(start_index)+"  end_index"+str(end_index))
    data = []
    
    # ✅ Correcting how whole_words is extracted
    whole_words = whole_transcript.split()  # Tokenize transcript into words
    total_words = len(whole_words)

    for i in range(start_index, end_index):
        print(i)
        if i < 0 or i >= len(transcript_original):  # ✅ Correct boundary check
            continue

        segment = transcript_original[i]
        seg_no = segment['Segment']

        # ✅ Check if segment already exists
        segment_path = f"data/{video_id}/segment_{seg_no:04d}.mp3"
        if os.path.exists(segment_path):
            print(f"✅ Segment {seg_no} already exists. Skipping...")
            continue  

        print(f"🔍 Processing missing segment {seg_no}...")

        segment_text = segment['Text']
        segment_words = segment_text.split()
        segment_word_count = len(segment_words)

        # Compute Start & End Indices for Context Window
        segment_start_word_idx = sum(len(s['Text'].split()) for s in transcript_original[:i])

        # Define Left & Right Context Limits
        left_idx = max(0, segment_start_word_idx - 50)
        right_idx = min(total_words, segment_start_word_idx + segment_word_count + 50)

        # Handle Edge Cases
        if i == 0:
            left_idx = 0
            right_idx = min(100, total_words)
        elif i == len(transcript_original) - 1:
            left_idx = max(0, total_words - 100)
            right_idx = total_words

        # ✅ Extract context words correctly
        context_text = " ".join(whole_words[left_idx:right_idx])

        # Async Translation with Retry
        max_retries = 3
        delay = 5  

        for attempt in range(max_retries):
            try:
                txt = await translate_segment(context_text, segment_text, source_lang, target_lang)
                break  
            except Exception as e:
                if "429" in str(e):  
                    print(f"Rate limit exceeded. Retrying in {delay} seconds (Attempt {attempt + 1}/{max_retries})...")
                    await asyncio.sleep(delay)
                    delay *= 2  
                else:
                    raise e  
        else:
            print(f"❌ Failed to translate segment {seg_no} after {max_retries} retries.")
            txt = segment_text  

        # Store translated data
        data.append({
            'Segment': seg_no,
            'Text': txt,
            'Start': segment['Start'],
            'End': segment['End'],
            'Duration': segment['Duration']
        })

    return data 

# function to get transcript with timestamps
async def get_transcript_with_timestamps_async(video_id):
    """Get the transcript with timestamps from a YouTube video ID.

    If English transcript is available, use it as-is.
    If English is not available but Hindi is, translate Hindi to English.
    """
    try:
        transcript_list = None
        source_language = None

        # Try to get English transcript first
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            source_language = 'en'
            print("Using English transcript (no translation needed)")
        except:
            # If English not available, try Hindi transcript
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi'])
                source_language = 'hi'
                print("Using Hindi transcript, translating to English")
            except:
                # If neither English nor Hindi is available, try to get any available transcript
                try:
                    available_transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                    for transcript in available_transcripts:
                        transcript_list = transcript.fetch()
                        source_language = transcript.language_code
                        needs_translation = (source_language != 'en')
                        print(f"Using {source_language} transcript, {'translating to English' if needs_translation else 'no translation needed'}")
                        break
                except Exception as e:
                    print(f"Error finding any transcript: {str(e)}")
                    return None,None,None

        if not transcript_list:
            print("No transcript available")
            return None,None,None

        # Initialize empty list to store transcript data
        data = []
        translation_tasks = []

        string_transcript=""
        # Create translation tasks for each segment if needed
        for i, entry in enumerate(transcript_list):
            # Get segment number (starting from 1)
            segment_number = i + 1

            # Get timing information
            start_time = entry['start']
            duration = entry['duration'] if 'duration' in entry else 0
            calculated_end_time = start_time + duration

            # Adjust end time if needed
            if i < len(transcript_list) - 1:
                next_start_time = transcript_list[i + 1]['start']
                if calculated_end_time > next_start_time:
                    end_time = next_start_time
                    adjusted_duration = end_time - start_time
                else:
                    end_time = calculated_end_time
                    adjusted_duration = duration
            else:
                end_time = calculated_end_time
                adjusted_duration = duration

            # Format timestamps
            start_formatted = format_timestamp(start_time)
            end_formatted = format_timestamp(end_time)
            duration_formatted = format_timestamp(adjusted_duration)

            # Get original text
            original_text = entry['text']
            string_transcript +=entry['text']
            # If no translation needed, append directly
            data.append({
                "Segment": segment_number,
                "Text": original_text,
                "Start": start_formatted,
                "End": end_formatted,
                "Duration": duration_formatted
            })

        # Add transcript metadata
        return data,source_language,string_transcript
    except Exception as e:
        print(f"Error retrieving transcript: {str(e)}")
        return None,None,None



## Pratham

async def generate_audio_and_save(text, lang, output_path):
    """Generate audio using edge-tts."""
    try:
        voice = VOICE_CONFIGS.get(lang, "en-AU-WilliamNeural")
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"Error generating audio: {str(e)}")
        return False
    
async def create_audio_segments(transcript_data,video_id, target_language):
    """
    Generates and saves audio segments based on the provided transcript and target language.
    """
    
    # Create necessary directories
    audio_path = os.path.join('data', video_id,)
    os.makedirs(audio_path, exist_ok=True)
    
    # Create tasks for all segments
    tasks = []
    for segment in transcript_data:
        if not segment['Text'].strip():
            continue
            
        async def process_segment(segment_text, segment_num):
            try:
                # Translate the text
                translated_text = await translate_text_async(segment_text, target_language)
                # Generate and save audio
                audio_file = os.path.join(audio_path, f"segment_{segment_num:04d}.mp3")
                await generate_audio_and_save(translated_text, target_language, audio_file)
                print(f"Processed segment {segment_num}")
            except Exception as e:
                print(f"Error processing segment {segment_num}: {str(e)}")
        
        # Add task to list
        tasks.append(process_segment(segment['Text'], segment['Segment']))
    
    # Execute all tasks concurrently
    await asyncio.gather(*tasks)
    print(f"Audio segments saved in: {audio_path}")

class TranscriptStore:
    def __init__(self, video_id, transcript_original, source_lang,original_string_transcript,whole_string_transcript_english):
        """
        Constructor to initialize video ID.
        Will always return transcript in ENGLISH.
        :param video_id: Unique ID of the video.
        """
        self.video_id = video_id

        if transcript_original is None:
            self.is_transcript_exists = False
        else:
            self.transcript_original = transcript_original
            self.original_video_lang = source_lang # helps while making audio
            self.is_transcript_exists = True
            self.audio_generated = False
            self.audio_generated_language = None
            self.is_summary_generated = None
            self.summary=""
            self.whole_string_transcript_original = original_string_transcript
            self.whole_string_transcript_english = whole_string_transcript_english

    @classmethod
    async def create(cls, video_id):
        """
        Async factory method to create an instance with awaited data.
        """
        transcript_original, source_lang , original_string_transcript = await get_transcript_with_timestamps_async(video_id)
        whole_string_transcript_english = original_string_transcript
        if(source_lang!='en'):
            whole_string_transcript_english = await count_words_and_translate(original_string_transcript)
        return cls(video_id, transcript_original, source_lang,original_string_transcript,whole_string_transcript_english)
    

## YOGIRAJ

def summarize_chunk(chunk):
    """
    Summarize a single chunk of the transcript using Mistral.
    Implements retry logic to handle rate limits.
    """
    retries = 0
    while retries < MAX_RETRIES:
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a note-taking assistant. Generate concise, well-structured notes from the following transcript segment. Focus on key points and main ideas."
                },
                {
                    "role": "user",
                    "content": f"Generate structured notes from this transcript segment:\n\n{chunk}"
                }
            ]
            
            response = client.chat.complete(
                model=model,
                messages=messages,
                max_tokens=1000,
                temperature=0.3  # Lower temperature for more focused outputs
            )
            return response.choices[0].message.content
        except Exception as e:
            if "rate limit" in str(e).lower():
                retries += 1
                print(f"Rate limit exceeded. Retrying ({retries}/{MAX_RETRIES})...")
                time.sleep(RATE_LIMIT_DELAY * retries)  # Exponential backoff
            else:
                return f"Error generating summary for chunk: {str(e)}"
    return f"Error: Failed to summarize chunk after {MAX_RETRIES} retries."


def get_notes_from_summary(transcript):
    notes = ''
    # Increase chunk size to reduce the number of API calls
    chunk_size = 8000  # Increased from 4000
    chunks = [transcript[i:i + chunk_size] for i in range(0, len(transcript), chunk_size)]
    
    # Use ThreadPoolExecutor with limited concurrency
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        futures = [executor.submit(summarize_chunk, chunk) for chunk in chunks]
        
        for future in as_completed(futures):
            try:
                summary = future.result()
                notes += summary + "\n\n----------------------------------------\n\n"
            except Exception as e:
                notes += f"Error generating summary: {str(e)}\n\n"
    
    # Remove all instances of * and #
    notes = notes.replace("*", "").replace("#", "")
    return notes

#NITESH


os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE" 
os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")



# Initialize models and tools
llm = LLM(model="gemini/gemini-1.5-flash")
llm_genai = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.4)
embedding_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
serper_tool = SerperDevTool()

# Constants
SIMILARITY_THRESHOLD = 0.3
def chunk_transcript(transcript_data, max_words=50):
    """
    Splits the transcript into chunks of approximately `max_words` words while preserving timestamps.
    """
    # Extract the transcript list
    transcript_list = transcript_data.get("transcript", [])
    print(transcript_data)

    if not transcript_list or not isinstance(transcript_list, list):
        print("Error: Transcript data is empty or not in the expected format.")
        return []

    chunks = []
    current_chunk = []
    current_word_count = 0
    chunk_start_time = None

    for segment in transcript_list:
        if not isinstance(segment, dict) or "Text" not in segment:
            print(f"Skipping invalid segment: {segment}")
            continue  # Skip invalid segments

        words = segment["Text"].split()
        word_count = len(words)

        if chunk_start_time is None:
            chunk_start_time = segment["Start"]

        # If adding this segment exceeds max_words, finalize the current chunk
        if current_word_count + word_count > max_words:
            chunk_text = " ".join(current_chunk)
            chunk_end_time = transcript_list[transcript_list.index(segment) - 1]["End"]
            
            chunks.append({
                "Text": chunk_text,
                "Start": chunk_start_time,
                "End": chunk_end_time
            })

            # Reset for the next chunk
            current_chunk = []
            current_word_count = 0
            chunk_start_time = segment["Start"]

        # Add words to the current chunk
        current_chunk.extend(words)
        current_word_count += word_count

    # Add the last chunk
    if current_chunk:
        chunk_text = " ".join(current_chunk)
        chunk_end_time = transcript_list[-1]["End"]
        chunks.append({
            "Text": chunk_text,
            "Start": chunk_start_time,
            "End": chunk_end_time
        })

    return chunks

def store_embeddings(chunks):
    """Create FAISS index from document chunks"""
    print(chunks)
    texts = [chunk["Text"] for chunk in chunks]
    vector_store = FAISS.from_texts(texts, embedding_model)
    return vector_store

def check_query_relevance(vector_store, query):
    """Check if query is relevant to the transcript context"""
    docs_and_scores = vector_store.similarity_search_with_score(query, k=1)
    if not docs_and_scores:
        return False
    best_match, best_score = docs_and_scores[0]
    similarity_score = 1 - best_score
    return similarity_score >= SIMILARITY_THRESHOLD

def get_conversational_chain():
    prompt_template = """
    You are an AI assistant helping users find relevant information from a video transcript.
    Context: {context}
    Question: {question}
    Answer:
    """
    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
    chain = load_qa_chain(llm_genai, chain_type="stuff", prompt=prompt)
    return chain

def search_query_with_llm(vector_store, chunks, query):
    """ Search for relevant chunks and use LLM to generate an answer """
    docs_and_scores = vector_store.similarity_search_with_score(query, k=3)
    best_match, best_score = docs_and_scores[0]
    similarity_score = 1 - best_score

    if similarity_score < SIMILARITY_THRESHOLD:
        return None

    # Convert to Document objects for the QA chain
    best_chunks = [Document(page_content=best_match.page_content)]
    
    # Get the QA chain
    qa_chain = get_conversational_chain()
    
    # Use invoke method instead of run (to avoid deprecation warning)
    answer = qa_chain.run(input_documents=best_chunks, question=query)
    
    # Extract the answer - adjust this based on your chain's output structure
    answer = answer
    
    return answer
def get_yt_details(video_id):
    """Fetches YouTube video title and channel."""
    try:
        ydl_opts = {}
        yt_url = f'https://www.youtube.com/watch?v={video_id}'
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(yt_url, download=False)
            return info.get('uploader', 'Unknown Channel'), info.get('title', 'Unknown Title')
    except Exception as e:
        print(f"Error getting YouTube details: {str(e)}")
        return "Unknown Channel", "Unknown Title"

def refine_answer_with_serper(query, context_answer, yt_channel, yt_title):
    """Refine answer with additional web search info if needed"""
    try:
        refinement_agent = Agent(
            role="Answer Refinement Agent",
            goal=(
                "Enhance the generated response using the latest web data. If the query pertains to a YouTube channel, provide information specifically related to {yt_channel}. "
                "If the query is based on the video title, ensure the response focuses on {yt_title} as referenced in the transcript."
            ),
            backstory="This agent verifies and refines responses using real-time search when needed. If no valid source is found, it relies solely on embeddings.",
            verbose=True,
            memory=True,
            tools=[serper_tool],
            llm=llm,
            allow_delegation=False
        )

        refinement_task = Task(
            description=(
                "Improve the response by incorporating the latest web data for the query: {query} and the given context answer: {context_answer}. "
                "Since the query is related to the YouTube channel {yt_channel} and video title {yt_title}, ensure that the response remains aligned with this context. "
                "If no valid information is found online, generate the response only from embeddings and do not mention that the internet did not provide relevant details."
                "Give the straight forward answer and dont provide unnecessary information"
            ),
            expected_output="A well-verified and refined response with accurate information. If no valid online sources are found, the response should explicitly state that the answer is based solely on embeddings.",
            tools=[serper_tool],
            agent=refinement_agent,
        )

        crew = Crew(agents=[refinement_agent], tasks=[refinement_task], verbose=True, process=Process.sequential)
        result = crew.kickoff(inputs={'query': query, 'context_answer': context_answer, 'yt_channel': yt_channel, 'yt_title': yt_title})
        return result.raw
    except Exception as e:
        print(f"Error refining answer: {str(e)}")
        return context_answer  # Fallback to original answer if refinement fails


# In-memory storage for both FAISS indexes and metadata
index_cache = {}  # For storing FAISS vector stores
metadata_cache = {}  # For storing transcript, channel, title

def is_processed(video_id):
    """ Check if a FAISS index exists in memory for the given video_id. """
    return video_id in index_cache

def store_metadata(video_id, transcript, yt_channel, yt_title,chunks):
    """ Stores transcript, channel, and title in metadata cache """
    metadata_cache[video_id] = {
        "transcript": transcript,
        "yt_channel": yt_channel,
        "yt_title": yt_title,
        "chunks":chunks
    }

def store_faiss_index(video_id, vector_store):
    """ Stores FAISS index in memory cache """
    try:
        print(f"🔹 Saving FAISS index in memory for video: {video_id}")
        index_cache[video_id] = vector_store
        print(f"✅ FAISS index stored successfully in memory")
        return True
    except Exception as e:
        print(f"🚨 Failed to store FAISS index: {str(e)}")
        return False

def load_faiss_index(video_id):
    """ Loads the FAISS index from memory """
    print(f"🔹 Checking for FAISS index in memory for video: {video_id}")

    if video_id not in index_cache:
        raise KeyError(f"🚨 FAISS index not found in memory for video: {video_id}")

    try:
        return index_cache[video_id]
    except Exception as e:
        raise RuntimeError(f"Failed to load FAISS index from memory: {str(e)}")

async def precompute(video_id):
    """ Precompute transcript and embeddings if not already stored in memory """
    if is_processed(video_id):
        return {"status": "cached"}

    try:
        transcript = await show_transcript(video_id)
        if "error" in transcript:
            return {"error": transcript["error"]}

        chunks = chunk_transcript(transcript)
        vector_store = store_embeddings(chunks)  # Create FAISS index

        yt_channel, yt_title = get_yt_details(video_id)

        # Store transcript and metadata in cache
        store_metadata(video_id, transcript, yt_channel, yt_title,chunks)

        # Store FAISS index in memory
        if not store_faiss_index(video_id, vector_store):
            return {"error": "Failed to store FAISS index in memory"}

        return {"status": "success", "video_id": video_id}
    except Exception as e:
        return {"error": f"Precompute failed: {str(e)}"}















































# Initialize Mistral client  
api_key = "AO2SetJOyHJdppAaMA32iydjFWvXsLfr"  # Replace with your actual API key
model = "mistral-large-latest"
client = Mistral(api_key=api_key)

# Create Quart app with CORS support
app = Quart(__name__)
app = cors(app)  # Enable CORS for all routes

@app.route('/')
async def home():
    return "Welcome to Quart!"

@app.route('/listen_audio/<video_id>/<target_language>/<segment_number>', methods=['GET'])
async def get_audio(video_id, target_language, segment_number):
    try:
        segment_number = int(segment_number)
        segment_path = f"data/{video_id}/segment_{segment_number:04d}.mp3"

        transcript_key = f"{video_id}_transcript"
        
        # Check if transcript exists
        if transcript_key in globals() and globals()[transcript_key].is_transcript_exists:
            print(f"✅ Transcript found for {video_id}.")

            # If segment exists, send immediately and process in background
            if os.path.exists(segment_path):
                print(f"✅ Segment {segment_number} exists: {segment_path}. Sending file...")
                
                # Create background task
                asyncio.create_task(process_and_generate_audio(video_id, target_language, segment_number))

                return await send_file(segment_path, mimetype="audio/mpeg")

            print(f"🔍 Segment {segment_number} not found. Processing synchronously...")

            # Extract transcript data
            transcript_data = globals()[transcript_key]
            transcript_original = transcript_data.transcript_original
            whole_transcript_english = transcript_data.whole_string_transcript_english
            source_lang = transcript_data.original_video_lang

            print("📜 Processing transcript...")
            temp_trans = await process_transcript(
                transcript_original, whole_transcript_english,
                video_id, source_lang, target_language, str(segment_number)
            )

            print("🎵 Creating audio segments...")
            await create_audio_segments(temp_trans, video_id, target_language)

            # Check if file was created
            if os.path.exists(segment_path):
                print(f"✅ Segment created successfully: {segment_path}")
                return await send_file(segment_path, mimetype="audio/mpeg")
            else:
                print("❌ Segment creation failed!")
                return jsonify({"error": "Segment could not be generated"}), 500

        else:
            # If transcript doesn't exist, create it asynchronously and retry
            print(f"🚀 Transcript not found for {video_id}. Creating new transcript...")
            globals()[transcript_key] = await TranscriptStore.create(video_id)
            return await get_audio(video_id, target_language, segment_number)

    except Exception as e:
        print(f"❌ Error in get_audio: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500

@app.route('/show_transcript/<video_id>')
async def show_transcript(video_id):
    try:
        if f"{video_id}_transcript" in globals():
            if globals()[f"{video_id}_transcript"].is_transcript_exists:
                return {"transcript": globals()[f"{video_id}_transcript"].transcript_original}
            else:
                return {"error": "No transcript available for this VIDEO"}
        else: 
            globals()[f"{video_id}_transcript"] = await TranscriptStore.create(video_id)
            return await show_transcript(video_id)
    except Exception as e:
        return {"error": f"An error occurred: show_transcript"}
    
@app.route('/show_data/<video_id>')
async def show_data(video_id):
    try:
        if f"{video_id}_transcript" in globals():
            transcript_store = globals()[f"{video_id}_transcript"]
            if transcript_store.is_transcript_exists:
                return {
                    "video_id": transcript_store.video_id,
                    "transcript_exists": transcript_store.is_transcript_exists,
                    "original_language": transcript_store.original_video_lang,
                    "audio_generated": transcript_store.audio_generated,
                    "audio_generated_language": transcript_store.audio_generated_language,
                    "transcript_data": transcript_store.transcript_original,
                    "Summary_generates": transcript_store.is_summary_generated,
                    "total_segments": len(transcript_store.transcript_original) if transcript_store.transcript_original else 0
                }
            else:
                return {"error": "No transcript available for this video"}
        else:
            globals()[f"{video_id}_transcript"] = await TranscriptStore.create(video_id)
            return await show_data(video_id)
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

@app.route('/summary/<video_id>', methods=['GET'])
async def summary_api(video_id):
    try:
        if f"{video_id}_transcript" in globals():
            transcript_store = globals()[f"{video_id}_transcript"]
            
            # Check if summary already exists
            if transcript_store.is_summary_generated:
                notes = transcript_store.summary
                return jsonify({"summary": notes}), 200
            else:
                trans_temp = transcript_store.whole_string_transcript_english
                # Get the summary as structured notes
                notes = get_notes_from_summary(trans_temp)
                
                # Store the summary and mark as generated
                transcript_store.summary = notes
                transcript_store.is_summary_generated = True
                
                return jsonify({"summary": notes}), 200
        else: 
            # Create the transcript asynchronously and store it
            globals()[f"{video_id}_transcript"] = await TranscriptStore.create(video_id)
            return await summary_api(video_id)
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

async def process_and_generate_audio(video_id, target_language, segment_number):
    """Handles async processing of transcript and audio in the background."""
    try:
        transcript_data = globals()[f"{video_id}_transcript"]
        print("Inside process_transcript")
        if globals()[f"{video_id}_transcript"] and transcript_data.is_transcript_exists:
            temp_trans = await process_transcript(
                transcript_data.transcript_original,
                transcript_data.whole_string_transcript_english,
                video_id, transcript_data.original_video_lang, target_language, str(segment_number)
            )
            print("inside create_audio_segments")
            await create_audio_segments(temp_trans, video_id, target_language)
            print(f"✅ Background processing completed for segment {segment_number}.")
        else:
            print(f"⚠️ Transcript not found for {video_id}, skipping background processing.")
    except Exception as e:
        print(f"❌ Error in background processing: {e}")



#Nitesh


# @app.route('/show_transcript/<video_id>')
# async def show_transcript(video_id):
#     try:
#         print(video_id)
#         print(type(video_id))
            
#         if f"{video_id}_transcript" in globals():
#             if globals()[f"{video_id}_transcript"].is_transcript_exists:
#                 # show the transcript
#                 return {"transcript": globals()[f"{video_id}_transcript"].transcript_english}
#             else:
#                 return {"error": "No transcript available for this VIDEO"}
#         else: 
#             # Create the transcript asynchronously and store it
#             globals()[f"{video_id}_transcript"] = await TranscriptStore.create(video_id)
#             return await show_transcript(video_id)
#     except Exception as e:
#         return {"error": f"An error occurred: show_transcript"}



#Nitesh
@app.route('/precompute/<video_id>', methods=['GET'])
async def precompute_route(video_id):
    """ Route to precompute transcript & embeddings and store in memory. """
    precompute_result = await precompute(video_id)
    if "error" in precompute_result:
        return jsonify(precompute_result), 400

    return jsonify(precompute_result), 200

@app.route('/process', methods=['POST'])
async def process():
    """ Processes user query using stored transcript and FAISS index from memory. """
    data = await request.json
    query = data.get('query')
    mode = data.get('addition_mode', True)
    video_id = data.get("video_id")

    if not video_id or not query:
        return jsonify({'error': 'Missing video_id or query'}), 400

    # If not processed, precompute first
    if not is_processed(video_id):
        precompute_result = await precompute(video_id)
        if "error" in precompute_result:
            return jsonify({"error": precompute_result["error"]}), 400

    try:
        # Load FAISS index from memory
        vector_store = load_faiss_index(video_id)
    except (KeyError, RuntimeError) as e:
        return jsonify({"error": f"Failed to load FAISS index: {str(e)}"}), 400

    if not vector_store:
        return jsonify({"error": "Failed to load FAISS index"}), 400

    # Retrieve metadata from cache
    cached_data = metadata_cache.get(video_id, {})
    transcript = cached_data.get("transcript")
    yt_channel = cached_data.get("yt_channel", "Unknown Channel")
    yt_title = cached_data.get("yt_title", "Unknown Title")
    chunks = cached_data.get("chunks")

    if not transcript:
        return jsonify({"error": "Transcript not found in cache"}), 400

    if not check_query_relevance(vector_store, query):
        return jsonify({"final_answer": "Query out of context."}), 200

    # Perform similarity search
    # docs_and_scores = vector_store.similarity_search_with_score(query, k=1)
    # best_match, _ = docs_and_scores[0]
    # context_answer = best_match.page_content
    context_answer = search_query_with_llm(vector_store,chunks, query)

    # Refine answer if mode is enabled
    refined_answer = refine_answer_with_serper(query, context_answer, yt_channel, yt_title) if mode else context_answer

    return jsonify({
        "final_answer": refined_answer,
        "channel": yt_channel,
        "title": yt_title
    })

# Debug function to check cache status
@app.route('/cache_status', methods=['GET'])
def cache_status():
    """ Returns information about what's currently in the cache """
    return jsonify({
        "indexed_videos": list(index_cache.keys()),
        "videos_with_metadata": list(metadata_cache.keys())
    })












if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)