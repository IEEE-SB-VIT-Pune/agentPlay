from flask import Flask, request
from youtube_transcript_api import YouTubeTranscriptApi
from transformers import pipeline

app = Flask(__name__)

@app.route('/summary', methods=['GET'])
def summary_api():
    url = request.args.get('url', '')
    if not url:
        return "URL parameter is required", 400

    # Extract video ID from URL
    video_id = url.split('v=')[-1].split('&')[0] if 'v=' in url else url.split('youtu.be/')[1] if 'youtu.be' in url else ''
    if not video_id:
        return "Invalid YouTube URL", 400

    # Get the transcript
    transcript = get_transcript(video_id)
    if 'Error' in transcript:
        return transcript, 400

    # Get the summary as structured notes
    notes = get_notes_from_summary(transcript)
    return notes, 200

def get_transcript(video_id):
    try:
        # Fetch the transcript for the video
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = ' '.join([d['text'] for d in transcript_list])
        return transcript
    except Exception as e:
        return f"Error fetching transcript: {str(e)}"

def get_notes_from_summary(transcript):
    # Initialize the Hugging Face summarizer
    summariser = pipeline('summarization')
    notes = ''
    # Split the transcript into manageable chunks for summarization
    for i in range(0, (len(transcript)//1000)+1):
        summary_text = summariser(transcript[i*1000:(i+1)*1000])[0]['summary_text']
        
        # Format the summary as notes
        notes += f"### Key Points:\n"
        notes += f"1. {summary_text.strip()}\n\n"
        notes += "----------------------------------------\n"

    return notes

if __name__ == '__main__':
    app.run(debug=True)
