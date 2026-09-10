"""ESR0C-style interactive menu and text logging for RB-IMX6UL QTP."""
from datetime import datetime
import os
import re

TESTS = {
    "1": ("DDR Functionality", "TEST_DDR"),
    "2": ("NAND Flash Functionality", "TEST_NAND"),
    "3": ("UART1 Debug Console Verification", "TEST_UART1_DEBUG"),
    "4": ("RS232 UART2 Verification", "TEST_UART2_RS232"),
    "5": ("UART3 Loopback Verification", "TEST_UART3_LOOPBACK"),
    "6": ("BLE & WiFi UART5 Verification", "TEST_UART5_BLE_WIFI"),
    "7": ("RS485 UART6 Transmit Test", "TEST_UART6_RS485_TX"),
    "8": ("RS485 UART6 Transmit Stop", "TEST_UART6_RS485_TX_STOP"),
    "9": ("RS485 UART6 Receive Test", "TEST_UART6_RS485_RX"),
    "10": ("RS485 UART6 Receive Stop", "TEST_UART6_RS485_RX_STOP"),
}

TEST_MESSAGES = {
    "TEST_DDR": "This test may take some time.",
    "TEST_UART1_DEBUG": "Note: UART1 /dev/ttymxc0 is used as the debug console; this test is skipped.",
    "TEST_UART2_RS232": "Note: UART2 /dev/ttymxc1 is used for QTP communication; this test is skipped.",
    "TEST_UART3_LOOPBACK": "Note: UART3 /dev/ttymxc2 is present on MikroBUS and expansion header.",
    "TEST_UART5_BLE_WIFI": "Note: UART5 /dev/ttymxc4 is for BLE/WiFi; hardware is not mounted right now.",
    "TEST_UART6_RS485_TX": "Note: UART6 /dev/ttymxc5 is RS485.",
    "TEST_UART6_RS485_TX_STOP": "Note: This closes the UART6 transmit port.",
    "TEST_UART6_RS485_RX": (
        "Note: UART6 /dev/ttymxc5 is listening. On the connected RS485 peer, "
        "send a message, then select test 10 to stop receiving."
    ),
    "TEST_UART6_RS485_RX_STOP": "Note: This stops UART6 receive and shows the received data.",
}


class TestLogger:
    _ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

    def __init__(self, log_dir="test_log"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, "test_log_{}.txt".format(timestamp))
        self.summary_file = os.path.join(log_dir, "test_summary_{}.txt".format(timestamp))
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self.aborted_tests = 0
        self.test_results = []
        self._write_header()

    def _write_header(self):
        header = """
{0}
QTP TEST EXECUTION LOG
{0}
Session Started: {1}
{0}

""".format("=" * 80, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        with open(self.log_file, "w", encoding="utf-8") as stream:
            stream.write(header)

    def log_test_start(self, test_num, test_desc, test_cmd):
        log_entry = """
{0}
TEST #{1}: {2}
Command: {3}
Started: {4}
{0}
""".format("-" * 80, test_num, test_desc, test_cmd,
           datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        with open(self.log_file, "a", encoding="utf-8") as stream:
            stream.write(log_entry)
        print(log_entry)

    def log_test_result(self, test_num, test_desc, status, details, working_as_expected):
        self.total_tests += 1
        if status == "PASS":
            self.passed_tests += 1
        elif status == "FAIL":
            self.failed_tests += 1
        elif status == "SKIPPED":
            self.skipped_tests += 1
        else:
            self.aborted_tests += 1

        acknowledgment = "YES" if working_as_expected else "NO"
        cleaned_details = self.sanitize(details)
        log_entry = """
Result: {0}
Details: {1}
Working as Expected: {2}
Completed: {3}
{4}

""".format(status, cleaned_details, acknowledgment,
           datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "=" * 80)
        with open(self.log_file, "a", encoding="utf-8") as stream:
            stream.write(log_entry)
        print(log_entry)
        self.test_results.append({
            "num": test_num,
            "desc": test_desc,
            "status": status,
            "expected": acknowledgment,
        })

    def sanitize(self, details):
        text = "" if details is None else str(details)
        text = text.replace("\x00", "")
        text = self._ANSI_RE.sub("", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return re.sub(r"\n{3,}", "\n\n", text).rstrip("\n")

    def write_summary(self):
        pass_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests else 0
        summary = """
{0}
TEST EXECUTION SUMMARY
{0}
Session Completed: {1}

STATISTICS:
-----------
Total Tests Executed: {2}
Passed: {3}
Failed: {4}
Skipped: {5}
Aborted: {6}

Pass Rate: {7:.2f}%

DETAILED RESULTS:
-----------------
""".format("=" * 80, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           self.total_tests, self.passed_tests, self.failed_tests,
           self.skipped_tests, self.aborted_tests, pass_rate)
        for result in self.test_results:
            summary += "Test #{}: {}\n".format(result["num"], result["desc"])
            summary += "  Status: {} | Expected: {}\n\n".format(
                result["status"], result["expected"])
        summary += "{}\n".format("=" * 80)
        with open(self.summary_file, "w", encoding="utf-8") as stream:
            stream.write(summary)
        with open(self.log_file, "a", encoding="utf-8") as stream:
            stream.write(summary)
        print(summary)
        print("\nLog files saved:")
        print("  - Detailed Log: {}".format(self.log_file))
        print("  - Summary: {}".format(self.summary_file))


def display_main_menu():
    print("\n" + "=" * 80)
    print(" QTP INTERACTIVE TEST MENU ".center(80))
    print("=" * 80)
    for number, (title, command) in TESTS.items():
        print("{:2d}. {}".format(int(number), title))
    print("\n" + "=" * 80)
    print(" OPTIONS ".center(80))
    print("=" * 80)
    print("  Enter test number (1-{})".format(len(TESTS)))
    print("  Enter 'q' to quit")
    print("=" * 80)


def collect_test_params(test_cmd):
    if test_cmd == "TEST_UART3_LOOPBACK":
        message = input("Enter UART3 loopback message: ")
        return {"message": message}
    if test_cmd == "TEST_UART6_RS485_TX":
        message = input("Enter RS485 UART6 transmit message: ")
        return {"message": message}
    return None


def run_single_test(cmd_handler, test_num, logger):
    key = str(test_num)
    if key not in TESTS:
        print("[ERROR] Test #{} not found!".format(test_num))
        return True
    test_desc, test_cmd = TESTS[key]
    operator_decides_status = test_cmd == "TEST_DDR"
    logger.log_test_start(test_num, test_desc, test_cmd)
    if test_cmd in TEST_MESSAGES:
        print("[INFO] {}".format(TEST_MESSAGES[test_cmd]))
    print("\n[EXECUTING] Running test: {}".format(test_cmd))
    try:
        streamed = []

        def show_live_output(text):
            streamed.append(text)
            print(text, end="", flush=True)

        params = collect_test_params(test_cmd)
        result = cmd_handler.execute_command(test_cmd, params=params, output_callback=show_live_output)
        if result is None:
            result = {"status": "ABORTED", "details": "Command returned no result", "output": ""}
        target_status = result.get("status", "UNKNOWN")
        details = result.get("details", "No details provided")
        if not operator_decides_status or target_status in (
                "ERROR", "NOT_CONFIGURED", "NOT_IMPLEMENTED", "ABORTED"):
            display_details = logger.sanitize(details)
            print("[RESULT] Status: {}".format(target_status))
            print("[RESULT] Details: {}".format(display_details))

        print("\n" + "-" * 80)
        ack_input = input("Is this test working as expected? (y/n): ").strip().lower()
        working_as_expected = ack_input in ("y", "yes")
        if operator_decides_status:
            status = "PASS" if working_as_expected else "FAIL"
            details = re.sub(r"^Status\s*:.*$", "Status   : {}".format(status),
                             details, count=1, flags=re.MULTILINE)
        else:
            status = target_status
        logger.log_test_result(test_num, test_desc, status, details, working_as_expected)

        return True
    except KeyboardInterrupt:
        logger.log_test_result(test_num, test_desc, "ABORTED",
                               "Interrupted by user", False)
        raise
    except Exception as exc:
        error_msg = "Exception occurred: {}".format(exc)
        print("[ERROR] {}".format(error_msg))
        logger.log_test_result(test_num, test_desc, "ABORTED", error_msg, False)
        return True


def interactive_mode(cmd_handler, log_dir="test_log"):
    logger = TestLogger(log_dir)
    print("\n" + "=" * 80)
    print(" QTP ENHANCED INTERACTIVE TEST MODE ".center(80))
    print("=" * 80)
    print("\nTest session started at: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("Logs will be saved to: {}/".format(logger.log_dir))
    try:
        while True:
            display_main_menu()
            choice = input("\nEnter your choice: ").strip().lower()
            if choice in ("q", "quit", "exit"):
                print("\n[INFO] Exiting test mode...")
                break
            if choice.isdigit() and choice in TESTS:
                if not run_single_test(cmd_handler, int(choice), logger):
                    print("\n[INFO] Test sequence aborted by user.")
                    break
            else:
                print("[ERROR] Invalid input. Enter a test number or 'q'.")
    except KeyboardInterrupt:
        print("\n\n[INFO] Test session interrupted by user (Ctrl+C)")
    finally:
        print("\n" + "=" * 80)
        print(" GENERATING TEST SUMMARY ".center(80))
        print("=" * 80)
        logger.write_summary()
