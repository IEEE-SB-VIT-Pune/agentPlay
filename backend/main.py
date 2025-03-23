import time
from flask import Flask, request, jsonify
from flask_cors import CORS  # Enable CORS 
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from mistralai import Mistral
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import aiohttp
from mtranslate import translate
import json
from flask import Flask, send_file
import os
import edge_tts

# Initialize Mistral client  
api_key = "AO2SetJOyHJdppAaMA32iydjFWvXsLfr"  # Replace with your actual API key
model = "mistral-large-latest"
client = Mistral(api_key=api_key)

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

# function to get transcript with timestamps
async def get_transcript_with_timestamps_async(video_id):
    """Get the transcript with timestamps from a YouTube video ID.

    If English transcript is available, use it as-is.
    If English is not available but Hindi is, translate Hindi to English.
    """
    try:
        transcript_list = None
        source_language = None
        needs_translation = False

        # Try to get English transcript first
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            source_language = 'en'
            needs_translation = False
            print("Using English transcript (no translation needed)")
        except:
            # If English not available, try Hindi transcript
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi'])
                source_language = 'hi'
                needs_translation = True
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
                    return None,None

        if not transcript_list:
            print("No transcript available")
            return None,None

        # Initialize empty list to store transcript data
        data = []
        translation_tasks = []

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

            if needs_translation:
                # Create translation task
                task = asyncio.create_task(translate_text_async(original_text, 'en'))
                translation_tasks.append((segment_number, original_text, task, start_formatted, end_formatted, duration_formatted))
            else:
                # If no translation needed, append directly
                data.append({
                    "Segment": segment_number,
                    "Text": original_text,
                    "Start": start_formatted,
                    "End": end_formatted,
                    "Duration": duration_formatted
                })

        # Wait for all translation tasks to complete
        if needs_translation:
            for segment_number, original_text, task, start_formatted, end_formatted, duration_formatted in translation_tasks:
                translated_text = await task
                data.append({
                    "Segment": segment_number,
                    "Text": translated_text,
                    "Start": start_formatted,
                    "End": end_formatted,
                    "Duration": duration_formatted
                })

        # Sort data by segment number to ensure correct order
        data.sort(key=lambda x: x["Segment"])

        # Add transcript metadata
        return data,source_language
    except Exception as e:
        print(f"Error retrieving transcript: {str(e)}")
        return None,None
    
## Pratham


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
    
async def create_audio_segments(transcript_store, target_language):
    """
    Generates and saves audio segments based on the provided transcript and target language.
    """
    transcript_data = transcript_store.transcript_english  # This is a list of dictionaries
    video_id = transcript_store.video_id
    
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
                audio_file = os.path.join(audio_path, f"segment_{segment_num-1:04d}.mp3")
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
    def __init__(self, video_id, transcript_english, source_lang):
        """
        Constructor to initialize video ID.
        Will always return transcript in ENGLISH.
        :param video_id: Unique ID of the video.
        """
        self.video_id = video_id

        if transcript_english is None:
            self.is_transcript_exists = False
        else:
            self.transcript_english = transcript_english
            self.original_video_lang = source_lang # helps while making audio
            self.is_transcript_exists = True
            self.audio_generated = False
            self.audio_generated_language = None
            self.is_summary_generated = None
            self.summary=""

    @classmethod
    async def create(cls, video_id):
        """
        Async factory method to create an instance with awaited data.
        """
        transcript_english, source_lang = await get_transcript_with_timestamps_async(video_id)
        return cls(video_id, transcript_english, source_lang)
    

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


app = Flask(__name__)

@app.route('/')  # Defines the route for the home page
def home():
    return "Welcome to Flask!"


@app.route('/create_audio/<video_id>/<target_language>')
async def generate_audio(video_id, target_language):
    try:
        print(target_language)
        print(type(target_language))
        print(video_id)
        print(type(video_id))
        # Clean the target_language parameter
        target_language = target_language.strip("'\"")  # Remove any quotes
        print(target_language)
        if target_language not in VOICE_CONFIGS:
            return {"error": f"Target language '{target_language}' not available. Available languages: {list(VOICE_CONFIGS.keys())}"}
            
        if f"{video_id}_transcript" in globals():
            if globals()[f"{video_id}_transcript"].is_transcript_exists:
                # processing the audio if already generated then return the message

                # if the original language is the same as the target language then return the error
                if globals()[f"{video_id}_transcript"].original_video_lang == target_language:
                    return {"error": "Audio in this video in the same language"}
                
                # if audio already generated in that language then return the message
                if globals()[f"{video_id}_transcript"].audio_generated and globals()[f"{video_id}_transcript"].audio_generated_language == target_language:
                    return {"message": f"Audio already generated for this video in {target_language}"}
                # if audio not generated in that language then generate the audio
                else:
                    await create_audio_segments(globals()[f"{video_id}_transcript"], target_language)
                    globals()[f"{video_id}_transcript"].audio_generated = True
                    globals()[f"{video_id}_transcript"].audio_generated_language = target_language
                    return {"message": "Audio generated successfully"}
            else:
                return {"error": "No transcript available for this VIDEO"}
        else:
            # Create the transcript asynchronously and store it
            globals()[f"{video_id}_transcript"] = await TranscriptStore.create(video_id)
            return await generate_audio(video_id, target_language)
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

@app.route('/listen_audio/<video_id>/<segment_number>', methods=['GET'])  # Explicitly defining GET request
async def get_audio(video_id, segment_number):
    try:
        segment_number = int(segment_number)
        print(video_id)
        print(type(video_id))
            
        if f"{video_id}_transcript" in globals():
            if globals()[f"{video_id}_transcript"].is_transcript_exists:
                # send audio file
                return send_file(f"data/{video_id}/segment_{segment_number-1:04d}.mp3", mimetype="audio/mpeg")
            else:
                return {"error": "No transcript available for this VIDEO"}
        else:
            # Create the transcript asynchronously and store it
            globals()[f"{video_id}_transcript"] = await TranscriptStore.create(video_id)
            return await get_audio(video_id, segment_number)
    except Exception as e:
        return {"error": f"An error occurred: sending audio{e}"}

@app.route('/show_transcript/<video_id>')
async def show_transcript(video_id):
    try:
        print(video_id)
        print(type(video_id))
            
        if f"{video_id}_transcript" in globals():
            if globals()[f"{video_id}_transcript"].is_transcript_exists:
                # show the transcript
                return {"transcript": globals()[f"{video_id}_transcript"].transcript_english}
            else:
                return {"error": "No transcript available for this VIDEO"}
        else: 
            # Create the transcript asynchronously and store it
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
                    "transcript_data": transcript_store.transcript_english,
                    "Summary_generates": transcript_store.is_summary_generated,
                    "total_segments": len(transcript_store.transcript_english) if transcript_store.transcript_english else 0
                }
            else:
                return {"error": "No transcript available for this video"}
        else:
            # Create the transcript asynchronously and store it
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
                # Get the transcript
                trans = transcript_store.transcript_english
                trans_temp = ""
                for i in trans:
                    trans_temp += i["Text"]

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
if __name__ == '__main__':
    app.run(debug=True)