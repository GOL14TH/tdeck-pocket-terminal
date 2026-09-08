#!/usr/bin/env python3
"""Read-only runtime identification of one explicitly selected Meshtastic device."""

import argparse, json, time
from pathlib import Path
from serial.tools import list_ports
from meshtastic.serial_interface import SerialInterface

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", required=True)
    ap.add_argument("--output", default=".tdeck-device.json")
    a = ap.parse_args()
    ports = [p for p in list_ports.comports() if p.device == a.port]
    if len(ports) != 1:
        raise SystemExit("Selected serial port is not present")
    info = ports[0]
    interface = SerialInterface(devPath=a.port)
    try:
        metadata = interface.metadata
        from meshtastic.protobuf import config_pb2, mesh_pb2

        family = mesh_pb2.HardwareModel.Name(metadata.hw_model)
        if family != "T_DECK":
            raise SystemExit("This runtime does not identify as T_DECK")
        record = {
            "runtime_verified": True,
            "family": family,
            "port": a.port,
            "usb_serial": info.serial_number,
            "vid": info.vid,
            "pid": info.pid,
            "firmware": metadata.firmware_version,
            "verified_at": int(time.time()),
        }
        Path(a.output).write_text(json.dumps(record, indent=2) + "\n")
        print(
            f"Runtime verified: {family}, firmware {metadata.firmware_version}. No flash/configuration written."
        )
    finally:
        interface.close()

if __name__ == "__main__":
    main()
