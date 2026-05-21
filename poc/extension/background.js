/**
 * Background Service Worker — MV3
 * Manages recording state, batches events, captures screenshots,
 * and POSTs to the backend API.
 */

const BACKEND_URL = "http://localhost:8000";
const BATCH_INTERVAL_MS = 2000;

let isRecording = false;
let sessionId = null;
let recordingTabId = null;
let eventBuffer = [];
let batchTimer = null;
let eventCount = 0;

// ── Session ID generation ──────────────────────────────────────

function generateSessionId() {
  try {
    return crypto.randomUUID();
  } catch {
    return "s-" + Date.now() + "-" + Math.random().toString(36).substring(2, 10);
  }
}

// ── Start recording ────────────────────────────────────────────

async function startRecording() {
  sessionId = generateSessionId();
  isRecording = true;
  eventBuffer = [];
  eventCount = 0;

  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  recordingTabId = tabs[0] ? tabs[0].id : null;

  // Save state
  await chrome.storage.local.set({
    isRecording: true,
    sessionId: sessionId,
    recordingTabId: recordingTabId,
    eventCount: 0,
  });

  // Notify content script in active tab
  if (tabs[0]) {
    try {
      await chrome.tabs.sendMessage(tabs[0].id, { type: "START_RECORDING" });
    } catch (e) {
      // Content script may not be loaded yet; inject it
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tabs[0].id },
          files: ["content.js"],
        });
        await chrome.tabs.sendMessage(tabs[0].id, { type: "START_RECORDING" });
      } catch (e2) {
        console.error("Failed to inject content script:", e2);
      }
    }
  }

  // Start batch timer
  batchTimer = setInterval(flushEvents, BATCH_INTERVAL_MS);

  console.log(`[AI Testing Agent] Recording started: ${sessionId}`);
}

// ── Stop recording ─────────────────────────────────────────────

async function stopRecording() {
  isRecording = false;

  // Notify content script
  if (recordingTabId !== null) {
    try {
      await chrome.tabs.sendMessage(recordingTabId, { type: "STOP_RECORDING" });
    } catch (e) {}
  }

  // Flush remaining events
  await flushEvents();

  // Stop batch timer
  if (batchTimer) {
    clearInterval(batchTimer);
    batchTimer = null;
  }

  // Mark session as completed on backend
  if (sessionId) {
    try {
      await fetch(`${BACKEND_URL}/api/sessions/${sessionId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
    } catch (e) {
      console.error("Failed to complete session:", e);
    }
  }

  // Save state
  await chrome.storage.local.set({
    isRecording: false,
    lastSessionId: sessionId,
    recordingTabId: null,
    eventCount: eventCount,
  });

  console.log(`[AI Testing Agent] Recording stopped: ${sessionId}, ${eventCount} events`);
  sessionId = null;
  recordingTabId = null;
}

// ── Flush event buffer to backend ──────────────────────────────

async function flushEvents() {
  if (eventBuffer.length === 0 || !sessionId) return;

  const eventsToSend = [...eventBuffer];
  eventBuffer = [];

  try {
    const response = await fetch(`${BACKEND_URL}/api/session/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        events: eventsToSend,
      }),
    });

    if (!response.ok) {
      console.error(`Backend returned ${response.status}`);
      // Put events back in buffer on failure
      eventBuffer = eventsToSend.concat(eventBuffer);
    } else {
      const data = await response.json();
      console.log(`[AI Testing Agent] Sent ${data.events_saved} events`);
    }
  } catch (e) {
    console.error("[AI Testing Agent] Failed to send events:", e);
    // Put events back in buffer on failure
    eventBuffer = eventsToSend.concat(eventBuffer);
  }
}

// ── Screenshot capture ─────────────────────────────────────────

async function captureScreenshot() {
  if (!isRecording || !sessionId) return;

  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs[0]) return;

    const dataUrl = await chrome.tabs.captureVisibleTab(null, {
      format: "png",
      quality: 80,
    });

    // Extract base64 data (remove "data:image/png;base64," prefix)
    const b64 = dataUrl.split(",")[1];

    eventBuffer.push({
      event_type: "screenshot",
      timestamp: Date.now() / 1000,
      url: tabs[0].url,
      selector: null,
      value: null,
      screenshot_b64: b64,
      meta: { tab_title: tabs[0].title },
    });
  } catch (e) {
    console.error("[AI Testing Agent] Screenshot capture failed:", e);
  }
}

// ── Message handler ────────────────────────────────────────────

chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
  if (msg.type === "START_RECORDING_CMD") {
    startRecording().then(() => {
      sendResponse({ status: "ok", sessionId: sessionId });
    });
    return true; // async response
  }

  if (msg.type === "STOP_RECORDING_CMD") {
    stopRecording().then(() => {
      sendResponse({ status: "ok" });
    });
    return true;
  }

  if (msg.type === "GET_STATE") {
    chrome.storage.local.get(
      ["isRecording", "sessionId", "recordingTabId", "eventCount", "lastSessionId"],
      (data) => {
        const isRecordingTab =
          !sender.tab ||
          data.recordingTabId === null ||
          data.recordingTabId === undefined ||
          sender.tab.id === data.recordingTabId;
        sendResponse({
          isRecording: (data.isRecording || false) && isRecordingTab,
          sessionId: data.sessionId || null,
          eventCount: data.eventCount || eventCount,
          lastSessionId: data.lastSessionId || null,
        });
      }
    );
    return true;
  }

  if (msg.type === "CAPTURED_EVENT") {
    if (isRecording && sessionId) {
      eventBuffer.push(msg.event);
      eventCount++;
      // Update count in storage for popup
      chrome.storage.local.set({ eventCount: eventCount });
    }
    sendResponse({ status: "ok" });
    return true;
  }

  if (msg.type === "CAPTURE_SCREENSHOT") {
    captureScreenshot();
    sendResponse({ status: "ok" });
    return true;
  }
});

// ── Tab navigation listener (capture screenshot on nav) ────────

chrome.tabs.onUpdated.addListener(function (tabId, changeInfo, tab) {
  if (!isRecording) return;
  if (recordingTabId !== null && tabId !== recordingTabId) return;
  if (changeInfo.status === "complete") {
    captureScreenshot();
  }
});

// ── Restore state on service worker restart ────────────────────

chrome.storage.local.get(["isRecording", "sessionId", "recordingTabId"], (data) => {
  if (data.isRecording && data.sessionId) {
    isRecording = true;
    sessionId = data.sessionId;
    recordingTabId = data.recordingTabId ?? null;
    batchTimer = setInterval(flushEvents, BATCH_INTERVAL_MS);
    console.log(`[AI Testing Agent] Restored recording: ${sessionId}`);
  }
});

console.log("[AI Testing Agent] Background service worker loaded");
