"""Host command lookup and target response parsing."""
import json
from uart_handler import UARTCommunicator

STATUSES = {"PASS", "FAIL", "ERROR", "NOT_CONFIGURED", "NOT_IMPLEMENTED", "ABORTED"}


class CommandHandler:
    def __init__(self, uart_comm: UARTCommunicator):
        self.uart = uart_comm
        self.commands = {
            "STOP_TARGET": self.stop_target,
            "GET_RTC_TIME": self.get_rtc_time,
            "TEST_DDR": self.test_ddr,
            "TEST_NAND": self.test_nand,
            "TEST_UART1_DEBUG": self.test_uart1_debug,
            "TEST_UART2_RS232": self.test_uart2_rs232,
            "TEST_UART3_LOOPBACK": self.test_uart3_loopback,
            "TEST_UART5_BLE_WIFI": self.test_uart5_ble_wifi,
            "TEST_UART6_RS485": self.test_uart6_rs485,
            "TEST_RTC_I2C_POWER_BACKUP": self.test_rtc_i2c_power_backup,
            "TEST_I2C_INTERFACE": self.test_i2c_interface,
            "TEST_USER_LED1": self.test_user_led1,
            "TEST_USER_LED2": self.test_user_led2,
            "TEST_USER_SWITCH": self.test_user_switch,
            "TEST_ADC_CHANNEL_READING": self.test_adc_channel_reading,
        }

    def execute_command(self, command_id, params=None, output_callback=None):
        if isinstance(command_id, str) and command_id in self.commands:
            return self.commands[command_id](params, output_callback)
        answer = {"test_id": command_id, "status": "NOT_IMPLEMENTED",
                  "measurements": {}, "details": "Unsupported host command", "output": ""}
        return answer

    def stop_target(self, params=None, output_callback=None):
        """Tell the target QTP server to stop."""
        return self._run_test("STOP_QTP", params, output_callback)

    def get_rtc_time(self, params=None, output_callback=None):
        """Read target RTC time before operator confirmation."""
        return self._run_test("GET_RTC_TIME", params, output_callback)

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

    def test_uart6_rs485(self, params=None, output_callback=None):
        """RS485 UART6 transmit and receive verification."""
        return self._run_test("UART6_RS485_TEST", params, output_callback)

    def test_rtc_i2c_power_backup(self, params=None, output_callback=None):
        """Verify RTC time and update it when requested by the operator."""
        return self._run_test("RTC_I2C_POWER_BACKUP_TEST", params, output_callback)

    def test_i2c_interface(self, params=None, output_callback=None):
        """Verify expected devices on I2C buses 0 and 1."""
        return self._run_test("I2C_INTERFACE_TEST", params, output_callback)

    def test_user_led1(self, params=None, output_callback=None):
        """Toggle indication User LED1."""
        return self._run_test("USER_LED1_TEST", params, output_callback)

    def test_user_led2(self, params=None, output_callback=None):
        """Toggle indication User LED2."""
        return self._run_test("USER_LED2_TEST", params, output_callback)

    def test_user_switch(self, params=None, output_callback=None):
        """Verify the active-low User Switch input transition."""
        return self._run_test("USER_SWITCH_TEST", params, output_callback)

    def test_adc_channel_reading(self, params=None, output_callback=None):
        """Read ADC1 channels 1 and 3 with their IIO scale."""
        return self._run_test("ADC_CHANNEL_READING_TEST", params, output_callback)

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

