fetch('http://localhost:8000/api/channel-id', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channelId })
  });


  