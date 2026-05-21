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
  let hoverTimer = null;
  let lastHoverSelector = null;
  let lastScreenshotAt = 0;
  const INPUT_DEBOUNCE_MS = 700;
  const SCREENSHOT_THROTTLE_MS = 750;

  function beginRecording(resetQueue) {
    const wasRecording = isRecording;
    isRecording = true;
    if (resetQueue) {
      eventQueue = [];
    }
    if (!wasRecording) {
      capturePageSnapshot();
    }
  }

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

  function trimText(value, limit) {
    if (!value) return null;
    const text = value.replace(/\s+/g, " ").trim();
    return text ? text.substring(0, limit) : null;
  }

  function escapeAttributeValue(value) {
    return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }

  function getActionElement(el) {
    if (!el || !el.closest) return el;
    return (
      el.closest(
        "button, a[href], summary, label, input[type='button'], input[type='submit'], " +
          "[role='button'], [role='link'], [role='menuitem'], [role='tab'], " +
          "[aria-haspopup], [data-testid]"
      ) || el
    );
  }

  function getHoverElement(el) {
    if (!el || !el.closest) return getActionElement(el);
    return (
      el.closest(
        "[aria-haspopup], [data-toggle], [data-bs-toggle], [class*='dropdown'], " +
          "[class*='menu'], [class*='trigger'], [id*='dropdown'], [id*='menu'], [id*='trigger']"
      ) || getActionElement(el)
    );
  }

  function getLabelText(el) {
    if (!el || !el.getAttribute) return null;
    if (el.labels && el.labels.length > 0) {
      return trimText(Array.from(el.labels).map((label) => label.innerText).join(" "), 120);
    }

    const labelledBy = el.getAttribute("aria-labelledby");
    if (labelledBy) {
      const text = labelledBy
        .split(/\s+/)
        .map((id) => document.getElementById(id))
        .filter(Boolean)
        .map((node) => node.innerText || node.textContent || "")
        .join(" ");
      if (text) return trimText(text, 120);
    }

    const parentLabel = el.closest("label");
    return parentLabel ? trimText(parentLabel.innerText, 120) : null;
  }

  function getElementRole(el) {
    if (!el || !el.getAttribute) return null;
    const explicitRole = el.getAttribute("role");
    if (explicitRole) return explicitRole;

    const tag = (el.tagName || "").toLowerCase();
    const inputType = (el.getAttribute("type") || "text").toLowerCase();
    if (tag === "button") return "button";
    if (tag === "a" && el.getAttribute("href")) return "link";
    if (tag === "textarea") return "textbox";
    if (tag === "select") return "combobox";
    if (tag === "input" && ["button", "reset", "submit"].includes(inputType)) {
      return "button";
    }
    if (tag === "input" && ["checkbox", "radio"].includes(inputType)) {
      return inputType;
    }
    if (tag === "input") return "textbox";
    return null;
  }

  function getAccessibleName(el, label) {
    if (!el || !el.getAttribute) return null;
    return (
      trimText(el.getAttribute("aria-label"), 120) ||
      label ||
      trimText(el.getAttribute("alt"), 120) ||
      trimText(el.getAttribute("title"), 120) ||
      trimText(el.getAttribute("placeholder"), 120) ||
      trimText(el.textContent || "", 120)
    );
  }

  function getSelectorCandidates(el) {
    if (!el || !el.getAttribute) return [];
    const selectors = [];
    const tag = (el.tagName || "").toLowerCase();
    const id = el.getAttribute("id");
    const testId = el.getAttribute("data-testid");
    const name = el.getAttribute("name");
    const ariaLabel = el.getAttribute("aria-label");

    if (id) selectors.push(`#${CSS.escape(id)}`);
    if (testId) selectors.push(`[data-testid="${escapeAttributeValue(testId)}"]`);
    if (name && ["input", "select", "textarea"].includes(tag)) {
      selectors.push(`${tag}[name="${escapeAttributeValue(name)}"]`);
    }
    if (ariaLabel) selectors.push(`[aria-label="${escapeAttributeValue(ariaLabel)}"]`);
    selectors.push(getCSSSelector(el));
    return Array.from(new Set(selectors)).slice(0, 5);
  }

  function getElementMeta(el) {
    if (!el) return {};
    const label = getLabelText(el);
    return {
      tag: el.tagName ? el.tagName.toLowerCase() : null,
      type: el.getAttribute ? el.getAttribute("type") : null,
      name: el.getAttribute ? el.getAttribute("name") : null,
      placeholder: el.getAttribute ? el.getAttribute("placeholder") : null,
      text: trimText(el.textContent || "", 100),
      ariaLabel: el.getAttribute ? el.getAttribute("aria-label") : null,
      accessibleName: getAccessibleName(el, label),
      dataTestId: el.getAttribute ? el.getAttribute("data-testid") : null,
      href: el.getAttribute ? el.getAttribute("href") : null,
      label: label,
      role: getElementRole(el),
      selectors: getSelectorCandidates(el),
    };
  }

  function isSensitiveInput(el) {
    if (!el || !el.getAttribute) return false;
    const fieldHints = [
      el.getAttribute("type"),
      el.getAttribute("name"),
      el.getAttribute("id"),
      el.getAttribute("autocomplete"),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return fieldHints.includes("password");
  }

  function recordedInputValue(el) {
    return isSensitiveInput(el) ? `{{secret:${getSecretKey(el)}}}` : el.value;
  }

  function getSecretKey(el) {
    const hint = [
      el.getAttribute("autocomplete"),
      el.getAttribute("name"),
      el.getAttribute("id"),
      "password",
    ].find(Boolean);
    return String(hint || "password")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "password";
  }

  function isTextEntryControl(el) {
    if (!el || !el.tagName) return false;
    const tag = el.tagName.toLowerCase();
    if (tag === "textarea") return true;
    if (tag !== "input") return false;
    const inputType = (el.getAttribute("type") || "text").toLowerCase();
    return !["button", "checkbox", "file", "radio", "reset", "submit"].includes(inputType);
  }

  function isRecordableFormControl(el) {
    if (!el || !el.tagName || el.disabled) return false;
    const tag = el.tagName.toLowerCase();
    if (tag === "select" || tag === "textarea") return Boolean(el.value);
    if (tag !== "input") return false;

    const inputType = (el.getAttribute("type") || "text").toLowerCase();
    if (["button", "checkbox", "file", "hidden", "radio", "reset", "submit"].includes(inputType)) {
      return false;
    }
    return Boolean(el.value);
  }

  function recordFormState(form) {
    if (!form || !form.querySelectorAll) return;
    form.querySelectorAll("input, select, textarea").forEach(function (control) {
      if (!isRecordableFormControl(control)) return;
      sendEvent({
        event_type: control.tagName === "SELECT" ? "select" : "fill",
        timestamp: Date.now() / 1000,
        url: window.location.href,
        selector: getCSSSelector(control),
        value: recordedInputValue(control),
        meta: {
          ...getElementMeta(control),
          fromFormState: true,
          sensitive: isSensitiveInput(control),
        },
      });
    });
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

  function requestScreenshot(delayMs) {
    const capture = function () {
      if (!isRecording || Date.now() - lastScreenshotAt < SCREENSHOT_THROTTLE_MS) {
        return;
      }
      lastScreenshotAt = Date.now();
      try {
        chrome.runtime.sendMessage({ type: "CAPTURE_SCREENSHOT" });
      } catch (e) {}
    };

    if (delayMs) {
      setTimeout(capture, delayMs);
    } else {
      capture();
    }
  }

  // ── Click listener ───────────────────────────────────────────

  document.addEventListener(
    "click",
    function (e) {
      if (!isRecording) return;
      const target = getActionElement(e.target);
      if (hoverTimer) clearTimeout(hoverTimer);
      sendEvent({
        event_type: "click",
        timestamp: Date.now() / 1000,
        url: window.location.href,
        selector: getCSSSelector(target),
        value: trimText(target.textContent || "", 200),
        meta: getElementMeta(target),
      });
      requestScreenshot(250);
    },
    true
  );

  function isLikelyHoverTrigger(el) {
    if (!el || !el.getAttribute) return false;
    if (el.getAttribute("aria-haspopup")) return true;
    if (el.getAttribute("data-toggle") || el.getAttribute("data-bs-toggle")) return true;

    const hints = [
      el.getAttribute("id"),
      el.getAttribute("class"),
      el.getAttribute("role"),
      el.getAttribute("data-state"),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return /(dropdown|flyout|menu|nav|panel|popover|submenu|tab|trigger)/.test(hints);
  }

  document.addEventListener(
    "pointerover",
    function (e) {
      if (!isRecording) return;
      const target = getHoverElement(e.target);
      if (!isLikelyHoverTrigger(target)) return;

      const selector = getCSSSelector(target);
      if (!selector || selector === lastHoverSelector) return;
      if (hoverTimer) clearTimeout(hoverTimer);
      hoverTimer = setTimeout(function () {
        if (!target.isConnected || !target.matches(":hover")) return;
        lastHoverSelector = selector;
        sendEvent({
          event_type: "hover",
          timestamp: Date.now() / 1000,
          url: window.location.href,
          selector: selector,
          value: trimText(target.textContent || "", 200),
          meta: getElementMeta(target),
        });
        requestScreenshot(250);
      }, 350);
    },
    true
  );

  // ── Input/Change listener ────────────────────────────────────

  document.addEventListener(
    "change",
    function (e) {
      if (!isRecording) return;
      const target = e.target;
      if (!isTextEntryControl(target) && target.tagName !== "SELECT") return;
      const selector = getCSSSelector(target);
      if (inputDebounce[selector]) {
        clearTimeout(inputDebounce[selector]);
        delete inputDebounce[selector];
      }
      sendEvent({
        event_type: target.tagName === "SELECT" ? "select" : "fill",
        timestamp: Date.now() / 1000,
        url: window.location.href,
        selector: selector,
        value: recordedInputValue(target),
        meta: getElementMeta(target),
      });
      requestScreenshot(250);
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
      if (!isTextEntryControl(target)) return;
      const selector = getCSSSelector(target);

      // Debounce: only send after 500ms of no typing
      if (inputDebounce[selector]) {
        clearTimeout(inputDebounce[selector]);
      }
      inputDebounce[selector] = setTimeout(() => {
        sendEvent({
          event_type: "input",
          timestamp: Date.now() / 1000,
          url: window.location.href,
          selector: selector,
          value: recordedInputValue(target),
          meta: getElementMeta(target),
        });
        delete inputDebounce[selector];
        requestScreenshot(250);
      }, INPUT_DEBOUNCE_MS);
    },
    true
  );

  // ── Form submit listener ─────────────────────────────────────

  document.addEventListener(
    "submit",
    function (e) {
      if (!isRecording) return;
      const form = e.target;
      recordFormState(form);
      sendEvent({
        event_type: "submit",
        timestamp: Date.now() / 1000,
        url: window.location.href,
        selector: getCSSSelector(form),
        value: form.action || null,
        meta: { method: form.method || "GET", action: form.action || "" },
      });
      requestScreenshot(250);
    },
    true
  );

  // ── Navigation / page load snapshot ──────────────────────────

  function capturePageSnapshot() {
    if (!isRecording) return;
    const snapshotRoot = document.documentElement.cloneNode(true);
    snapshotRoot.querySelectorAll("input, textarea").forEach(function (field) {
      if (isSensitiveInput(field)) {
        field.setAttribute("value", "********");
        field.textContent = "";
      }
    });
    sendEvent({
      event_type: "navigate",
      timestamp: Date.now() / 1000,
      url: window.location.href,
      selector: null,
      value: document.title,
      dom_snapshot: snapshotRoot.outerHTML.substring(0, 50000),
      meta: { title: document.title },
    });

    requestScreenshot(250);
  }

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
      beginRecording(true);
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

  // A fresh content script is created after full-page navigation.
  // Restore the background recording state so the new page keeps recording.
  try {
    chrome.runtime.sendMessage({ type: "GET_STATE" }, function (response) {
      if (chrome.runtime.lastError || !response || !response.isRecording) {
        return;
      }
      beginRecording(false);
    });
  } catch (e) {}

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
