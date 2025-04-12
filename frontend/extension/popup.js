// Add a RequestManager class to handle request locking
class RequestManager {
    constructor() {
      this.isRequestInProgress = false;
      this.pendingRequests = [];
    }
  
    async executeRequest(requestFn, description) {
      if (this.isRequestInProgress) {
        document.getElementById("output").textContent = `Please wait. A request is already in progress: ${description}`;
        return null;
      }
  
      try {
        this.isRequestInProgress = true;
        document.getElementById("output").textContent = `Processing: ${description}...`;
        
        // Execute the request function
        const result = await requestFn();
        return result;
      } catch (error) {
        console.error(`Error during request (${description}):`, error);
        document.getElementById("output").textContent = `Error: ${error.message}`;
        return null;
      } finally {
        this.isRequestInProgress = false;
      }
    }
  }
  
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
  
  // Create a shared request manager instance
  const requestManager = new RequestManager();
  
  // Helper function for fetch with timeout
  async function fetchWithTimeout(url, timeout, options = {}) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
  
      try {
          let response = await fetch(url, { 
              signal: controller.signal,
              ...options 
          });
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
  
  // Check if the current tab is a YouTube video
  document.addEventListener("DOMContentLoaded", () => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        let url = tabs[0].url;
        if (url.includes("youtube.com/watch?v=")) {
          document.getElementById("output").textContent = "YouTube Video Detected:\n" + url;
          console.log("YouTube Video URL:", url);
          let vid_id = getYouTubeVideoID(url);
          
          // Update UI elements to show request status
          function updateButtonState(button, isLoading) {
              button.disabled = isLoading;
              button.textContent = isLoading ? "Processing..." : button.dataset.originalText || button.textContent;
          }
          
          // Save original button text for all buttons
          document.querySelectorAll('button').forEach(btn => {
              btn.dataset.originalText = btn.textContent;
          });
  
          //Summary
          document.getElementById("fetchSummary").addEventListener("click", async () => {
              const timeoutDuration = 100000; // 100 seconds timeout
              const summaryBtn = document.getElementById("fetchSummary");
              
              await requestManager.executeRequest(async () => {
                  updateButtonState(summaryBtn, true);
                  try {
                      let url = `http://127.0.0.1:5000/concise_summary/${vid_id}`;
                      let data = await fetchWithTimeout(url, timeoutDuration);
                      
                      if (!data || !data.concise_summary) {
                          throw new Error("No summary available for this video.");
                      }
          
                      console.log("Summary:", data.concise_summary);
                      document.getElementById("output").textContent = data.concise_summary;
                      return data;
                  } catch (error) {
                      console.error("Error fetching summary:", error);
                      throw error;
                  } finally {
                      updateButtonState(summaryBtn, false);
                  }
              }, "Fetching video summary");
          });
  
          document.getElementById("fetchNotes").addEventListener("click", async () => {
              const timeoutDuration = 100000; // 100 seconds timeout
              const notesBtn = document.getElementById("fetchNotes");
              
              await requestManager.executeRequest(async () => {
                  updateButtonState(notesBtn, true);
                  try {
                      let url = `http://127.0.0.1:5000/notes/${vid_id}`;
                      let data = await fetchWithTimeout(url, timeoutDuration);
                      
                      if (!data || !data.notes) {
                          throw new Error("No notes available for this video.");
                      }
          
                      document.getElementById("output").textContent = data.notes;
                      return data;
                  } catch (error) {
                      console.error("Error fetching notes:", error);
                      throw error;
                  } finally {
                      updateButtonState(notesBtn, false);
                  }
              }, "Fetching video notes");
          });
          
          //Transcript
          let intervalId; // To store the interval for updating the transcript
  
          document.getElementById("fetchTranscript").addEventListener("click", async () => {            
              const transcriptBtn = document.getElementById("fetchTranscript");
              
              await requestManager.executeRequest(async () => {
                  updateButtonState(transcriptBtn, true);
                  try {
                      let response = await fetch(`http://127.0.0.1:5000/show_transcript/${vid_id}`);
                      let transcriptData = await response.json();
                      console.log("Transcript Data:", transcriptData);
              
                      if (!transcriptData.transcript) {
                          throw new Error("Transcript not available.");
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
                      
                      return transcriptData;
                  } catch (error) {
                      console.error("Error fetching transcript:", error);
                      throw error;
                  } finally {
                      updateButtonState(transcriptBtn, false);
                  }
              }, "Fetching video transcript");
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
                 
          
          //Process Query (chatbot)
          const queryInput = document.getElementById("query");
          const submitButton = document.getElementById("submitquery");
          const toggleMode = document.getElementById("toggleMode");
              
          // Submit query when button is clicked
          submitButton.addEventListener("click", async () => {
              const query = queryInput.value.trim();
              if (!query) {
                  alert("Please enter a question");
                  return;
              }
              
              await requestManager.executeRequest(async () => {
                  // Show loading state
                  updateButtonState(submitButton, true);
                  
                  try {
                      const response = await fetch("http://127.0.0.1:5000/process", {
                          method: "POST",
                          headers: {
                              "Content-Type": "application/json"
                          },
                          body: JSON.stringify({
                              query: query,
                              addition_mode: toggleMode.checked,
                              video_id: vid_id
                          })
                      });
                      
                      const data = await response.json();
                      
                      if (response.ok) {
                          // Display the answer
                          const answerElement = document.createElement("div");
                          answerElement.className = "answer";
                          answerElement.innerHTML = `
                              <h3>Answer:</h3>
                              <p>${data.final_answer}</p>
                              <div class="video-info">
                              <small>From: ${data.title} by ${data.channel}</small>
                              </div>
                          `;
                          
                          // Add the answer to the chatbot div
                          document.getElementById("chatbot").appendChild(answerElement);
                          
                          // Clear the input
                          queryInput.value = "";
                          return data;
                      } else {
                          throw new Error(data.error || "Unknown error occurred");
                      }
                  } catch (error) {
                      console.error("Error processing query:", error);
                      throw error;
                  } finally {
                      // Reset button state
                      updateButtonState(submitButton, false);
                  }
              }, "Processing your query");
          });
              
          // Allow submitting with Enter key
          queryInput.addEventListener("keypress", (event) => {
              if (event.key === "Enter") {
                  submitButton.click();
              }
          });
  
          //Data
          document.getElementById("fetchData").addEventListener("click", async () => {
              const dataBtn = document.getElementById("fetchData");
              
              await requestManager.executeRequest(async () => {
                  updateButtonState(dataBtn, true);
                  try {
                      console.log("Fetching data");
                      let response = await fetch(`http://127.0.0.1:5000/show_data/${vid_id}`);
                      let data = await response.json();
                      console.log("Data received:", data);
                      document.getElementById("output").textContent = JSON.stringify(data, null, 2);
                      return data;
                  } catch (error) {
                      console.error("Error fetching data:", error);
                      throw error;
                  } finally {
                      updateButtonState(dataBtn, false);
                  }
              }, "Fetching video data");
          });
  
  
          //Audio Handling
          let audio = null; // Store the audio object globally
          let stopPlayback = false; // Flag to stop playback
          let transcriptDataGlobal = null; // Store transcript data globally
  
          document.getElementById("createAudio").addEventListener("click", () => {
              const languageForm = document.getElementById("languageForm");
              const stopAudio = document.getElementById("stopAudio");
              // Toggle display of languageForm
              languageForm.style.display = (languageForm.style.display === "block") ? "none" : "block";
  
              // Toggle display of stopAudio
              stopAudio.style.display = (stopAudio.style.display === "block") ? "none" : "block";
          });
  
          document.getElementById("submitLanguage").addEventListener("click", handleLanguageInput);
          document.getElementById("targetLanguage").addEventListener("keypress", (event) => {
              if (event.key === "Enter") {
                  handleLanguageInput();
              }
          });
  
          document.getElementById("stopAudio").addEventListener("click", () => {
              stopPlayback = true;
              if (audio) {
                  audio.pause();
                  audio.currentTime = 0;
                  document.getElementById("output").textContent = "Audio playback stopped.";
              }
          });
  
          async function handleLanguageInput() {
              const targetLanguage = document.getElementById("targetLanguage").value.trim();
              const langBtn = document.getElementById("submitLanguage");
              
              if (!targetLanguage) {
                  document.getElementById("output").textContent = "Please enter a target language.";
                  return;
              }
              
              await requestManager.executeRequest(async () => {
                  updateButtonState(langBtn, true);
                  
                  try {
                      stopPlayback = false; // Reset stop flag
                      
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
  
                      let response = await fetch(`http://127.0.0.1:5000/show_transcript/${vid_id}`);
                      let data = await response.json();
                      transcriptDataGlobal = data.transcript;
                      
                      await playSegmentAudio(targetLanguage);
                      return data;
                  } catch (error) {
                      console.error("Error handling audio:", error);
                      throw error;
                  } finally {
                      updateButtonState(langBtn, false);
                  }
              }, "Processing audio translation");
          }
  
          async function playSegmentAudio(targetLanguage) {
              while (!stopPlayback && !requestManager.isRequestInProgress) {
                  let currentVideoTime = await new Promise((resolve, reject) => {
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
          
                  let currentSegmentIndex = findClosestSegment(transcriptDataGlobal, currentVideoTime);
          
                  if (currentSegmentIndex === null || currentSegmentIndex < 0 || currentSegmentIndex >= transcriptDataGlobal.length) {
                      document.getElementById("output").textContent = "Could not determine the current segment.";
                      return;
                  }
          
                  const listenAudioUrl = `http://127.0.0.1:5000/listen_audio/${vid_id}/${targetLanguage}/${currentSegmentIndex+1}`;
                  
                  console.log("Playing audio from:", listenAudioUrl);
                  document.getElementById("output").textContent = `Playing: ${transcriptDataGlobal[currentSegmentIndex].Text}...`;
          
                  // Create new audio object
                  audio = new Audio(listenAudioUrl);
                  audio.play();
          
                  // Wait for the audio to finish playing before fetching the next segment
                  await new Promise(resolve => {
                      audio.onended = resolve;
                      audio.onerror = () => {
                          console.error("Error playing audio");
                          resolve();
                      };
                  });
          
                  await new Promise(resolve => setTimeout(resolve, 500)); // Small delay before checking next segment
              }
          }
  
          //Show chatbot form and call precompute
          document.getElementById("chatbtn").addEventListener("click", async () => {
              document.getElementById("chatbot").style.display = (document.getElementById("chatbot").style.display==="block") ? "none":"block"; // Show input form
              document.getElementById("submitquery").style.display = (document.getElementById("submitquery").style.display === "block") ? "none":"block";
              
              const chatBtn = document.getElementById("chatbtn");
              
              await requestManager.executeRequest(async () => {
                  updateButtonState(chatBtn, true);
                  try {
                      // Call the precompute route with the video ID
                      const response = await fetch(`http://127.0.0.1:5000/precompute/${vid_id}`, {
                          method: 'GET'
                      });
                      
                      const data = await response.json();
                      
                      if (response.ok) {
                          console.log("Precompute successful:", data);
                          document.getElementById("output").textContent = "Precomputing complete!";
                      } else {
                          throw new Error("Failed to precompute video data.");
                      }
                      
                      return data;
                  } catch (error) {
                      console.error("Error calling precompute:", error);
                      throw error;
                  } finally {
                      updateButtonState(chatBtn, false);
                  }
              }, "Precomputing video data");
          });
  
        } else {
            document.getElementById("output").textContent = "No YouTube video detected.";
        }
    });
  });