function getYouTubeVideoID(url) {
  let match = url.match(/v=([a-zA-Z0-9_-]{11})/);
  return match ? match[1] : null;
}

// Convert MM:SS or HH:MM:SS to seconds
function convertTimeToSeconds(timeStr) {
    let parts = timeStr.split(":").map(Number);
    return parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + parts[2] : parts[0] * 60 + parts[1];
}   

// Function to execute inside YouTube tab to get current video time
function getCurrentVideoTime() {
    let video = document.querySelector("video");
    return video ? Math.floor(video.currentTime) : null;
}

// Find the closest transcript segment based on timestamp
function findClosestSegment(transcript, currentTime) {
    let closestSegment = null;
    let minDiff = Infinity;

    transcript.forEach((segment, index) => {
        let segmentStart = convertTimeToSeconds(segment.Start);
        let diff = Math.abs(segmentStart - currentTime);
        if (diff < minDiff) {
            minDiff = diff;
            closestSegment = index;
        }
    });

    return closestSegment;
}

// Check if the current tab is a YouTube video
document.addEventListener("DOMContentLoaded", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      let url = tabs[0].url;
      if (url.includes("youtube.com/watch?v=")) {
            document.getElementById("output").textContent = "YouTube Video Detected:\n" + url;
            console.log("YouTube Video URL:", url);
            let vid_id = getYouTubeVideoID(url);
          
            //Summary
            document.getElementById("fetchSummary").addEventListener("click", async () => {
                const timeoutDuration = 100000; // 100 seconds timeout
        
                // Function to fetch summary with timeout
                async function fetchWithTimeout(url, timeout) {
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), timeout);
        
                    try {
                        let response = await fetch(url, { signal: controller.signal });
                        clearTimeout(timeoutId); // Clear timeout if response arrives
                    
                        if (!response.ok) {
                            throw new Error(`HTTP Error: ${response.status}`);
                        }
        
                        let data = await response.json();
                        return data;
                    } catch (error) {
                        if (error.name === "AbortError") {
                            throw new Error("Request timed out. Please try again.");
                        }
                        throw error;
                    }
                }
        
                try {
                    let url = `http://127.0.0.1:5000/summary/${vid_id}`;
                    let data = await fetchWithTimeout(url, timeoutDuration);
        
                    if (!data || !data.summary) {
                        throw new Error("No summary available for this video.");
                    }
        
                    console.log("Summary:", data.summary);
                    document.getElementById("output").textContent = data.summary;
                } catch (error) {
                    console.error("Error fetching summary:", error);
                    document.getElementById("output").textContent = error.message;
                }
            });
        

            //Transcript
            let intervalId; // To store the interval for updating the transcript

            document.getElementById("fetchTranscript").addEventListener("click", async () => {            
            
                try {
                    let response = await fetch(`http://127.0.0.1:5000/show_transcript/${vid_id}`);
                    let transcriptData = await response.json();
                    console.log("Transcript Data:", transcriptData);
            
                    if (!transcriptData.transcript) {
                        alert("Transcript not available.");
                        return;
                    }
            
                    let outputDiv = document.getElementById("output");
                    outputDiv.innerHTML = ""; // Clear previous transcript
            
                    // Create a container for transcript lines
                    transcriptData.transcript.forEach((segment, index) => {
                        let div = document.createElement("div");
                        div.classList.add("transcript-line");
                        div.dataset.index = index;
                        div.innerHTML = `[${segment.Start} - ${segment.End}] ${segment.Text}`;
                        outputDiv.appendChild(div);
                    });
            
                    // Function to continuously update the transcript based on video time
                    async function updateTranscript() {
                        chrome.scripting.executeScript({
                            target: { tabId: tabs[0].id },
                            function: getCurrentVideoTime
                        }, (injectionResults) => {
                            if (!injectionResults || !injectionResults[0].result) {
                                return;
                            }
            
                            let currentTime = injectionResults[0].result;
                            let currentSegment = findClosestSegment(transcriptData.transcript, currentTime);
                            highlightAndScrollTranscript(currentSegment);
                        });
                    }
            
                    // Start updating transcript every second
                    clearInterval(intervalId); // Clear any previous intervals
                    intervalId = setInterval(updateTranscript, 1000);
                } catch (error) {
                    console.error("Error fetching transcript:", error);
                }
            });
            
            // Highlight the current transcript line and auto-scroll
            function highlightAndScrollTranscript(currentSegment) {
                if (currentSegment === null) return;
            
                let transcriptLines = document.querySelectorAll(".transcript-line");
                
                transcriptLines.forEach((line, index) => {
                    if (index === currentSegment) {
                        line.style.color = "red";
                        line.style.fontWeight = "bold";
                        line.scrollIntoView({ behavior: "smooth", block: "center" });
                    } else {
                        line.style.color = "black";
                        line.style.fontWeight = "normal";
                    }
                });
            }
                     

            //Data
            document.getElementById("fetchData").addEventListener("click", async () => {
                try {
                    let response = await fetch("http://127.0.0.1:5000/show_data/"+vid_id);
                    let data = await response.json();
                    console.log("Transcript Data:", data);
                    document.getElementById("output").textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    console.error("Error fetching transcript:", error);
                }
            });


            //Audio handling
            document.getElementById("createAudio").addEventListener("click", () => {
                document.getElementById("languageForm").style.display = "block"; // Show input form
            });
            
            document.getElementById("submitLanguage").addEventListener("click", handleLanguageInput);
            document.getElementById("targetLanguage").addEventListener("keypress", (event) => {
                if (event.key === "Enter") {
                    handleLanguageInput();
                }
            });

            async function handleLanguageInput() {
                const targetLanguage = document.getElementById("targetLanguage").value.trim();
                
                if (!targetLanguage) {
                    document.getElementById("output").textContent = "Please enter a target language.";
                    return;
                }
            
                // Get current timestamp from YouTube
                let currentTime = await new Promise((resolve, reject) => {
                    chrome.scripting.executeScript({
                        target: { tabId: tabs[0].id },
                        function: getCurrentVideoTime
                    }, (results) => {
                        if (!results || !results[0] || results[0].result === null) {
                            console.error("Error: Failed to fetch current video time.");
                            reject("Failed to fetch current video time.");
                        } else {
                            resolve(results[0].result);
                        }
                    });
                });
            
                console.log("Current Video Time:", currentTime);
            
                try {
                    let response = await fetch(`http://127.0.0.1:5000/show_transcript/${vid_id}`);
                    let data = await response.json();
                    transcriptDataGlobal = data.transcript;
                } catch (error) {
                    console.error("Error fetching transcript data:", error);
                    document.getElementById("output").textContent = "Error fetching transcript data.";
                    return;
                }
            
            
                // Find the closest transcript segment
                let currentSegment = findClosestSegment(transcriptDataGlobal, currentTime);
                console.log("Closest Transcript Segment:", currentSegment);
            
                if (currentSegment === null) {
                    document.getElementById("output").textContent = "Could not determine the current segment.";
                    return;
                }
            
                // API URLs
                const createAudioUrl = `http://127.0.0.1:5000/create_audio/${vid_id}/${targetLanguage}`;
                const listenAudioUrl = `http://127.0.0.1:5000/listen_audio/${vid_id}/${currentSegment}`;
            
                try {
                    // Step 1: Request to create audio
                    document.getElementById("output").textContent = "Generating audio...";
                    let response = await fetch(createAudioUrl);
                    let data = await response.json();
            
                    if (data.error) {
                        document.getElementById("output").textContent = `Error: ${data.error}`;
                        return;
                    }
            
                    // Step 2: Poll until audio is ready
                    let audioReady = false;
                    for (let i = 0; i < 20; i++) { // Try for up to 40 seconds (20 * 2s)
                        await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds
            
                        let checkResponse = await fetch(createAudioUrl);
                        let checkData = await checkResponse.json();
            
                        if (checkData.message && checkData.message.includes("Audio already generated")) {
                            audioReady = true;
                            break;
                        }
                    }
            
                    if (!audioReady) {
                        document.getElementById("output").textContent = "Audio generation took too long.";
                        return;
                    }
            
                    // Step 3: Play audio
                    console.log("Playing audio from:", listenAudioUrl);
                    document.getElementById("output").textContent = "Playing audio...";
                    let audio = new Audio(listenAudioUrl);
                    audio.play();
                    document.getElementById("output").textContent = "Done";
            
                } catch (error) {
                    console.error("Error processing audio:", error);
                    document.getElementById("output").textContent = "An error occurred.";
                }
            }
            
      } else {
          document.getElementById("output").textContent = "No YouTube video detected.";
      }
  });
});
