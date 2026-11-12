"""Command line: `ffhelper run` and `ffhelper calibrate`."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import threading
from pathlib import Path

from .config import Config, ConfigError, load_config

log = logging.getLogger("ffhelper")

# PyInstaller unpacks bundled data files under sys._MEIPASS; from source they're in the working folder.
DEFAULTS_DIR = Path(getattr(sys, "_MEIPASS", "."))


def default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        # The installed app can't write next to itself, so settings live in the user's AppData.
        return Path(os.environ.get("APPDATA", Path.home())) / "FFHelper" / "config.toml"
    return Path("config.toml")


def create_config(path: Path, defaults: Path = DEFAULTS_DIR) -> None:
    """First run: copy the example settings, and the example callouts if there's no mechanics folder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(defaults / "config.example.toml", path)
    mechanics = path.parent / "mechanics"
    if not mechanics.exists():
        shutil.copytree(defaults / "mechanics", mechanics)
    log.info("Created %s", path)


def run(config: Config, radar: bool = True, coach: bool = True) -> int:
    from .capture import monitor_width
    from .coach import run_coach
    from .mechanics import MechanicsBook
    from .radar import run_radar
    from .voice import Voice

    # Surface config problems now rather than from inside a worker thread.
    jobs = []
    if radar and config.radar.enabled:
        config.region(config.radar.region)
        book = MechanicsBook.load(config.radar.mechanics, config.radar.match_cutoff)
        jobs.append(("radar", run_radar, (config, book)))
    if coach and config.coach.enabled:
        for name in config.coach.regions:
            config.region(name)
        jobs.append(("coach", run_coach, (config,)))
    if not jobs:
        raise ConfigError("Both the radar and the coach are off. Nothing to do.")
    monitor_width(config.monitor)

    voice = Voice(config.voice.rate)
    stop = threading.Event()
    workers = [
        threading.Thread(target=target, args=(*args, voice, stop), name=name, daemon=True)
        for name, target, args in jobs
    ]
    for worker in workers:
        worker.start()
    log.info("FFHelper running. Press Ctrl+C to stop.")
    interrupted = False
    try:
        # Short waits keep Ctrl+C responsive on Windows.
        while any(worker.is_alive() for worker in workers):
            stop.wait(0.5)
        log.error("Everything has stopped. See the messages above.")
    except KeyboardInterrupt:
        interrupted = True
        log.info("Stopping...")
    finally:
        stop.set()
        for worker in workers:
            worker.join(timeout=5)
        voice.close()
    return 0 if interrupted else 1


def _owns_console() -> bool:
    """True when Windows opened a console window just for us, e.g. when started from a shortcut."""
    if sys.platform != "win32":
        return False
    import ctypes

    return ctypes.windll.kernel32.GetConsoleProcessList((ctypes.c_uint32 * 1)(), 1) == 1


def main(argv: list[str] | None = None) -> int:
    try:
        code = _main(sys.argv[1:] if argv is None else argv)
    except SystemExit as e:  # argparse usage errors
        code = e.code if isinstance(e.code, int) else 1
    if code and _owns_console():
        input("Press Enter to close this window...")
    return code


def _main(argv: list[str]) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-c", "--config", type=Path, help="settings file (default: config.toml, or AppData when installed)"
    )
    parser = argparse.ArgumentParser(prog="ffhelper", description="Local, screen-reading FFXIV raid assistant.")
    commands = parser.add_subparsers(dest="command", required=True)
    run_cmd = commands.add_parser("run", parents=[common], help="start the raid assistant")
    run_cmd.add_argument("--no-radar", action="store_true", help="skip boss cast-bar callouts")
    run_cmd.add_argument("--no-coach", action="store_true", help="skip the AI rotation coach")
    run_cmd.add_argument("--debug", action="store_true", help="log every OCR read and coach timing")
    cal_cmd = commands.add_parser("calibrate", parents=[common], help="drag boxes to set screen regions")
    cal_cmd.add_argument("--delay", type=float, default=3.0, help="seconds before the screenshot (default: 3)")
    cal_cmd.add_argument("--image", type=Path, help="use a saved full-screen screenshot instead")
    args = parser.parse_args(argv or ["run"])  # double-clicking the exe starts the assistant

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    if getattr(args, "debug", False):
        log.setLevel(logging.DEBUG)

    config_path = args.config or default_config_path()
    try:
        if args.config is None and not config_path.exists() and (DEFAULTS_DIR / "config.example.toml").exists():
            create_config(config_path)
        config = load_config(config_path)
        if args.command == "calibrate":
            from .calibrate import calibrate

            calibrate(config, args.delay, args.image)
            return 0
        return run(config, radar=not args.no_radar, coach=not args.no_coach)
    except ConfigError as e:
        log.error("%s", e)
        return 2
    except KeyboardInterrupt:
        return 0
    except Exception:
        log.exception("Unexpected error")
        return 1
