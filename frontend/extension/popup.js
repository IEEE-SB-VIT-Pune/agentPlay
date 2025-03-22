function getYouTubeVideoID(url) {
  let match = url.match(/v=([a-zA-Z0-9_-]{11})/);
  return match ? match[1] : null;
}
function formatTranscript(data) {
  if (!data || !data.transcript) {
      return "Invalid transcript data";
  }

  return data.transcript.map(segment => {
      return `[${segment.Start} - ${segment.End}] ${segment.Text}`;
  }).join("\n");
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
          document.getElementById("fetchTranscript").addEventListener("click", async () => {
            try {
                let response = await fetch("http://127.0.0.1:5000/show_transcript/"+vid_id);
                let data = await response.json();
                console.log("Transcript Data:", data);
                document.getElementById("output").textContent = formatTranscript(data);
            } catch (error) {
                console.error("Error fetching transcript:", error);
            }
          });

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
      } else {
          document.getElementById("output").textContent = "No YouTube video detected.";
      }
  });
});
