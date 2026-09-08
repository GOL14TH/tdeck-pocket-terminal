#!/usr/bin/env python3

"""Inspect one ROM loader and optionally write a hash-verified app image only."""

import argparse, hashlib, re, subprocess, sys

from pathlib import Path

def main():

    ap = argparse.ArgumentParser(description=__doc__)

    ap.add_argument("--port", required=True)

    ap.add_argument("--expected-mac", required=True)

    ap.add_argument("--image", type=Path, required=True)

    ap.add_argument("--sha256", required=True)

    ap.add_argument("--confirm-app-write", action="store_true")

    a = ap.parse_args()

    data = a.image.read_bytes()

    if not data or data[0] != 0xE9 or len(data) > 0x640000:

        raise SystemExit("Invalid/oversized app image")

    if hashlib.sha256(data).hexdigest().lower() != a.sha256.lower():

        raise SystemExit("Image SHA-256 does not match reviewed artifact")

    def run(*args):

        p = subprocess.run(

            [

                sys.executable,

                "-m",

                "esptool",

                "--chip",

                "esp32s3",

                "--port",

                a.port,

                "--before",

                "no_reset",

                "--after",

                "no_reset",

                *args,

            ],

            capture_output=True,

            text=True,

            timeout=180,

        )

        if p.returncode:

            raise SystemExit(

                "ROM operation failed; no further action. "

                + p.stdout[-500:]

                + p.stderr[-500:]

            )

        return p.stdout

    output = run("read_mac")

    macs = re.findall(r"MAC:\s*([0-9a-f:]{17})", output, re.I)

    normalize = lambda s: re.sub("[^0-9a-f]", "", s.lower())

    detected = {normalize(mac) for mac in macs}

    if detected != {normalize(a.expected_mac)}:

        raise SystemExit("ROM MAC does not match the reviewed T-Deck")

    output = run("flash_id")

    if not re.search(r"Detected flash size:\s*16MB", output, re.I):

        raise SystemExit("Expected 16MB flash; stopping")

    print("Exact ROM MAC and 16MB flash confirmed. App hash verified.")

    if not a.confirm_app_write:

        print(

            "INSPECTION ONLY. Supply --confirm-app-write only after reviewing/approving the image."

        )

        return

    output = run("write_flash", "0x10000", str(a.image.resolve()))

    if "Hash of data verified" not in output:

        raise SystemExit("Write did not report verification; inspect before rebooting")

    print(

        "Application write verified. No factory erase or filesystem write. Press RST to boot."

    )

if __name__ == "__main__":

    main()
