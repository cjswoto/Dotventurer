"""Console harness for exercising the SFX runtime."""

from __future__ import annotations

import argparse
import shlex
import time
from typing import Optional, Tuple

from .logging_utils import log_line
from .sfx import SFX

DEFAULT_SCREEN = (1920, 1080)
_DT = 1.0 / 60.0


class Harness:
    """Simple REPL used during manual QA passes."""

    def __init__(self, enable_audio: bool, catalog: Optional[str]):
        self.sfx = SFX(enable_audio=enable_audio, config_path=catalog)
        self.screen_size: Tuple[int, int] = DEFAULT_SCREEN
        self.position = [self.screen_size[0] / 2, self.screen_size[1] / 2]

    def run(self) -> None:
        log_line("QA harness started")
        print("SFX QA Harness — type 'help' for commands, 'exit' to quit")
        while True:
            try:
                raw = input("sfx> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not raw.strip():
                continue
            if raw.strip().lower() in {"exit", "quit"}:
                break
            if raw.strip().lower() == "help":
                self._print_help()
                continue
            self._dispatch(raw)
        log_line("QA harness stopped")

    def _dispatch(self, raw: str) -> None:
        parts = shlex.split(raw)
        if not parts:
            return
        command, *rest = parts
        method = getattr(self, f"_cmd_{command}", None)
        if method is None:
            print(f"Unknown command: {command}")
            return
        method(rest)

    # ------------------------------------------------------------------
    def _cmd_play(self, args):
        if not args:
            print("Usage: play <event>")
            return
        event = args[0]
        self.sfx.play(event, pos=tuple(self.position), screen_size=self.screen_size)
        self._tick(0.5)

    def _cmd_loop(self, args):
        if not args:
            print("Usage: loop <event>")
            return
        event = args[0]
        self.sfx.play_loop(event, pos=tuple(self.position), screen_size=self.screen_size)
        self._tick(0.2)

    def _cmd_stop(self, args):
        if not args:
            print("Usage: stop <event>")
            return
        self.sfx.stop_loop(args[0])
        self._tick(0.1)

    def _cmd_duck(self, args):
        if not args:
            print("Usage: duck <bus> [gain_db] [ms]")
            return
        bus = args[0]
        gain = float(args[1]) if len(args) > 1 else -6.0
        ms = int(args[2]) if len(args) > 2 else 250
        self.sfx.duck(bus, gain_db=gain, ms=ms)
        self._tick(ms / 1000.0)

    def _cmd_pan(self, args):
        if not args:
            print("Usage: pan <x (0-1)>")
            return
        x = float(args[0])
        x = max(0.0, min(1.0, x))
        self.position[0] = x * self.screen_size[0]
        print(f"Pan position set to {self.position[0]:.1f}")

    def _cmd_sweep(self, args):
        if not args:
            print("Usage: sweep <event>")
            return
        event = args[0]
        steps = 20
        for idx in range(steps + 1):
            frac = idx / steps
            self.position[0] = frac * self.screen_size[0]
            self.sfx.play(event, pos=tuple(self.position), screen_size=self.screen_size)
            self._tick(0.1)

    def _cmd_spam(self, args):
        if len(args) < 2:
            print("Usage: spam <event> <count>")
            return
        event, count = args[0], int(args[1])
        for _ in range(count):
            self.sfx.play(event, pos=tuple(self.position), screen_size=self.screen_size)
            self._tick(0.05)

    def _cmd_overflow(self, args):
        if not args:
            print("Usage: overflow <bus>")
            return
        bus = args[0]
        cap = self.sfx.buses.get(bus, self.sfx.buses["sfx"]).cap
        for idx in range(cap + 2):
            event = f"qa_overflow_{idx}"
            spec = self.sfx.catalog.get(event)
            spec.bus = bus
            spec.priority = idx
            self.sfx.catalog._events[event] = spec  # type: ignore[attr-defined]
            self.sfx.play(event)
        self._tick(0.5)

    def _cmd_status(self, args):  # noqa: ARG002 - command signature
        snapshot = self.sfx.get_debug_snapshot()
        print("Buses:")
        for bus, data in snapshot["buses"].items():
            print(f"  {bus}: {data['voices']} voices ({data['virtual']} virtual)")
        print("Recent events:", ", ".join(snapshot["events"]))

    # ------------------------------------------------------------------
    def _tick(self, duration: float) -> None:
        elapsed = 0.0
        while elapsed < duration:
            self.sfx.update(_DT)
            time.sleep(_DT)
            elapsed += _DT

    def _print_help(self) -> None:
        print(
            "Commands: play, loop, stop, duck, pan, sweep, spam, overflow, status, help, exit"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive harness for the SFX mixer")
    parser.add_argument("--mute", action="store_true", help="Disable actual audio output")
    parser.add_argument("--catalog", help="Path to catalog JSON", default=None)
    args = parser.parse_args()

    harness = Harness(enable_audio=not args.mute, catalog=args.catalog)
    harness.run()


if __name__ == "__main__":
    main()
