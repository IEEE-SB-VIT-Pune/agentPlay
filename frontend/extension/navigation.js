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
          <div class="language-form" id="languageForm" style="margin-top: 15px; display: flex; flex-direction: column; gap: 10px;">
            <input type="text" id="targetLanguage" placeholder="Enter language code (es, fr, de...)" style="padding: 10px; width: 94% ; border-radius: 6px; border: 1px solid #ccc;">
            <div style="display: flex; gap: 10px;">
              <button class="extrabtn" id="submitLanguage" style="flex: 1;">Submit</button>
              <button class="extrabtn" id="stopAudio" style="flex: 1;">Stop</button>
            </div>
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
              <span>Get your answers</span>
          </button>
          <div class="chatbot" id="chatbot" style="display: none; margin-top: 15px; display: flex; flex-direction: column; gap: 10px;">
              <input type="text" id="query" placeholder="Ask your question" style="padding: 10px; width: 94%; border-radius: 6px; border: 1px solid #ccc;">
              <div class="toggle-container" style="display: flex; align-items: center; justify-content: space-between;">
                  <span>Addition Mode</span>
                  <label class="switch">
                      <input type="checkbox" id="toggleMode" checked>
                      <span class="slider round"></span>
                  </label>
              </div>
              <button class="extrabtn" id="submitquery">Submit</button>
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
