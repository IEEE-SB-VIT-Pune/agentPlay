let lastUrl = location.href;
let isPanelOpen = false;

const addSliderIcon = () => {
  if (document.getElementById("slider-icon")) return;

  const icon = document.createElement("div");
  icon.id = "slider-icon";
  icon.title = "Open AgentPlay Panel";

  // Create image element
  const iconImg = document.createElement("img");
  iconImg.src = chrome.runtime.getURL("icon.png");
  iconImg.style.width = "100%";
  iconImg.style.height = "100%";
  
  icon.appendChild(iconImg);

  icon.addEventListener("click", () => {
    if (document.getElementById("slider-frame")) {
      // Panel is open, close it
      document.getElementById("slider-frame").remove();
      isPanelOpen = false;
    } else {
      // Panel is closed, open it
      const iframe = document.createElement("iframe");
      iframe.id = "slider-frame";
      iframe.src = chrome.runtime.getURL("sidebar.html");
      document.body.appendChild(iframe);
      isPanelOpen = true;
    }
  });

  document.body.appendChild(icon);
};

const removeSliderUI = () => {
  const icon = document.getElementById("slider-icon");
  const frame = document.getElementById("slider-frame");
  if (icon) icon.remove();
  if (frame) frame.remove();
  isPanelOpen = false;
};

const observer = new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    removeSliderUI();

    if (location.href.includes("watch?v=")) {
      setTimeout(addSliderIcon, 1000);
    }
  }
});

observer.observe(document.body, { childList: true, subtree: true });

// Add icon when video page loads initially
if (location.href.includes("watch?v=")) {
  setTimeout(addSliderIcon, 1000);
}

// Add keyboard shortcut to toggle panel
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === ';') {
    e.preventDefault();
    const icon = document.getElementById("slider-icon");
    if (icon) icon.click();
  }
});