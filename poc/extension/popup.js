/**
 * Popup Script — controls recording state and updates UI.
 */

document.addEventListener("DOMContentLoaded", function () {
  const recordBtn = document.getElementById("recordBtn");
  const recordBtnText = document.getElementById("recordBtnText");
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const eventCountEl = document.getElementById("eventCount");
  const sessionIdEl = document.getElementById("sessionId");
  const sessionRow = document.getElementById("sessionRow");
  const statusCard = document.querySelector(".status-card");

  let isRecording = false;
  let pollTimer = null;

  // ── Load current state ───────────────────────────────────────

  function loadState() {
    chrome.runtime.sendMessage({ type: "GET_STATE" }, function (response) {
      if (chrome.runtime.lastError) {
        console.error("Error getting state:", chrome.runtime.lastError);
        return;
      }
      if (response) {
        isRecording = response.isRecording;
        updateUI(response);
      }
    });
  }

  // ── Update UI based on state ─────────────────────────────────

  function updateUI(state) {
    if (state.isRecording) {
      recordBtn.className = "record-btn stop";
      recordBtnText.textContent = "Stop Recording";
      statusDot.className = "status-dot recording";
      statusText.textContent = "Recording";
      sessionRow.style.display = "flex";
      sessionIdEl.textContent = state.sessionId
        ? state.sessionId.substring(0, 12) + "..."
        : "—";
    } else {
      recordBtn.className = "record-btn start";
      recordBtnText.textContent = "Start Recording";
      statusDot.className = "status-dot idle";
      statusText.textContent = "Idle";
      sessionRow.style.display = "none";
    }

    eventCountEl.textContent = state.eventCount || 0;
  }

  function showError(message) {
    let errorEl = document.getElementById("errorText");
    if (!errorEl) {
      errorEl = document.createElement("div");
      errorEl.id = "errorText";
      errorEl.style.cssText = "margin-top:10px;color:#fecaca;background:#7f1d1d;padding:8px;border-radius:8px;font-size:11px;line-height:1.4;";
      statusCard.appendChild(errorEl);
    }
    errorEl.textContent = message;
  }

  // ── Button click handler ─────────────────────────────────────

  recordBtn.addEventListener("click", function () {
    recordBtn.disabled = true;
    recordBtn.style.opacity = "0.7";

    if (isRecording) {
      // Stop recording
      chrome.runtime.sendMessage(
        { type: "STOP_RECORDING_CMD" },
        function (response) {
          recordBtn.disabled = false;
          recordBtn.style.opacity = "1";
          isRecording = false;
          loadState();
          stopPolling();
        }
      );
    } else {
      // Start recording
      chrome.runtime.sendMessage(
        { type: "START_RECORDING_CMD" },
        function (response) {
          recordBtn.disabled = false;
          recordBtn.style.opacity = "1";
          if (!response || response.status === "error") {
            showError(response && response.error ? response.error : "Unable to start recording.");
            return;
          }
          isRecording = true;
          loadState();
          startPolling();
        }
      );
    }
  });

  // ── Poll for event count updates ─────────────────────────────

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(function () {
      chrome.storage.local.get(["eventCount"], function (data) {
        if (data.eventCount !== undefined) {
          eventCountEl.textContent = data.eventCount;
        }
      });
    }, 1000);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // ── Initialize ───────────────────────────────────────────────

  loadState();

  // Start polling if already recording
  chrome.storage.local.get(["isRecording"], function (data) {
    if (data.isRecording) {
      startPolling();
    }
  });
});
