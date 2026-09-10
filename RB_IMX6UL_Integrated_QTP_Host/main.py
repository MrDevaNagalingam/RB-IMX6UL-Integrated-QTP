"""Start the host UART connection and interactive test menu."""
import argparse

from command_handler import CommandHandler
from interactive_menu import interactive_mode
from uart_handler import UARTCommunicator


def main():
    parser = argparse.ArgumentParser(description="RB-IMX6UL Integrated QTP Host")
    parser.add_argument("port", help="Host serial port, e.g. COM4 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--report-dir", default="test_log")
    args = parser.parse_args()
    if args.baud <= 0:
        parser.error("Baud must be positive")
    uart = UARTCommunicator(args.port, args.baud)
    handler = None
    try:
        print("[QTP] Using Serial Port: {}".format(args.port))
        print("[QTP] Starting in interactive mode")
        uart.connect()
        print("[QTP] Connected to {} at {} baud".format(args.port, args.baud))
        handler = CommandHandler(uart)
        interactive_mode(handler, args.report_dir)
    except (KeyboardInterrupt, EOFError):
        print("\n[QTP] Host stopped. An active target test may continue.")
    except (ImportError, OSError) as exc:
        print("[QTP] Error: {}".format(exc))
        return 1
    finally:
        uart.disconnect()
        print("[QTP] Shutdown complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

