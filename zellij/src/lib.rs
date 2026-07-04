// CAO v2.5 Phase 2 — `zellaude` status-bar plugin.
//
// Receives JSON snapshots from `services/zellij_bridge.py` over the
// `zellij pipe --name zellaude` channel and renders a single-line
// status bar: session count, kill-switched task classes, 60s rolling
// cache hit-rate, and the most recent ASI score (color-banded).
//
// The plugin is intentionally dumb: it stores only the latest snapshot
// and re-renders on each pipe message. All aggregation lives in the
// Python bridge so the WASM binary stays small (<2 MB) and stateless.

use std::collections::BTreeMap;

use serde::Deserialize;
use zellij_tile::prelude::*;

#[derive(Default, Debug, Deserialize)]
struct Snapshot {
    #[serde(default)]
    sessions: u32,
    #[serde(default)]
    kill_switched: Vec<String>,
    #[serde(default)]
    cache_hit_rate_60s: Option<f64>,
    #[serde(default)]
    asi: Option<AsiSnapshot>,
}

#[derive(Debug, Deserialize)]
struct AsiSnapshot {
    task_class: String,
    score: f64,
    band: String, // "green" | "yellow" | "red"
}

#[derive(Default)]
struct ZellaudeBar {
    snapshot: Snapshot,
    last_error: Option<String>,
}

register_plugin!(ZellaudeBar);

impl ZellijPlugin for ZellaudeBar {
    fn load(&mut self, _config: BTreeMap<String, String>) {
        // `pipe()` is delivered to plugins independently of the
        // `subscribe()` event filter, so we only need to declare the
        // permission we use to render the bar.
        request_permission(&[PermissionType::ReadApplicationState]);
    }

    fn pipe(&mut self, message: PipeMessage) -> bool {
        if message.name != "zellaude" {
            return false;
        }
        let payload = match message.payload {
            Some(p) => p,
            None => return false,
        };
        match serde_json::from_str::<Snapshot>(&payload) {
            Ok(snap) => {
                self.snapshot = snap;
                self.last_error = None;
            }
            Err(e) => {
                self.last_error = Some(format!("decode: {e}"));
            }
        }
        true
    }

    fn render(&mut self, _rows: usize, cols: usize) {
        let snap = &self.snapshot;
        let mut segments: Vec<String> = Vec::new();

        segments.push(format!("CAO sessions: {}", snap.sessions));

        if !snap.kill_switched.is_empty() {
            // ANSI red background for the kill-switch badge.
            segments.push(format!(
                "\x1b[41;97m KILL: {} \x1b[0m",
                snap.kill_switched.join(",")
            ));
        }

        match snap.cache_hit_rate_60s {
            Some(rate) => segments.push(format!("cache@60s: {:.1}%", rate * 100.0)),
            None => segments.push("cache@60s: --".to_string()),
        }

        if let Some(asi) = &snap.asi {
            let color = match asi.band.as_str() {
                "green" => "\x1b[42;30m",
                "yellow" => "\x1b[43;30m",
                "red" => "\x1b[41;97m",
                _ => "\x1b[40;97m",
            };
            segments.push(format!(
                "{} ASI[{}]={:.2} \x1b[0m",
                color, asi.task_class, asi.score
            ));
        } else {
            segments.push("ASI: --".to_string());
        }

        if let Some(err) = &self.last_error {
            segments.push(format!("\x1b[31m{}\x1b[0m", err));
        }

        let mut line = segments.join("  |  ");
        // Best-effort truncation; ANSI escapes are short and we leave a
        // small slack so we don't slice mid-escape on extreme widths.
        if cols > 0 && line.len() > cols + 16 {
            line.truncate(cols + 16);
        }
        print!("{}", line);
    }
}
