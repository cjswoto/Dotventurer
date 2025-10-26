"""CLI harness to audition procedural audio events and behaviors."""

from __future__ import annotations

import argparse
import sys
import time

from audio.logging import log_lines
from audio.sfx import SFX

SCREEN_SIZE = (1920, 1080)


def list_events(sfx: SFX) -> None:
    log_lines(["qa_harness.list_events"])
    for spec in sfx._catalog.events():  # pragma: no cover - diagnostic helper
        print(
            f"{spec.name:20s} bus={spec.bus:5s} priority={spec.priority} loop={spec.loop}"
        )


def play_event(sfx: SFX, event: str, loop: bool = False) -> None:
    log_lines([f"qa_harness.play_event event={event} loop={loop}"])
    if loop:
        sfx.play_loop(event, pos=(SCREEN_SIZE[0] / 2, SCREEN_SIZE[1] / 2), screen_size=SCREEN_SIZE)
    else:
        sfx.play(event, pos=(SCREEN_SIZE[0] / 2, SCREEN_SIZE[1] / 2), screen_size=SCREEN_SIZE)
    sfx.update(0.016)


def spam_event(sfx: SFX, event: str, count: int = 20, interval: float = 0.05) -> None:
    log_lines([f"qa_harness.spam_event event={event} count={count}"])
    for _ in range(count):
        sfx.play(event)
        sfx.update(interval)
        time.sleep(interval)


def sweep_pan(sfx: SFX, event: str, steps: int = 10) -> None:
    log_lines([f"qa_harness.sweep_pan event={event} steps={steps}"])
    width = SCREEN_SIZE[0]
    for i in range(steps + 1):
        x = (width / steps) * i
        sfx.play(event, pos=(x, SCREEN_SIZE[1] / 2), screen_size=SCREEN_SIZE)
        left, right = sfx._pan(sfx._catalog.get_spec(event), (x, 0), SCREEN_SIZE)
        print(f"x={x:6.1f} left={left:.3f} right={right:.3f}")
        sfx.update(0.016)
        time.sleep(0.05)


def duck_demo(sfx: SFX, loop_event: str, transient_event: str) -> None:
    log_lines([f"qa_harness.duck_demo loop={loop_event} transient={transient_event}"])
    sfx.play_loop(loop_event)
    time.sleep(0.5)
    sfx.duck("loops", -6.0, 250)
    sfx.play(transient_event)
    for _ in range(30):
        sfx.update(0.016)
        time.sleep(0.016)
    sfx.stop_loop(loop_event)


def overflow_demo(sfx: SFX, event: str, plays: int = 10) -> None:
    log_lines([f"qa_harness.overflow_demo event={event} plays={plays}"])
    for i in range(plays):
        sfx.play(event)
        print(f"trigger {i+1}")
        sfx.update(0.01)
        time.sleep(0.01)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Procedural audio QA harness")
    parser.add_argument("mode", choices=["list", "play", "play_loop", "spam", "pan", "duck", "overflow"])
    parser.add_argument("event", nargs="?", default="hit")
    parser.add_argument("event_b", nargs="?", default="explosion")
    args = parser.parse_args(argv)

    sfx = SFX()

    if args.mode == "list":
        list_events(sfx)
    elif args.mode == "play":
        play_event(sfx, args.event, loop=False)
    elif args.mode == "play_loop":
        play_event(sfx, args.event, loop=True)
    elif args.mode == "spam":
        spam_event(sfx, args.event)
    elif args.mode == "pan":
        sweep_pan(sfx, args.event)
    elif args.mode == "duck":
        duck_demo(sfx, args.event, args.event_b)
    elif args.mode == "overflow":
        overflow_demo(sfx, args.event)

    return 0


if __name__ == "__main__":  # pragma: no cover - manual QA entry
    raise SystemExit(main())
