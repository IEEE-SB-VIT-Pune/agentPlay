import os
from flask import Flask, request
from youtube_transcript_api import YouTubeTranscriptApi
from mistralai import Mistral

app = Flask(__name__)

# Initialize Mistral client
api_key = os.getenv("MISTRAL_API_KEY")
model = "mistral-large-latest"
client = Mistral(api_key=api_key)

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
    notes = ''
    # Split the transcript into chunks of approximately 4000 characters
    # (Mistral can handle longer contexts than the previous transformer model)
    chunk_size = 4000
    chunks = [transcript[i:i + chunk_size] for i in range(0, len(transcript), chunk_size)]
    
    for chunk in chunks:
        # Create a prompt that instructs Mistral to generate structured notes
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
        
        # Get response from Mistral
        try:
            response = client.chat.complete(
                model=model,
                messages=messages,
                max_tokens=1000,
                temperature=0.3  # Lower temperature for more focused outputs
            )
            
            # Add the summary to notes
            summary = response.choices[0].message.content
            notes += summary + "\n\n----------------------------------------\n\n"
            
        except Exception as e:
            notes += f"Error generating summary for chunk: {str(e)}\n\n"
    
    return notes

if __name__ == '__main__':
    app.run(debug=True)