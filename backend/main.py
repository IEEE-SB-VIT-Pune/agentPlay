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
            self.is_summary_generated=False
            self.is_notes_generated=False
            self.summary=False
            self.notes=False

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

def summarize_chunk(chunk, mode="summary"):
    """
    Summarize a single chunk of text using Mistral.
    Supports both 'notes' and 'summary' generation modes.
    
    Args:
        chunk: Text content to process
        mode: Either "notes" (for detailed notes) or "summary" (for concise summary)
        
    Returns:
        Processed content based on the selected mode
    """
    retries = 0
    while retries < MAX_RETRIES:
        try:
            if mode == "notes":
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a professional note-taking assistant. Generate detailed, "
                            "well-structured notes from the following content. Include:\n"
                            "1. Key concepts and main ideas\n"
                            "2. Important technical terms\n"
                            "3. Logical structure with bullet points\n"
                            "4. Relevant examples (when helpful)\n"
                            "Format with clear headings and bullet points."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Generate comprehensive notes from this content:\n\n{chunk}"
                    }
                ]
            else:  # summary mode
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are an expert summary generation assistant. Create a concise, "
                            "coherent summary that captures the essential information.\n"
                            "Focus on:\n"
                            "1. Key points and main ideas\n"
                            "2. Logical flow between concepts\n"
                            "3. Preservation of important terms\n"
                            "4. Omitting redundant examples\n"
                            "Structure as a single cohesive paragraph."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Generate a concise summary of this content:\n\n{chunk}"
                    }
                ]
            
            response = client.chat.complete(
                model=model,
                messages=messages,
                max_tokens=1000,
                temperature=0.3 if mode == "summary" else 0.5  # More creative for notes
            )
            return response.choices[0].message.content
        except Exception as e:
            if "rate limit" in str(e).lower():
                retries += 1
                print(f"Rate limit exceeded. Retrying ({retries}/{MAX_RETRIES})...")
                time.sleep(RATE_LIMIT_DELAY * retries)
            else:
                return f"Error generating {mode} for chunk: {str(e)}"
    return f"Error: Failed to process chunk after {MAX_RETRIES} retries"


def get_notes_from_summary(transcript):
    """Generate detailed notes from transcript"""
    notes = ''
    chunk_size = 8000
    chunks = [transcript[i:i + chunk_size] for i in range(0, len(transcript), chunk_size)]
    
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        futures = [executor.submit(summarize_chunk, chunk, "notes") for chunk in chunks]
        
        for future in as_completed(futures):
            try:
                notes += future.result() + "\n\n----------------------------------------\n\n"
            except Exception as e:
                notes += f"Error generating notes: {str(e)}\n\n"
    
    return notes.replace("*", "").replace("#", "")


def generate_summary_directly(transcript, max_concurrent_requests=4):
    """Generate summary directly from transcript without notes intermediate"""
    if not transcript:
        return "No transcript available for summary generation"
    
    chunk_size = 8000
    chunks = [transcript[i:i + chunk_size] for i in range(0, len(transcript), chunk_size)]
    
    with ThreadPoolExecutor(max_workers=max_concurrent_requests) as executor:
        futures = [executor.submit(summarize_chunk, chunk, "summary") for chunk in chunks]
        
        chunk_summaries = []
        for future in as_completed(futures):
            try:
                chunk_summaries.append(future.result())
            except Exception as e:
                chunk_summaries.append(f"Error in summarization: {str(e)}")
    
    # Final consolidation
    combined = "\n".join([s for s in chunk_summaries if not s.startswith("Error")])
    return summarize_chunk(combined, "summary") if len(chunk_summaries) > 1 else combined

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
async def concise_summary_api(video_id):
    try:
        if f"{video_id}_transcript" in globals():
            transcript_store = globals()[f"{video_id}_transcript"]
            
            # Check if we already have notes to summarize from
            if transcript_store.is_summary_generated:
                # Generate concise summary from the existing notes
                concise_summary = transcript_store.summary
                return jsonify({"concise_summary": concise_summary}), 200
            else:
                if transcript_store.is_notes_generated:
                    # Now generate the concise summary
                    notes = transcript_store.notes
                    concise_summary = generate_summary_directly(notes)
                    transcript_store.summary  = concise_summary
                    transcript_store.is_summary_generated = True
                else:
                    # First generate the detailed notes
                    trans_temp = transcript_store.whole_string_transcript_english
                    notes = get_notes_from_summary(trans_temp)
                    
                    # Store the notes and mark as generated
                    transcript_store.notes = notes
                    transcript_store.is_notes_generated = True
                    
                    
                    # Now generate the concise summary
                    concise_summary = generate_summary_directly(notes)
                    transcript_store.summary  = concise_summary
                    transcript_store.is_summary_generated = True
                    
                    return jsonify({"concise_summary": concise_summary}), 200
        else: 
            # Create the transcript asynchronously and store it
            globals()[f"{video_id}_transcript"] = await TranscriptStore.create(video_id)
            return await concise_summary_api(video_id)
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    
@app.route('/notes/<video_id>', methods=['GET'])
async def notes(video_id):
    try:
        if f"{video_id}_transcript" in globals():
            transcript_store = globals()[f"{video_id}_transcript"]
            
            # Check if we already have notes to summarize from
            if transcript_store.is_notes_generated:
                return jsonify({"notes": transcript_store.notes}), 200
            else:
                
                # First generate the detailed notes
                trans_temp = transcript_store.whole_string_transcript_english
                notes = get_notes_from_summary(trans_temp)
                transcript_store.is_notes_generated = True
                transcript_store.notes = notes
                
                return jsonify({"notes": notes}), 200
        else: 
            # Create the transcript asynchronously and store it
            globals()[f"{video_id}_transcript"] = await TranscriptStore.create(video_id)
            return await concise_summary_api(video_id)
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

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
        
@app.route('/compute/<video_id>') 

def compute():
   return jsonify({"Nitesh_feature ":{str("summary_generate")}})

@app.route('/process_query/<video_id>')  
 
def processs_query():
    return jsonify({"error": f"An error occurred: {str("Project head pratham")}"})
    


  

# output : solution def





# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5001)
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
    
