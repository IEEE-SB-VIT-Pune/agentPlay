// navigation.js

document.addEventListener("DOMContentLoaded", () => {
  const navItems = document.querySelectorAll(".nav-item");
  const featureView = document.getElementById("feature-view");

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      navItems.forEach(nav => nav.classList.remove("active"));
      item.classList.add("active");

      const feature = item.getAttribute("data-feature");
      loadFeatureContent(feature);
    });
  });

  function loadFeatureContent(feature) {
    switch (feature) {
      case "summary":
        featureView.innerHTML = `
          <div class="status-bar" id="status">
              <span class="status-icon"></span>
              <span class="status-text">Checking video...</span>
          </div>
          <button class="action-btn" id="fetchSummary">
              <span class="icon">📝</span>
              <span>Get Summary</span>
          </button>
          <div class="output-container"><pre id="output"></pre></div>
        `;
        break;

      case "notes":
        featureView.innerHTML = `
          <button class="action-btn" id="fetchNotes">
              <span class="icon">📝</span>
              <span>Get Notes</span>
          </button>
          <div class="output-container"><pre id="output"></pre></div>
        `;
        break;

      case "translation":
        featureView.innerHTML = `
          <button class="action-btn" id="createAudio">
              <span class="icon">🔊</span>
              <span>Translate Audio</span>
          </button>
          <div class="language-form" id="languageForm" style="margin-top: 10px;">
            <input type="text" id="targetLanguage" placeholder="Enter language code (es, fr, de...)" style="padding: 8px; width: 100%; border-radius: 5px; border: 1px solid #ccc; margin-bottom: 8px;">
            <button class="submit-btn" id="submitLanguage">Submit</button>
            <button class="submit-btn" id="stopAudio">Stop</button>
          </div>
          <div class="output-container"><pre id="output"></pre></div>
        `;
        break;

      case "transcript":
        featureView.innerHTML = `
          <button class="action-btn" id="fetchTranscript">
              <span class="icon">📋</span>
              <span>Get Transcript</span>
          </button>
          <div class="output-container"><pre id="output"></pre></div>
        `;
        break;

      case "qa":
        featureView.innerHTML = `
          <button class="action-btn" id="chatbtn">
              <span class="icon">🤖</span>
              <span>Chatbot</span>
          </button>
          <div class="chatbot" id="chatbot" style="display: none; margin-top: 10px;">
              <input type="text" id="query" placeholder="Ask your question" style="padding: 8px; width: 100%; border-radius: 5px; border: 1px solid #ccc; margin-bottom: 8px;">
              <div class="toggle-container" style="margin-bottom: 10px;">
                  <span>Addition Mode</span>
                  <label class="switch">
                      <input type="checkbox" id="toggleMode" checked>
                      <span class="slider round"></span>
                  </label>
              </div>
              <button class="submit-btn" id="submitquery">Submit</button>
          </div>
          <div class="output-container"><pre id="output"></pre></div>
        `;
        break;

      default:
        featureView.innerHTML = `<p>Feature not found.</p>`;
        break;
    }

    if (typeof initializePopupLogic === 'function') {
      initializePopupLogic();
    }
  }
});
