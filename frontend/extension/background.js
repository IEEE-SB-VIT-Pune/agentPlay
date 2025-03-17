chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.channelId) {
        console.log("Received Channel ID:", message.channelId);
        // Optionally send to backend
        fetch('http://localhost:8000/api/channel-id', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channelId: message.channelId })
        }).then(response => response.json())
          .then(data => console.log(data));
    }
});
