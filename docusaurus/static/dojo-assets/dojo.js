// ABOUTME: CAO AG-UI Dojo renderer — replays the committed fixture bundle into panels,
// ABOUTME: refuses off-list components (defense-in-depth), and exposes data-dojo-* hooks for the shift-left recorder.
"use strict";

(function () {
  // The closed generative-UI allow-list, mirrored client-side as defense in
  // depth (docs/agui.md "A conformant client SHOULD mirror the allow-list").
  var ALLOW_LIST = {
    approval_card: true,
    choice_prompt: true,
    diff_summary: true,
    progress: true,
    metric: true,
    agent_card: true,
  };

  function readJSON(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }
  function readNDJSON(id) {
    var el = document.getElementById(id);
    if (!el) return [];
    return el.textContent
      .split("\n")
      .map(function (l) { return l.trim(); })
      .filter(Boolean)
      .map(function (l) { try { return JSON.parse(l); } catch (e) { return null; } })
      .filter(Boolean);
  }

  // Safe element builder — text goes in via textContent, never innerHTML.
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }
  function slot(id) { return document.getElementById(id); }
  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); }

  // ---------- Dashboard ----------
  function renderDashboard(manifest, dash) {
    var s = slot("dojo-dashboard-slot");
    if (!s) return;
    clear(s);
    if (!dash) { s.appendChild(el("em", null, "no dashboard fixture")); return; }

    var stats = el("div", "dojo-stats");
    stats.appendChild(stat("active sessions", dash.active_sessions));
    stats.appendChild(stat("terminals", (dash.counts && dash.counts.terminals) || 0));
    stats.appendChild(stat("providers", Object.keys(dash.by_provider || {}).length));
    s.appendChild(stats);

    var provs = el("div", "dojo-providers");
    var by = dash.by_provider || {};
    Object.keys(by).forEach(function (p) {
      var chip = el("span", "dojo-chip", p + " ×" + by[p]);
      chip.setAttribute("data-provider", p);
      provs.appendChild(chip);
    });
    s.appendChild(provs);

    if (dash.waiting_terminals && dash.waiting_terminals.length) {
      var w = el("div", "dojo-waiting");
      w.appendChild(el("span", "dojo-badge warn", "waiting: " + dash.waiting_terminals.length));
      dash.waiting_terminals.forEach(function (t) {
        w.appendChild(el("span", "dojo-chip", (t.terminal_id || "?") + " · " + (t.reason || "")));
      });
      s.appendChild(w);
    }
  }
  function stat(label, value) {
    var d = el("div", "dojo-stat");
    d.appendChild(el("div", "dojo-stat-value", value));
    d.appendChild(el("div", "dojo-stat-label", label));
    return d;
  }

  // ---------- Timeline ----------
  function renderTimeline(entries) {
    var s = slot("dojo-timeline-slot");
    if (!s) return;
    clear(s);
    if (!entries.length) { s.appendChild(el("em", null, "no delegations")); return; }
    var ol = el("ol", "dojo-timeline-list");
    entries.forEach(function (e) {
      var li = el("li", "dojo-timeline-item");
      li.setAttribute("data-status", e.status || "open");
      var head = el("div", "dojo-timeline-head");
      head.appendChild(el("span", "dojo-kind " + (e.orchestration_type || ""), e.orchestration_type || e.kind));
      head.appendChild(el("span", "dojo-arrow", (e.sender || "?") + " → " + (e.receiver || "?")));
      head.appendChild(el("span", "dojo-status " + (e.status || ""), e.status || "open"));
      li.appendChild(head);
      // Metadata only — there is deliberately no message body to show.
      li.appendChild(el("div", "dojo-meta", "tool: " + (e.tool_call_name || "—") + " · metadata only"));
      ol.appendChild(li);
    });
    s.appendChild(ol);
  }

  // ---------- Generative UI (the six components + off-list refusal) ----------
  function renderGenerative(reel) {
    var s = slot("dojo-generative-slot");
    if (!s) return;
    clear(s);
    reel.forEach(function (item) {
      var comp = item.component;
      var allowed = ALLOW_LIST[comp] === true;
      // Refuse anything not on the allow-list — regardless of what the fixture
      // claims — and NEVER create the named node. Inert placeholder only.
      if (!allowed) {
        var refused = el("div", "dojo-card dojo-refused");
        refused.setAttribute("data-dojo-offlist-refused", "true");
        refused.setAttribute("data-offlist-component", comp);
        refused.appendChild(el("div", "dojo-card-title", "⛔ refused: " + comp));
        refused.appendChild(el("div", "dojo-card-body", "Off-list component refused server-side and client-side. No HTML/iframe/script is ever rendered."));
        s.appendChild(refused);
        return;
      }
      var card = renderComponent(comp, item.props || {});
      if (card) {
        card.setAttribute("data-dojo-component", comp);
        s.appendChild(card);
      }
    });
  }

  function renderComponent(comp, props) {
    var card = el("div", "dojo-card dojo-comp-" + comp);
    switch (comp) {
      case "agent_card":
        card.appendChild(el("div", "dojo-card-title", props.name || "agent"));
        card.appendChild(el("div", "dojo-card-body", (props.provider || "") + " · " + (props.status || "")));
        break;
      case "progress":
        card.appendChild(el("div", "dojo-card-title", props.label || "progress"));
        var bar = el("div", "dojo-progress");
        var fill = el("div", "dojo-progress-fill");
        var v = typeof props.value === "number" ? Math.max(0, Math.min(1, props.value)) : null;
        fill.style.width = v === null ? "40%" : (v * 100).toFixed(0) + "%";
        if (v === null) fill.className += " indeterminate";
        bar.appendChild(fill);
        card.appendChild(bar);
        if (v !== null) card.appendChild(el("div", "dojo-card-body", (v * 100).toFixed(0) + "%"));
        break;
      case "diff_summary":
        card.appendChild(el("div", "dojo-card-title", props.title || "diff"));
        (props.files || []).forEach(function (f) {
          var row = el("div", "dojo-diff-row");
          row.appendChild(el("span", "dojo-diff-path", f.path || "?"));
          row.appendChild(el("span", "dojo-add", "+" + (f.additions || 0)));
          row.appendChild(el("span", "dojo-del", "-" + (f.deletions || 0)));
          card.appendChild(row);
        });
        break;
      case "metric":
        card.appendChild(el("div", "dojo-metric-value", String(props.value) + (props.unit ? " " + props.unit : "")));
        card.appendChild(el("div", "dojo-card-body", props.label || ""));
        break;
      case "choice_prompt":
        card.appendChild(el("div", "dojo-card-title", props.question || "choose"));
        var choices = el("div", "dojo-choices");
        (props.choices || []).forEach(function (c) {
          var label = typeof c === "string" ? c : (c.label || c.value || "");
          choices.appendChild(el("button", "dojo-choice", label));
        });
        card.appendChild(choices);
        break;
      case "approval_card":
        card.className += " risk-" + (props.risk || "low");
        card.appendChild(el("div", "dojo-card-title", props.title || "approve?"));
        if (props.detail) card.appendChild(el("div", "dojo-card-body", props.detail));
        var acts = el("div", "dojo-actions");
        acts.appendChild(el("button", "dojo-btn approve", "Approve"));
        acts.appendChild(el("button", "dojo-btn deny", "Deny"));
        card.appendChild(acts);
        if (props.risk) card.appendChild(el("span", "dojo-badge risk", "risk: " + props.risk));
        break;
      default:
        return null;
    }
    return card;
  }

  // ---------- Raw frames ----------
  function renderFrames(frames) {
    var s = slot("dojo-frames-slot");
    if (!s) return;
    clear(s);
    s.appendChild(el("div", "dojo-badge", frames.length + " frames on the wire"));
    var pre = el("div", "dojo-frames-list");
    frames.forEach(function (f) {
      var row = el("div", "dojo-frame-row");
      row.appendChild(el("span", "dojo-frame-type", f.agui_type || "?"));
      var who = f.step_name || f.terminal_id || f.session_name || "";
      row.appendChild(el("span", "dojo-frame-who", who));
      pre.appendChild(row);
    });
    s.appendChild(pre);
  }

  // ---------- Optional live mode (?server=…) ----------
  function maybeLive() {
    var params = new URLSearchParams(window.location.search);
    var server = params.get("server");
    if (!server) return;
    var badge = document.getElementById("dojo-mode");
    if (badge) { badge.textContent = "live: " + server; badge.setAttribute("data-mode", "live"); }
    try {
      var es = new EventSource(server.replace(/\/$/, "") + "/agui/v1/stream");
      var s = slot("dojo-frames-slot");
      es.onmessage = function (ev) {
        try {
          var f = JSON.parse(ev.data);
          if (!s) return;
          var row = el("div", "dojo-frame-row live");
          row.appendChild(el("span", "dojo-frame-type", f.agui_type || f.type || "?"));
          row.appendChild(el("span", "dojo-frame-who", f.step_name || f.terminal_id || ""));
          s.insertBefore(row, s.firstChild);
        } catch (e) { /* ignore malformed */ }
      };
      es.onerror = function () { es.close(); };
    } catch (e) { /* live mode is best-effort; replay already rendered */ }
  }

  function main() {
    var manifest = readJSON("dojo-manifest");
    renderDashboard(manifest, readJSON("dojo-dashboard"));
    renderTimeline(readJSON("dojo-timeline") || []);
    renderGenerative(readNDJSON("dojo-reel"));
    renderFrames(readNDJSON("dojo-frames"));
    maybeLive();
    // Signal readiness for the shift-left recorder (assert-before-export).
    var root = document.getElementById("dojo");
    if (root) root.setAttribute("data-dojo-ready", "true");
    document.body.setAttribute("data-dojo-ready", "true");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", main);
  } else {
    main();
  }
})();
