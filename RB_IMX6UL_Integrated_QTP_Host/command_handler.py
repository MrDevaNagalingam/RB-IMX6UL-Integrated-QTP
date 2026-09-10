"""Host command lookup and target response parsing."""
import json
from uart_handler import UARTCommunicator

STATUSES = {"PASS", "FAIL", "ERROR", "NOT_CONFIGURED", "NOT_IMPLEMENTED", "ABORTED"}


class CommandHandler:
    def __init__(self, uart_comm: UARTCommunicator):
        self.uart = uart_comm
        self.commands = {
            "TEST_DDR": self.test_ddr,
            "TEST_NAND": self.test_nand,
            "TEST_UART1_DEBUG": self.test_uart1_debug,
            "TEST_UART2_RS232": self.test_uart2_rs232,
            "TEST_UART3_LOOPBACK": self.test_uart3_loopback,
            "TEST_UART5_BLE_WIFI": self.test_uart5_ble_wifi,
            "TEST_UART6_RS485_TX": self.test_uart6_rs485_tx,
            "TEST_UART6_RS485_TX_STOP": self.test_uart6_rs485_tx_stop,
            "TEST_UART6_RS485_RX": self.test_uart6_rs485_rx,
            "TEST_UART6_RS485_RX_STOP": self.test_uart6_rs485_rx_stop,
        }

    def execute_command(self, command_id, params=None, output_callback=None):
        if isinstance(command_id, str) and command_id in self.commands:
            return self.commands[command_id](params, output_callback)
        answer = {"test_id": command_id, "status": "NOT_IMPLEMENTED",
                  "measurements": {}, "details": "Unsupported host command", "output": ""}
        return answer

    def test_ddr(self, params=None, output_callback=None):
        """Host RAM test entry point; target runs memtester 10M 1."""
        return self._run_test("DDR_TEST", params, output_callback)

    def test_nand(self, params=None, output_callback=None):
        """Host NAND test entry point; target runs the configured nandtest region."""
        return self._run_test("NAND_RW_TEST", params, output_callback)

    def test_uart1_debug(self, params=None, output_callback=None):
        """UART1 is the debug console, so this test is intentionally aborted."""
        return self._run_test("UART1_DEBUG_TEST", params, output_callback)

    def test_uart2_rs232(self, params=None, output_callback=None):
        """UART2 is the QTP communication console, so this test is intentionally aborted."""
        return self._run_test("UART2_RS232_TEST", params, output_callback)

    def test_uart3_loopback(self, params=None, output_callback=None):
        """UART3 operator loopback/message verification."""
        return self._run_test("UART3_LOOPBACK_TEST", params, output_callback)

    def test_uart5_ble_wifi(self, params=None, output_callback=None):
        """UART5 BLE/Wi-Fi hardware is not mounted for this stage."""
        return self._run_test("UART5_BLE_WIFI_TEST", params, output_callback)

    def test_uart6_rs485_tx(self, params=None, output_callback=None):
        """RS485 transmit operator-message verification."""
        return self._run_test("UART6_RS485_TX_TEST", params, output_callback)

    def test_uart6_rs485_tx_stop(self, params=None, output_callback=None):
        """Close the UART6 transmit session."""
        return self._run_test("UART6_RS485_TX_STOP", params, output_callback)

    def test_uart6_rs485_rx(self, params=None, output_callback=None):
        """RS485 receive operator-confirmation verification."""
        return self._run_test("UART6_RS485_RX_TEST", params, output_callback)

    def test_uart6_rs485_rx_stop(self, params=None, output_callback=None):
        """Stop UART6 receive and return the collected data."""
        return self._run_test("UART6_RS485_RX_STOP", params, output_callback)

    def _run_test(self, command, params=None, output_callback=None):
        """Shared UART response validation and reporting for named test methods."""
        answer = {"test_id": command, "status": "ERROR", "measurements": {},
                  "details": "", "output": ""}
        try:
            raw = self.uart.send_and_receive(
                command, json.dumps(params) if params is not None else None, output_callback)
            parsed = json.loads(raw)
            if (not isinstance(parsed, dict) or parsed.get("test_id") != command
                    or parsed.get("status") not in STATUSES
                    or not isinstance(parsed.get("measurements"), dict)
                    or not isinstance(parsed.get("details"), str)
                    or not isinstance(parsed.get("output"), str)):
                raise ValueError("Invalid target result schema or test ID")
            answer = parsed
        except (OSError, TimeoutError, ValueError, TypeError) as exc:
            answer.update(status="ERROR", details=str(exc))
        except KeyboardInterrupt:
            answer.update(status="ERROR", details="Host interrupted; target may still be running")
            raise
        return answer

