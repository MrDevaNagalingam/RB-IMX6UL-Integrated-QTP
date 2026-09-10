"""Start the RB-IMX6UL target UART server."""
import argparse

import config
import dispatcher


def main():
    parser = argparse.ArgumentParser(description="RB-IMX6UL QTP UART target")
    parser.add_argument("--port", default=config.QTP_CONSOLE)
    parser.add_argument("--baud", type=int, default=config.BAUDRATE)
    args = parser.parse_args()
    if not args.port or args.baud <= 0:
        parser.error("Configure command UART port and a positive baud rate")
    try:
        import serial
        with serial.Serial(args.port, args.baud, timeout=0.1, exclusive=True) as connection:
            print("[QTP] Listening on {} at {} baud".format(args.port, args.baud), flush=True)
            dispatcher.serve(connection)
    except KeyboardInterrupt:
        print("\n[QTP] Target stopped.")
    except (ImportError, OSError) as exc:
        print("[QTP] Target error: {}".format(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
