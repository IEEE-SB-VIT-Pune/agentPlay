// let mediaRecorder;
// let audioStream;

// chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
//     if (message.action === "start_transcription") {
//       try {
//         audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
//         mediaRecorder = new MediaRecorder(audioStream);
//         let audioChunks = [];
  
//         mediaRecorder.ondataavailable = (event) => {
//           audioChunks.push(event.data);
//           if (mediaRecorder.state === "inactive") {
//             processAudioChunks(audioChunks);
//           }
//         };
//         mediaRecorder.start();
//         sendResponse({ success: true });
//       } catch (error) {
//         console.error("Error starting transcription:", error);
//         sendResponse({ error: error.message });
//       }
//     } else if (message.action === "stop_transcription") {
//       if (mediaRecorder && mediaRecorder.state !== "inactive") {
//         mediaRecorder.stop();
//         audioStream.getTracks().forEach((track) => track.stop());
//       }
//     }
//   });