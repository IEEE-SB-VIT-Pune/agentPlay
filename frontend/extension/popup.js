// popup.js

function getYouTubeVideoID(url) {
    let match = url.match(/v=([a-zA-Z0-9_-]{11})/);
    return match ? match[1] : null;
}

function convertTimeToSeconds(timeStr) {
    let parts = timeStr.split(":" ).map(Number);
    return parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + parts[2] : parts[0] * 60 + parts[1];
}

function getCurrentVideoTime() {
    let video = document.querySelector("video");
    return video ? Math.floor(video.currentTime) : null;
}

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

let tabs;
let vid_id;
let intervalId;
let transcriptDataGlobal;
let audio = null;
let stopPlayback = false;

function initializePopupLogic() {
    chrome.tabs.query({ active: true, currentWindow: true }, (queriedTabs) => {
        tabs = queriedTabs;
        let url = tabs[0].url;
        if (!url.includes("youtube.com/watch?v=")) {
            const output = document.getElementById("output");
            if (output) output.textContent = "No YouTube video detected.";
            return;
        }

        vid_id = getYouTubeVideoID(url);
        if (document.getElementById("output")) {
            document.getElementById("output").textContent = "YouTube Video Detected:\n" + url;
        }

        const safeBind = (id, handler) => {
            const btn = document.getElementById(id);
            if (btn) btn.addEventListener("click", handler);
        };

        safeBind("fetchSummary", async () => {
            await fetchWithOutput(`http://127.0.0.1:5000/concise_summary/${vid_id}`, "concise_summary");
        });

        safeBind("fetchNotes", async () => {
            await fetchWithOutput(`http://127.0.0.1:5000/notes/${vid_id}`, "notes");
        });

        safeBind("fetchTranscript", async () => {
            try {
                let response = await fetch(`http://127.0.0.1:5000/show_transcript/${vid_id}`);
                let transcriptData = await response.json();
                if (!transcriptData.transcript) {
                    alert("Transcript not available.");
                    return;
                }
                transcriptDataGlobal = transcriptData.transcript;
                let outputDiv = document.getElementById("output");
                outputDiv.innerHTML = "";
                transcriptData.transcript.forEach((segment, index) => {
                    let div = document.createElement("div");
                    div.classList.add("transcript-line");
                    div.dataset.index = index;
                    div.innerHTML = `[${segment.Start} - ${segment.End}] ${segment.Text}`;
                    outputDiv.appendChild(div);
                });
                clearInterval(intervalId);
                intervalId = setInterval(updateTranscript, 1000);
            } catch (error) {
                console.error("Transcript error:", error);
            }
        });

        safeBind("fetchData", async () => {
            try {
                let response = await fetch(`http://127.0.0.1:5000/show_data/${vid_id}`);
                let data = await response.json();
                document.getElementById("output").textContent = JSON.stringify(data, null, 2);
            } catch (error) {
                console.error("Data fetch error:", error);
            }
        });

        safeBind("createAudio", () => {
            const languageForm = document.getElementById("languageForm");
            const stopAudio = document.getElementById("stopAudio");
            if (languageForm) languageForm.style.display = (languageForm.style.display === "block") ? "none" : "block";
            if (stopAudio) stopAudio.style.display = (stopAudio.style.display === "block") ? "none" : "block";
        });

        safeBind("submitLanguage", handleLanguageInput);

        const langInput = document.getElementById("targetLanguage");
        if (langInput) {
            langInput.addEventListener("keypress", (event) => {
                if (event.key === "Enter") handleLanguageInput();
            });
        }

        const submitButton = document.getElementById("submitquery");
        const queryInput = document.getElementById("query");
        const toggleMode = document.getElementById("toggleMode");

        if (submitButton && queryInput) {
            submitButton.addEventListener("click", async () => {
                const query = queryInput.value.trim();
                if (!query) return alert("Please enter a question");

                submitButton.disabled = true;
                submitButton.textContent = "Processing...";

                try {
                    const response = await fetch("http://127.0.0.1:5000/process", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            query: query,
                            addition_mode: toggleMode?.checked,
                            video_id: vid_id
                        })
                    });

                    const data = await response.json();
                    if (response.ok) {
                        document.getElementById("output").innerHTML = `<h3>Answer:</h3>${data.final_answer}<div class="video-info"><small>From: ${data.title} by ${data.channel}</small></div>`;
                        queryInput.value = "";
                    } else alert(`Error: ${data.error || "Unknown error"}`);
                } catch (err) {
                    alert(`Network error: ${err.message}`);
                } finally {
                    submitButton.disabled = false;
                    submitButton.textContent = "Submit";
                }
            });

            queryInput.addEventListener("keypress", (e) => {
                if (e.key === "Enter") submitButton.click();
            });
        }

        safeBind("chatbtn", () => {
            const chat = document.getElementById("chatbot");
            const submitBtn = document.getElementById("submitquery");
            if (chat) chat.style.display = (chat.style.display === "block") ? "none" : "block";
            if (submitBtn) submitBtn.style.display = (submitBtn.style.display === "block") ? "none" : "block";

            fetch(`http://127.0.0.1:5000/precompute/${vid_id}`)
                .then(res => res.json())
                .then(data => {
                    document.getElementById("output").textContent += "\nPrecomputing complete!";
                })
                .catch(err => {
                    console.error("Precompute error:", err);
                    document.getElementById("output").textContent += "\nError: Could not connect to server.";
                });
        });
    });
}

async function fetchWithOutput(url, field) {
    const timeoutDuration = 100000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutDuration);

    try {
        let response = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
        let data = await response.json();
        if (!data || !data[field]) throw new Error(`No ${field} available for this video.`);
        document.getElementById("output").textContent = data[field];
    } catch (error) {
        console.error("Fetch error:", error);
        document.getElementById("output").textContent = error.message;
    }
}

async function updateTranscript() {
    chrome.scripting.executeScript({
        target: { tabId: tabs[0].id },
        function: getCurrentVideoTime
    }, (results) => {
        if (!results || !results[0] || results[0].result === null) return;
        let currentSegment = findClosestSegment(transcriptDataGlobal, results[0].result);
        highlightAndScrollTranscript(currentSegment);
    });
}

async function highlightAndScrollTranscript(currentSegment) {
    if (currentSegment === null) return;
    
    // Add a short delay to ensure DOM is ready
    setTimeout(() => {
        let lines = document.querySelectorAll(".transcript-line");
        if (lines.length === 0) {
            console.error("No transcript lines found in the DOM");
            return;
        }
        
        lines.forEach((line, index) => {
            line.style.color = index === currentSegment ? "red" : "black";
            line.style.fontWeight = index === currentSegment ? "bold" : "normal";
        });
        
        // Scroll the element into view
        if (currentSegment >= 0 && currentSegment < lines.length) {
            try {
                lines[currentSegment].scrollIntoView({ behavior: "smooth", block: "center" });
            } catch (e) {
                console.error("Error scrolling to element:", e);
            }
        }
    }, 100); // Small delay to ensure rendering
}

async function handleLanguageInput() {
    const targetLang = document.getElementById("targetLanguage").value.trim();
    if (!targetLang) {
        document.getElementById("output").textContent = "Please enter a target language.";
        return;
    }
    
    document.getElementById("output").textContent = "Processing request...";
    stopPlayback = false;
    
    try {
        // Verify transcript data
        if (!transcriptDataGlobal) {
            document.getElementById("output").textContent = "Fetching transcript...";
            console.log(`Fetching transcript for video ID: ${vid_id}`);
            
            let response = await fetch(`http://127.0.0.1:5000/show_transcript/${vid_id}`);
            let data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            if (!data.transcript || data.transcript.length === 0) {
                throw new Error("No transcript data available");
            }
            
            transcriptDataGlobal = data.transcript;
            console.log("Transcript fetched successfully:", transcriptDataGlobal.length, "segments");
        }
        
        // Now play the audio
        document.getElementById("output").textContent = `Starting playback in ${targetLang}...`;
        await playSegmentAudio(targetLang);
    } catch (err) {
        console.error("Language input error:", err);
        document.getElementById("output").textContent = `Error: ${err.message || "Failed to process audio"}`;
    }
}

async function playSegmentAudio(targetLang) {
    try {
        while (!stopPlayback) {
            // Define the function to be injected into the page
            function getVideoTimeFromPage() {
                const video = document.querySelector("video");
                return video ? Math.floor(video.currentTime) : null;
            }
            
            // Get current video time with proper error handling
            console.log("Getting current video time...");
            let currentTime;
            try {
                const results = await chrome.scripting.executeScript({
                    target: { tabId: tabs[0].id },
                    func: getVideoTimeFromPage
                });
                
                if (results && results[0] && results[0].result !== null) {
                    currentTime = results[0].result;
                    console.log("Current video time:", currentTime);
                } else {
                    throw new Error("Could not get video time");
                }
            } catch (scriptError) {
                console.error("Script execution error:", scriptError);
                document.getElementById("output").textContent = "Error: Could not access video player. Make sure you're on a YouTube video page.";
                return;
            }

            // Find segment
            let segmentIdx = findClosestSegment(transcriptDataGlobal, currentTime);
            console.log("Closest segment index:", segmentIdx);
            
            if (segmentIdx === null) {
                console.error("No matching segment found for current time");
                document.getElementById("output").textContent = "No matching segment found for current time";
                return;
            }

            // Construct URL and play
            const listenUrl = `http://127.0.0.1:5000/listen_audio/${vid_id}/${targetLang}/${segmentIdx + 1}`;
            console.log("Fetching audio from:", listenUrl);
            
            document.getElementById("output").textContent = `Playing: ${transcriptDataGlobal[segmentIdx].Text}...`;
            
            // Create and play audio
            audio = new Audio(listenUrl);
            
            try {
                await audio.play();
                console.log("Playing audio...");
                
                // Wait for audio to finish
                await new Promise(resolve => {
                    audio.onended = () => {
                        console.log("Audio playback ended");
                        resolve();
                    };
                    audio.onerror = () => {
                        console.error("Audio playback error");
                        resolve();
                    };
                });
            } catch (audioError) {
                console.error("Audio playback failed:", audioError);
            }

            // Small delay between segments
            console.log("Waiting before next segment...");
            await new Promise(res => setTimeout(res, 500));
        }
    } catch (error) {
        console.error("Playback error:", error);
        document.getElementById("output").textContent = `Playback error: ${error.message}`;
    }
}

document.addEventListener("DOMContentLoaded", initializePopupLogic);
