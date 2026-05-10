# Custom always-on-top floating window instead of native OS toasts

User-visible prompts ("当前姿势良好", "请眺望远方", "请向左/右调整") are rendered by a frameless, transparent, always-on-top Qt widget that the app draws and animates itself. The window appears on demand near a corner of the active screen, lingers for a few seconds, then dismisses itself. Native OS toast notifications (Windows Toast / Linux libnotify) were rejected as the primary mechanism.

## Considered Options

- **Native OS toasts via `desktop-notifier`** — rejected as primary: limited control over content (cannot draw a head-pose mini-preview), inconsistent dismissal behavior across Windows 10 / 11 / different Linux DEs, and Linux DEs (GNOME especially) sometimes route notifications into a tray history the user doesn't see.
- **In-window banner only** — rejected: invisible when the main window is minimized to tray, which is the expected operating mode.
- **Modal popup** — rejected: interrupts focus and clearly fails the productized polish bar.

## Consequences

- Cross-platform always-on-top behavior must be handled deliberately: Windows + X11 are straightforward, Wayland needs a layer-shell or platform-specific workaround.
- High-DPI scaling, multi-monitor active-screen detection, and click-through behavior all become our problem.
- The custom widget is also where we can render extra context (a tiny head-pose indicator, a "snooze" link, a count-down to auto-dismiss) — the upside that justifies the complexity.
