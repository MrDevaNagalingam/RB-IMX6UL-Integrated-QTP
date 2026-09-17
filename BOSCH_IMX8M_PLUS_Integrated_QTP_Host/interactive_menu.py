"""Interactive menu and text logging for BOSCH-IMX8M-PLUS QTP."""
from datetime import datetime
import os
import re

TESTS = {
    "14": ("TC-10 TPM functionality", "TEST_TPM"),
    "15": ("TC-11 PCIe controller verify", "TEST_PCIE"),
    "13": ("TC-09 USB Bluetooth (USB1, USB2)", "TEST_USB_BLUETOOTH"),
    "11": ("TC-07 CAN0 and CAN1 Loopback test", "TEST_CAN_LOOPBACK"),
    "12": ("TC-08 HDMI Test case", "TEST_HDMI"),
    "9": ("TC-06 Ethernet0 throughput test pin no.(X8)", "TEST_ETHERNET0"),
    "10": ("TC-06 Ethernet1 throughput test pin no.(X9)", "TEST_ETHERNET1"),
    "5": ("TC-05 Indication LED1 Pin no.(GPIO2_IO06)", "TEST_LED1"),
    "6": ("TC-05 Indication LED2 Pin no.(GPIO2_IO07)", "TEST_LED2"),
    "7": ("TC-05 Indication LED3 Pin no.(GPIO2_IO08)", "TEST_LED3"),
    "8": ("TC-05 Indication LED4 Pin no.(GPIO2_IO09)", "TEST_LED4"),
    "4": ("TC-04 SD Card Write/ Read / Delete", "TEST_SD_CARD_RW_DELETE"),
    "1": ("TC-01 Boot mode", "TEST_BOOT_MODE"),
    "2": ("TC-02 UART1 Debug Console", "TEST_UART1_DEBUG_CONSOLE"),
    "3": ("TC-03 Reset Switch (S1)", "TEST_RESET_SWITCH"),
}

TEST_MESSAGES = {
    "TEST_TPM": "Checks TPM devices, random generation, and RSA encryption/decryption with data verification.",
    "TEST_PCIE": "Checks the PCIe bridge and its active kernel driver using lspci -k.",
    "TEST_USB_BLUETOOTH": "Connect the Bluetooth adapter to the USB port being tested. Make a nearby Bluetooth device discoverable.",
    "TEST_HDMI": "Connect the HDMI cable to test. Observe the test patterns on the connected display.",
    "TEST_CAN_LOOPBACK": "Connect CAN0 and CAN1 on a correctly terminated CAN bus. Tests both directions at 500000 bit/s.",
    "TEST_SD_CARD_RW_DELETE": "SD card: five 10 MiB write/read/delete cycles with SHA256 verification.",
    "TEST_BOOT_MODE": "Reads SRC_SBMR2 and decodes BOOT_MODE[3:0].",
    "TEST_UART1_DEBUG_CONSOLE": "UART1 is used for the debug console.",
    "TEST_RESET_SWITCH": (
        "Press reset button S1. Observe the debug console and wait for the "
        "board to complete the cold-start boot sequence."
    ),
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
        completed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = """
Result: {0}
Details: {1}
Working as Expected: {2}
Completed: {3}
{4}

""".format(status, cleaned_details, acknowledgment,
           completed, "=" * 80)
        with open(self.log_file, "a", encoding="utf-8") as stream:
            stream.write(log_entry)
        if len(cleaned_details) > 1200 or cleaned_details.count("\n") > 25:
            print("\nResult: {}\nDetails: [large output saved in {}]\n"
                  "Working as Expected: {}\nCompleted: {}\n{}\n".format(
                      status, self.log_file, acknowledgment, completed, "=" * 80))
        else:
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
    for number, (title, command) in sorted(TESTS.items(), key=lambda item: int(item[0])):
        print("{:2d}. {}".format(int(number), title))
    print("\n" + "=" * 80)
    print(" OPTIONS ".center(80))
    print("=" * 80)
    print("  Enter test number (1-{})".format(len(TESTS)))
    print("  Enter 'q' to quit")
    print("=" * 80)


def collect_test_params(test_cmd):
    return None


def confirm_working_as_expected(prompt="Is this test working as expected? (y/n): "):
    while True:
        answer = input(prompt).strip().lower()
        if answer in ("y", "yes", "n", "no"):
            return answer in ("y", "yes")
        print("[ERROR] Enter YES or NO.")


def run_single_test(cmd_handler, test_num, logger):
    key = str(test_num)
    if key not in TESTS:
        print("[ERROR] Test #{} not found!".format(test_num))
        return True
    test_desc, test_cmd = TESTS[key]
    operator_decides_status = test_cmd in ("TEST_LED1", "TEST_LED2", "TEST_LED3", "TEST_LED4", "TEST_HDMI")
    logger.log_test_start(test_num, test_desc, test_cmd)
    if test_cmd in TEST_MESSAGES:
        print("[INFO] {}".format(TEST_MESSAGES[test_cmd]))
    print("\n[EXECUTING] Running test: {}".format(test_cmd))
    try:
        # The board reboots during this manual test, so no target reply is expected.
        if test_cmd == "TEST_RESET_SWITCH":
            print("\n" + "-" * 80)
            working_as_expected = confirm_working_as_expected(
                "After checking the reset test, is it working as expected? (YES/NO): ")
            status = "PASS" if working_as_expected else "FAIL"
            details = "{}\nOperator reported reset test: {}.".format(
                TEST_MESSAGES[test_cmd], status)
            print("\n" + "=" * 80)
            logger.log_test_result(test_num, test_desc, status, details, status == "PASS")
            return True

        streamed = []

        def show_live_output(text):
            streamed.append(text)
            print(text, end="", flush=True)

        params = collect_test_params(test_cmd)
        result = cmd_handler.execute_command(
            test_cmd, params=params, output_callback=show_live_output)
        if result is None:
            result = {"status": "ABORTED", "details": "Command returned no result", "output": ""}
        target_status = result.get("status", "UNKNOWN")
        details = result.get("details", "No details provided")
        display_details = logger.sanitize(details)
        if test_cmd not in ("TEST_ETHERNET0", "TEST_ETHERNET1"):
            print("[RESULT] Status: {}".format(
                "AWAITING OPERATOR" if operator_decides_status and target_status == "PASS" else target_status))
            print("[RESULT] Details: {}".format(display_details))
        if test_cmd in ("TEST_SD_CARD_RW_DELETE", "TEST_HDMI", "TEST_CAN_LOOPBACK", "TEST_USB_BLUETOOTH", "TEST_TPM", "TEST_PCIE"):
            log_file = result.get("measurements", {}).get("log_file")
            if log_file:
                print("\nLog file Location: {}".format(log_file))
                details += "\nLog file Location: " + log_file
        if test_cmd in ("TEST_SD_CARD_RW_DELETE", "TEST_CAN_LOOPBACK", "TEST_HDMI") and result.get("output"):
            details = result["output"] + "\n" + details
        if test_cmd in ("TEST_ETHERNET0", "TEST_ETHERNET1") and streamed:
            details = "".join(streamed) + "\n" + details

        print("\n" + "-" * 80)
        working_as_expected = confirm_working_as_expected(
            "After checking the HDMI display, is it working as expected? (YES/NO): "
            if test_cmd == "TEST_HDMI" else "Is this test working as expected? (y/n): ")
        if operator_decides_status and target_status == "PASS":
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
                print("\n[INFO] Sending stop command to target...")
                stop_result = cmd_handler.execute_command("STOP_TARGET")
                if stop_result.get("status") == "PASS":
                    print("[QTP] Target stopped.")
                else:
                    print("[QTP] Target stop failed: {}".format(
                        logger.sanitize(stop_result.get("details", "Unknown error"))))
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
