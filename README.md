# youtube_to_notes

## Setup

1. Clone the repository:
    ```sh
    git clone <repository_url>
    cd youtube_to_notes
    ```

2. Create a virtual environment:
    ```sh
    python -m venv venv
    ```

3. Activate the virtual environment:
    - On Windows:
        ```sh
        venv\Scripts\activate
        ```
    - On macOS/Linux:
        ```sh
        source venv/bin/activate
        ```

4. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

5. Create a `.env` file in the root directory and add your environment variables:
    ```env
    MISTRAL_API_KEY=<your_api_key>
    ```

## Usage

1. Start the application:
    ```sh
    python app.py
    ```

2. Open Postman and create a new POST request to test the application:
    - URL: `http://127.0.0.1:5000/summary?url=`
    - Params: `url`: `<youtube_video_url>`

3. Send the request and check the response for the notes generated from the YouTube video.
