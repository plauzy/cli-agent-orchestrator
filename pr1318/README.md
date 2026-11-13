# Evidence for awslabs/cli-agent-orchestrator#1318

Head commit: b5c1a276c1bf12513256eb55f8a698fb990b0ab2 (base: upstream main 6960d6be92c0366da02e8a32da0bab5443d18c1d).

Every screenshot is 1440x900 at device scale 2. Each comes from a private cao-server (free loopback port,
throwaway HOME, its own tmux socket, CAO_AGUI_ENABLED=1) whose mock_cli terminals really assign and hand
off. The same driver script runs each time, so terminal ids and timestamps differ between runs. The
browser is Playwright Chromium, and ffmpeg-static makes the GIF.

- before-*.png: upstream main as shipped (no stylesheet), light.
- after-*.png: this commit, light. after-1 has keyboard focus on Approve (focus-visible ring).
- after-dark-finished-fullpage.png: this commit with prefers-color-scheme: dark.
- after-run.gif: the whole light run on this commit.
- contrast.txt: WCAG contrast ratios for the stylesheet's colour pairs, both schemes.
- unit-build.txt, e2e.txt, gates.txt: command output.
