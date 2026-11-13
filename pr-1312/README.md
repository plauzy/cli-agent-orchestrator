# Evidence for awslabs/cli-agent-orchestrator#1312 at head 8f82180c0751a4c7d0b984550fc4e986bef9d43d

Everything here was recorded on private cao-servers (loopback port, isolated HOME, own tmux socket, mock_cli agents),
not on a live fleet. Dashboard media and both status probes were recorded on exactly 8f82180c0751a4c7d0b984550fc4e986bef9d43d.
The CAO Dojo media, the AG-UI Dojo still and the inspector still were taken on b7d3f043872e4fd96ba3af6f5f5232d5aa444020;
nothing under examples/ag-ui/cao-dojo changed between that commit and 8f82180c0751a4c7d0b984550fc4e986bef9d43d.

| Files | Recorded with |
|---|---|
| 1312-dashboard-fleet-live.gif/.mp4, 3-dashboard-fleet-host-status.png, 4-dashboard-timeline-handoff.png | the operator dashboard (vite dev, shipped view/styles.css), Playwright video and screenshots, ffmpeg-static |
| 5-SYNTHETIC-runner-grouping.png | the operator dashboard with the stream served by the test (Playwright route fulfilment): SYNTHETIC |
| 1312-cao-dojo-live-approval.gif/.mp4, 2-cao-dojo-approval-live-status.png | CAO Dojo (index.html), Playwright, ffmpeg-static |
| 1-agui-dojo-approval.png | AG-UI Dojo (ag-ui#2216 CAO integration, Next.js dev on a throwaway copy), Playwright |
| 6-inspector-live-trace.png, live-trace.ndjson | CAO Dojo inspector.html reading a trace recorded by the Dojo recorder modules (scrubbed, leak-checked) |
| status_probe.txt, status_publish_probe-GREEN-8f82180c.txt, status_publish_probe-RED-9218c929.txt | probe scripts against a private server: terminals[].status on GET /terminals and on the stream; the status-change publish on the previous (RED) and final (GREEN) head |

Each image has a one-line .caption.txt.
