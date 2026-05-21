/**
 * Content Script — DOM observer + event capture
 * Runs on every page to capture user interactions,
 * DOM snapshots, and network calls.
 */

(function () {
  "use strict";

  // Avoid double injection
  if (window.__aiTestingAgentInjected) return;
  window.__aiTestingAgentInjected = true;

  let isRecording = false;
  let eventQueue = [];

  // ── Utility: generate a CSS selector for an element ──────────

  function getCSSSelector(el) {
    if (!el || el === document.body || el === document.documentElement) {
      return "body";
    }

    // Prefer ID
    if (el.id) {
      return `#${CSS.escape(el.id)}`;
    }

    // Prefer data-testid
    const testId = el.getAttribute("data-testid");
    if (testId) {
      return `[data-testid="${testId}"]`;
    }

    // Prefer name attribute for inputs
    const name = el.getAttribute("name");
    if (name && (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA")) {
      return `${el.tagName.toLowerCase()}[name="${name}"]`;
    }

    // Build a path
    const parts = [];
    let current = el;
    while (current && current !== document.body && current !== document.documentElement) {
      let selector = current.tagName.toLowerCase();

      if (current.id) {
        selector = `#${CSS.escape(current.id)}`;
        parts.unshift(selector);
        break;
      }

      // Add class info
      if (current.className && typeof current.className === "string") {
        const classes = current.className
          .trim()
          .split(/\s+/)
          .filter((c) => c.length > 0 && c.length < 40)
          .slice(0, 2);
        if (classes.length > 0) {
          selector += "." + classes.map((c) => CSS.escape(c)).join(".");
        }
      }

      // Add nth-child for disambiguation
      const parent = current.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(
          (s) => s.tagName === current.tagName
        );
        if (siblings.length > 1) {
          const index = siblings.indexOf(current) + 1;
          selector += `:nth-child(${index})`;
        }
      }

      parts.unshift(selector);
      current = current.parentElement;
    }

    return parts.join(" > ");
  }

  // ── Utility: get element metadata ────────────────────────────

  function getElementMeta(el) {
    if (!el) return {};
    return {
      tag: el.tagName ? el.tagName.toLowerCase() : null,
      type: el.getAttribute ? el.getAttribute("type") : null,
      name: el.getAttribute ? el.getAttribute("name") : null,
      placeholder: el.getAttribute ? el.getAttribute("placeholder") : null,
      text: el.textContent ? el.textContent.trim().substring(0, 100) : null,
      ariaLabel: el.getAttribute ? el.getAttribute("aria-label") : null,
    };
  }

  // ── Send event to background script ──────────────────────────

  function sendEvent(event) {
    if (!isRecording) return;
    eventQueue.push(event);

    // Also forward immediately to background
    try {
      chrome.runtime.sendMessage({
        type: "CAPTURED_EVENT",
        event: event,
      });
    } catch (e) {
      // Extension context might be invalidated
    }
  }

  // ── Click listener ───────────────────────────────────────────

  document.addEventListener(
    "click",
    function (e) {
      if (!isRecording) return;
      const target = e.target;
      sendEvent({
        event_type: "click",
        timestamp: Date.now() / 1000,
        url: window.location.href,
        selector: getCSSSelector(target),
        value: target.textContent ? target.textContent.trim().substring(0, 200) : null,
        meta: getElementMeta(target),
      });
    },
    true
  );

  // ── Input/Change listener ────────────────────────────────────

  document.addEventListener(
    "change",
    function (e) {
      if (!isRecording) return;
      const target = e.target;
      const isPassword = target.type === "password";
      sendEvent({
        event_type: "fill",
        timestamp: Date.now() / 1000,
        url: window.location.href,
        selector: getCSSSelector(target),
        value: isPassword ? "••••••••" : target.value,
        meta: getElementMeta(target),
      });
    },
    true
  );

  // ── Input event for real-time tracking ───────────────────────

  let inputDebounce = {};
  document.addEventListener(
    "input",
    function (e) {
      if (!isRecording) return;
      const target = e.target;
      const selector = getCSSSelector(target);

      // Debounce: only send after 500ms of no typing
      if (inputDebounce[selector]) {
        clearTimeout(inputDebounce[selector]);
      }
      inputDebounce[selector] = setTimeout(() => {
        const isPassword = target.type === "password";
        sendEvent({
          event_type: "input",
          timestamp: Date.now() / 1000,
          url: window.location.href,
          selector: selector,
          value: isPassword ? "••••••••" : target.value,
          meta: getElementMeta(target),
        });
        delete inputDebounce[selector];
      }, 500);
    },
    true
  );

  // ── Form submit listener ─────────────────────────────────────

  document.addEventListener(
    "submit",
    function (e) {
      if (!isRecording) return;
      const form = e.target;
      sendEvent({
        event_type: "submit",
        timestamp: Date.now() / 1000,
        url: window.location.href,
        selector: getCSSSelector(form),
        value: form.action || null,
        meta: { method: form.method || "GET", action: form.action || "" },
      });
    },
    true
  );

  // ── Navigation / page load snapshot ──────────────────────────

  function capturePageSnapshot() {
    if (!isRecording) return;
    sendEvent({
      event_type: "navigate",
      timestamp: Date.now() / 1000,
      url: window.location.href,
      selector: null,
      value: document.title,
      dom_snapshot: document.documentElement.outerHTML.substring(0, 50000),
      meta: { title: document.title },
    });

    // Request screenshot from background
    try {
      chrome.runtime.sendMessage({ type: "CAPTURE_SCREENSHOT" });
    } catch (e) {}
  }

  // Capture initial page load
  capturePageSnapshot();

  // ── Network interception — Fetch ─────────────────────────────

  const originalFetch = window.fetch;
  window.fetch = function (...args) {
    const startTime = Date.now();
    let url = "";
    let method = "GET";

    if (typeof args[0] === "string") {
      url = args[0];
    } else if (args[0] instanceof Request) {
      url = args[0].url;
      method = args[0].method || "GET";
    }
    if (args[1] && args[1].method) {
      method = args[1].method;
    }

    return originalFetch.apply(this, args).then(
      (response) => {
        if (isRecording) {
          sendEvent({
            event_type: "network",
            timestamp: Date.now() / 1000,
            url: window.location.href,
            selector: null,
            value: null,
            network_data: {
              method: method,
              url: url.substring(0, 500),
              status: response.status,
              statusText: response.statusText,
              duration_ms: Date.now() - startTime,
              type: "fetch",
            },
          });
        }
        return response;
      },
      (error) => {
        if (isRecording) {
          sendEvent({
            event_type: "network",
            timestamp: Date.now() / 1000,
            url: window.location.href,
            selector: null,
            value: null,
            network_data: {
              method: method,
              url: url.substring(0, 500),
              status: 0,
              statusText: "Network Error",
              duration_ms: Date.now() - startTime,
              type: "fetch",
              error: error.message,
            },
          });
        }
        throw error;
      }
    );
  };

  // ── Network interception — XMLHttpRequest ────────────────────

  const originalXHROpen = XMLHttpRequest.prototype.open;
  const originalXHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__aiMethod = method;
    this.__aiUrl = url;
    this.__aiStartTime = Date.now();
    return originalXHROpen.call(this, method, url, ...rest);
  };

  XMLHttpRequest.prototype.send = function (...args) {
    this.addEventListener("loadend", function () {
      if (isRecording) {
        sendEvent({
          event_type: "network",
          timestamp: Date.now() / 1000,
          url: window.location.href,
          selector: null,
          value: null,
          network_data: {
            method: this.__aiMethod || "?",
            url: (this.__aiUrl || "").toString().substring(0, 500),
            status: this.status,
            statusText: this.statusText,
            duration_ms: Date.now() - (this.__aiStartTime || Date.now()),
            type: "xhr",
          },
        });
      }
    });
    return originalXHRSend.apply(this, args);
  };

  // ── DOM Mutation Observer (significant changes only) ─────────

  let mutationTimer = null;
  const observer = new MutationObserver(function (mutations) {
    if (!isRecording) return;

    // Debounce: only report after 1s of no mutations
    if (mutationTimer) clearTimeout(mutationTimer);
    mutationTimer = setTimeout(() => {
      const significantChanges = mutations.filter(
        (m) =>
          m.type === "childList" &&
          (m.addedNodes.length > 0 || m.removedNodes.length > 0)
      );
      if (significantChanges.length > 3) {
        sendEvent({
          event_type: "dom_mutation",
          timestamp: Date.now() / 1000,
          url: window.location.href,
          selector: null,
          value: `${significantChanges.length} DOM changes detected`,
          meta: { mutations_count: significantChanges.length },
        });
      }
    }, 1000);
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  // ── Listen for messages from background ──────────────────────

  chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
    if (msg.type === "START_RECORDING") {
      isRecording = true;
      eventQueue = [];
      capturePageSnapshot();
      sendResponse({ status: "recording_started" });
    } else if (msg.type === "STOP_RECORDING") {
      isRecording = false;
      observer.disconnect();
      sendResponse({ status: "recording_stopped", events_count: eventQueue.length });
    } else if (msg.type === "GET_STATUS") {
      sendResponse({ isRecording: isRecording, events_count: eventQueue.length });
    }
    return true;
  });

  // ── URL change detection (SPA navigation) ────────────────────

  let lastUrl = window.location.href;
  const urlCheckInterval = setInterval(function () {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      capturePageSnapshot();
    }
  }, 500);

  console.log("[AI Testing Agent] Content script loaded");
})();
