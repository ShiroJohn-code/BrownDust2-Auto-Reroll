import argparse
import os
import sys

from mod.ld_controller import LDController

# 使用者可在此直接設定 adb 路徑（例如：r"C:\\LDPlayer\\adb.exe"）
DEFAULT_ADB_PATH = r"D:\\LDPlayer\\LDPlayer9\\adb.exe"


def build_parser():
    p = argparse.ArgumentParser(description="LD emulator control demo")
    p.add_argument("action", choices=[
        "list", "connect", "set-serial", "screencap", "tap", "swipe", "find", "tap-template"
    ])
    p.add_argument("--adb", dest="adb", nargs='?', const=DEFAULT_ADB_PATH, default=DEFAULT_ADB_PATH)
    p.add_argument("--serial", dest="serial", default=None)
    p.add_argument("--host", dest="host", default="127.0.0.1")
    p.add_argument("--port", dest="port", type=int, default=5555)
    p.add_argument("--out", dest="out", default=None)
    p.add_argument("--x", dest="x", type=int, default=None)
    p.add_argument("--y", dest="y", type=int, default=None)
    p.add_argument("--x2", dest="x2", type=int, default=None)
    p.add_argument("--y2", dest="y2", type=int, default=None)
    p.add_argument("--duration", dest="duration", type=int, default=300)
    p.add_argument("--template", dest="template", default=None)
    p.add_argument("--threshold", dest="threshold", type=float, default=0.85)
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        ctrl = LDController(adb_path=args.adb, serial=args.serial)

        if args.action == "list":
            devs = ctrl.list_devices()
            if not devs:
                print("No devices.")
            else:
                for k, v in devs.items():
                    print(k, v.get("raw", ""))
            return

        if args.action == "connect":
            ok = ctrl.connect(args.host, args.port)
            print("connect:", ok)
            return

        if args.action == "set-serial":
            if not args.serial:
                print("--serial is required")
                sys.exit(2)
            ctrl.set_serial(args.serial)
            print("serial set to:", args.serial)
            return

        if args.action == "screencap":
            out = ctrl.save_screenshot(args.out)
            print("saved:", out)
            return

        if args.action == "tap":
            if args.x is None or args.y is None:
                print("--x --y are required")
                sys.exit(2)
            print("tap:", ctrl.tap(args.x, args.y))
            return

        if args.action == "swipe":
            if None in (args.x, args.y, args.x2, args.y2):
                print("--x --y --x2 --y2 are required")
                sys.exit(2)
            ok = ctrl.swipe(args.x, args.y, args.x2, args.y2, duration_ms=args.duration)
            print("swipe:", ok)
            return

        if args.action == "find":
            if not args.template:
                print("--template is required")
                sys.exit(2)
            info = ctrl.find_template(args.template, threshold=args.threshold)
            print(info if info else "not found")
            return

        if args.action == "tap-template":
            if not args.template:
                print("--template is required")
                sys.exit(2)
            info = ctrl.tap_template(args.template, threshold=args.threshold)
            print(info if info else "not found or tap failed")
            return
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
