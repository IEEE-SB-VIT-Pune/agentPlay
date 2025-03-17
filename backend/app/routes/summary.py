from pytube import YouTube

@app.route('/summary', methods=['GET'])
def summary_api():
    url = request.args.get('url', '')
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    # Extract video ID
    video_id = url.split('v=')[-1].split('&')[0] if 'v=' in url else url.split('youtu.be/')[1] if 'youtu.be' in url else ''
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"}), 400

    # Fetch channel_id using pytube
    try:
        yt = YouTube(url)
        channel_id = yt.channel_id
        print(f"Channel ID: {channel_id}")
    except Exception as e:
        return jsonify({"error": f"Error fetching channel info: {str(e)}"}), 400

    # Get transcript
    transcript = get_transcript(video_id)
    if isinstance(transcript, str) and transcript.startswith("Error"):
        return jsonify({"error": transcript}), 400

    # Translate if not English
    if not is_english(transcript):
        print("Transcript is not in English. Translating...")
        transcript = translate_text(transcript, target_language='en')

    # Summarize
    notes = get_notes_from_summary(transcript)

    # Return both summary and channel_id
    return jsonify({
        "channel_id": channel_id,
        "summary": notes
    }), 200
