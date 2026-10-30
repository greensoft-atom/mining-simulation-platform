#!/usr/bin/env python3
"""Capture GrowStone screens and clips from your own phone or emulator.

Other people's videos show their account at one moment, at YouTube quality.
The most complete and current UI reference is the one you record while you
play: every menu, popup and transition at full resolution, with your labels.
Files go to corpus/media/own/<date>/ and appear first in media.py's gallery.

  python3 capture.py session                  # interactive; type "help" inside
  python3 capture.py shot "inventory full"    # one screenshot with a label
  python3 capture.py record 120 "clan raid"   # 120 s of video (no audio); takes over 180 s are split
  python3 capture.py import ~/phone-export    # screenshots and recordings you copied off the phone

shot, record and session need Android platform-tools (adb) with USB debugging
on; pass --serial when several devices are connected. If the game will not
start while USB debugging is on (anti-tamper checks sometimes look for it),
use the phone's own screenshot and screen-record buttons, or scrcpy's
--record (which also keeps the audio), and import the files. A black
screenshot means the app blocks capture.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from common import DEFAULT_OUT, log, slug

MAX_TAKE = 180  # screenrecord stops each file at 3 minutes
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm", ".mov", ".mkv"}
HELP = ('Enter = screenshot · "<label>" Enter = labeled screenshot · "r <seconds> [label]" = record · q = quit')


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class Captures:
    """corpus/media/own/<date>/<time>_<label>.<ext>, listed in own/index.jsonl."""

    def __init__(self, out: Path):
        self.out = out
        self.index_path = out / "index.jsonl"
        self.known = {e["sha1"] for e in self.entries()}

    def entries(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        return [json.loads(line) for line in self.index_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def path_for(self, when: dt.datetime, label: str, ext: str) -> Path:
        name = when.strftime("%H%M%S") + (f"_{slug(label, 40)}" if label else "")
        path = self.out / when.strftime("%Y-%m-%d") / f"{name}{ext}"
        n = 1
        while path.exists():
            path = path.with_name(f"{name}_{n}{ext}")
            n += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def register(self, path: Path, digest: str, label: str, source: str) -> None:
        self.known.add(digest)
        entry = {"file": path.relative_to(self.out.parent).as_posix(), "label": label, "source": source,
                 "sha1": digest, "saved": dt.datetime.now().isoformat(timespec="seconds")}
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def adb(serial: str | None, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["adb", *(["-s", serial] if serial else []), *args], capture_output=True, check=True)


def shot(cap: Captures, serial: str | None, label: str) -> Path:
    png = adb(serial, "exec-out", "screencap", "-p").stdout
    if not png.startswith(b"\x89PNG"):
        raise SystemExit("adb returned no image: " + png[:200].decode(errors="replace"))
    path = cap.path_for(dt.datetime.now(), label, ".png")
    path.write_bytes(png)
    cap.register(path, hashlib.sha1(png).hexdigest(), label, "adb screencap")
    log(f"saved {path}" + ("  (nearly empty: the app may block capture)" if len(png) < 15_000 else ""))
    return path


def record(cap: Captures, serial: str | None, seconds: int, label: str) -> list[Path]:
    saved, left, part = [], seconds, 1
    while left > 0:
        take = min(left, MAX_TAKE)
        remote = f"/sdcard/gs_capture_{part}.mp4"
        log(f"recording {take} s" + (f" (part {part})" if seconds > MAX_TAKE else "") + " ...")
        start = dt.datetime.now()
        adb(serial, "shell", "screenrecord", "--time-limit", str(take), remote)
        path = cap.path_for(start, label + (f" part{part}" if seconds > MAX_TAKE else ""), ".mp4")
        adb(serial, "pull", remote, str(path))
        adb(serial, "shell", "rm", "-f", remote)
        cap.register(path, sha1_file(path), label, "adb screenrecord")
        log(f"saved {path}")
        saved.append(path)
        left -= take
        part += 1
    return saved


def import_files(cap: Captures, folder: Path, label: str = "") -> tuple[int, int]:
    added = skipped = 0
    for f in sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXT):
        digest = sha1_file(f)
        if digest in cap.known:
            skipped += 1
            continue
        path = cap.path_for(dt.datetime.fromtimestamp(f.stat().st_mtime), label or f.stem, f.suffix.lower())
        shutil.copy2(f, path)
        cap.register(path, digest, label or f.stem, f"import:{f.name}")
        added += 1
    log(f"imported {added} files ({skipped} already there) into {cap.out}")
    return added, skipped


def session(cap: Captures, serial: str | None) -> None:
    log(HELP)
    while True:
        try:
            line = input("capture> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line in ("q", "quit", "exit"):
            break
        if line == "help":
            log(HELP)
            continue
        try:
            if m := re.fullmatch(r"r\s+(\d+)\s*(.*)", line):
                record(cap, serial, int(m.group(1)), m.group(2))
            else:
                shot(cap, serial, line)
        except subprocess.CalledProcessError as e:
            log(f"adb failed: {e.stderr.decode(errors='replace').strip()}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serial", help="adb device serial (see `adb devices`)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT / "media" / "own")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("session", help="interactive screenshots and recordings")
    p = sub.add_parser("shot", help="one screenshot")
    p.add_argument("label", nargs="?", default="")
    p = sub.add_parser("record", help="record the screen")
    p.add_argument("seconds", type=int)
    p.add_argument("label", nargs="?", default="")
    p = sub.add_parser("import", help="copy screenshots and recordings from a folder")
    p.add_argument("folder", type=Path)
    p.add_argument("--label", default="", help="label for every file (default: the original file name)")
    args = ap.parse_args(argv)

    cap = Captures(args.out)
    if args.cmd == "import":
        import_files(cap, args.folder.expanduser(), args.label)
        return 0
    if not shutil.which("adb"):
        raise SystemExit("adb not found: install Android platform-tools, or use `capture.py import` "
                         "with files saved by the phone's own screenshot and screen-record buttons.")
    try:
        if args.cmd == "session":
            session(cap, args.serial)
        elif args.cmd == "shot":
            shot(cap, args.serial, args.label)
        else:
            record(cap, args.serial, args.seconds, args.label)
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"adb failed: {e.stderr.decode(errors='replace').strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
