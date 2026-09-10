# RB-IMX6UL Integrated QTP

Start the target UART server, then run the host and select a numbered test.
The host sends selected test commands over RS232, the target executes the test,
and the host displays the returned status/details and saves ESR0C-style text logs.
DDR, NAND and the first UART operator-verification tests are implemented.
The target main.py file only starts the UART server; target logic is split by role.

## Project structure

```text
RB-IMX6UL-Integrated-QTP/
|-- RB_IMX6UL_Integrated_QTP_Host/
|   |-- main.py
|   |-- command_handler.py
|   |-- uart_handler.py
|   |-- interactive_menu.py
|   '-- requirements.txt
|-- RB_IMX6UL_Integrated_QTP_Target/
|   |-- main.py
|   |-- config.py
|   |-- dispatcher.py
|   |-- tests.py
|   |-- requirements.txt
|   '-- gpio.py
|-- docs/
|   |-- hardware_mapping.md
|   '-- test_matrix.md
'-- README.md
```

Host main owns startup and cleanup; uart_handler owns transport and protocol;
interactive_menu owns the numbered TESTS menu that the operator sees;
command_handler owns the host command lookup, results and reporting.
Target main owns only startup; dispatcher owns pack/unpack, UART frame reading
and command dispatch; config owns hardware settings; tests owns RAM/NAND tests;
gpio is reserved for future GPIO operations.
No additional Python modules or qtp package are planned.

## Reference and source notes

Behavior reference (unchanged):
`C:\Deva_Workspace\Training\Signify\ESR0C\__git\ESR0C\ESR0C-Integrated-QTP`.

Its host main imports UARTCommunicator, CommandHandler and the enhanced
interactive menu, then connects, runs the menu and disconnects.
This project follows that active workflow, with the numbered menu and reporting
in the requested host modules and a thin target main.py. The inspected sources were host main.py,
qtp/uart_comm.py, qtp/command_handler.py, qtp/interactive_menu_enhanced.py,
and target main.py and protocol.py. Legacy *_working.py files are not used.

Wire format matches the active ESR0C V2 encoder: AA, big-endian uint16 payload
length, big-endian uint16 checksum (sum(payload) % 0xFFFF), TLV payload, BB.
Each TLV has a one-byte type and two-byte length. Type 1 carries a command;
type 2 carries a response, type 4 carries live output chunks, and type 5 carries
JSON parameters for operator-entered messages. RB responses contain JSON so
statuses are preserved exactly. RB adds type 3 for a request ID echoed in the
response, preventing stale results from being assigned to a later request. Use the RB host and target
together: framing compatibility does not imply ESR0C application interchangeability.
Target protocol helpers remain in dispatcher.py and host helpers in uart_handler.py.

Test-case source:
`C:\Deva_Workspace\Training\RB-imx6ul\imx6ul_testcases\imx6ul_testcases`.
These files are reference material, not implemented or validated tests.

## Wiring and startup

Connect the host through a USB-to-RS232 adapter to X_UART2. Confirm TX/RX/GND
and the connector pinout. Keep X_UART1 (/dev/ttymxc0) for the debug shell.
Both QTP endpoints default to 115200 baud, 8 data bits, no parity, one stop bit,
no flow control. Ensure no login service or other application uses X_UART2.

Use Python 3.7+ and pyserial 3.5 on both sides. Target also needs memtester and mtd-utils (nandtest)
utilities. Include these utilities in the Yocto image, or install the corresponding
packages through the image's package manager. The board's package manager and
Python version remain to be confirmed; no package-manager command is assumed.

Copy RB_IMX6UL_Integrated_QTP_Target to the board. From that directory, install
pyserial if it is not provided by the BSP, then start the server through the debug
console or SSH as root:

```sh
python3 -m pip install pyserial==3.5
python3 main.py
```

The server listens on /dev/ttymxc1; it waits for host commands and stays running
after each test. Override the configured link if needed with
`python3 main.py --port /dev/ttymxc1 --baud 115200`.
For images without pip, include python3-pyserial in the BSP image instead.

On the PC, open RB_IMX6UL_Integrated_QTP_Host and run:

```powershell
python -m pip install -r requirements.txt
python main.py COM4
```

Replace COM4 with the adapter's actual COM port. On Linux, use
`python3 main.py /dev/ttyUSB0`. The menu offers:

```text
1. DDR Functionality
2. NAND Flash Functionality
3. UART1 Debug Console Verification
4. RS232 UART2 Verification
5. UART3 Loopback Verification
6. BLE & WiFi UART5 Verification
7. RS485 UART6 Transmit Test
8. RS485 UART6 Transmit Stop
9. RS485 UART6 Receive Test
10. RS485 UART6 Receive Stop
q. Quit
```

The visible menu entries are defined in interactive_menu.py:

```python
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
```

Enter a test number to run that test on the board. The selected host command is handed
to command_handler.py, where TEST_DDR calls test_ddr() and sends DDR_TEST;
TEST_NAND calls test_nand() and sends NAND_RW_TEST. UART menu entries map to
UART1_DEBUG_TEST, UART2_RS232_TEST, UART3_LOOPBACK_TEST, UART5_BLE_WIFI_TEST,
UART6_RS485_TX_TEST, UART6_RS485_TX_STOP, UART6_RS485_RX_TEST and
UART6_RS485_RX_STOP. The host waits for completion
and shows status and details, then returns to the menu.
Before the DDR command is sent, the host prints `This test may take some time.`
Missing utilities or an unsuitable NAND region are
reported as NOT_CONFIGURED by the target.
UART1 and UART2 return ABORTED because they are already used as the debug console
and QTP communication console. UART5 returns ABORTED until BLE/WiFi hardware is
mounted. UART3 performs a physical TX-to-RX loopback comparison. Test 7 opens
UART6 and transmits the entered message; test 8 closes the transmit session.
Test 9 opens UART6 and starts a background receiver. Test 10 stops receive,
closes UART6 and reports all collected data.

DDR_TEST runs `memtester 10M 1`. NAND_RW_TEST runs
`nandtest -k -p 1 -o 0x1e700000 -l 0xA00000 /dev/mtd2`.
The exact command strings are in target config.py:

```python
X_UART1 = "/dev/ttymxc0"
X_UART2 = "/dev/ttymxc1"
X_UART3 = "/dev/ttymxc2"
X_UART5 = "/dev/ttymxc4"
X_UART6 = "/dev/ttymxc5"
QTP_CONSOLE = X_UART2
BAUDRATE = 115200

ADC1_GPIO1_1_IN1 = "/sys/bus/iio/devices/iio:device0/in_voltage1_raw"
ADC1_GPIO1_3_IN3 = "/sys/bus/iio/devices/iio:device0/in_voltage3_raw"
ADC1_VOLTAGE_SCALE = "/sys/bus/iio/devices/iio:device0/in_voltage_scale"

DDR_TEST = "memtester 10M 1"
NAND_RW_TEST = "nandtest -k -p 1 -o 0x1e700000 -l 0xA00000 /dev/mtd2"
```

Commands are sent once; they are not automatically repeated. Host Ctrl+C closes the connection and saves
the summary; it does not cancel a running target test. Check the debug console
and allow an active test to finish before starting another session.

Host logs are saved under test_log/ relative to the host working directory:
test_log_<timestamp>.txt contains the ESR0C-style detailed execution log;
test_summary_<timestamp>.txt contains counts and per-test status/details.
Use --report-dir to change the output directory. Target command output is saved
on the board under /home/root/qtp_logs/.
DDR output is streamed live to the host while memtester runs. Target command
logs stay on the board under /home/root/qtp_logs/. Other UART responses return
status, measurements and the ESR0C-style details block.
The host process exit code reflects startup/runtime errors, not aggregate test
results; use the summary for pass/fail decisions.

NAND writes the configured 10 MiB region, from 0x1e700000 to 0x1f100000
(exclusive), relative to /dev/mtd2. Use an offline, reserved test region with no
other users. The runner rejects mounted/UBI-attached devices and invalid geometry;
these checks cannot prove the region contains no needed offline data.
The -k option restores contents after testing, but interruption, power loss or
failure can leave contents unrestored. Back up needed data first.

Review docs/hardware_mapping.md before adding each test. Agree its command,
prerequisites, procedure and acceptance criteria in docs/test_matrix.md, then
add the host command/menu entry, target dispatcher route and target test function
incrementally.
Results distinguish PASS, FAIL, ERROR, ABORTED, NOT_CONFIGURED and NOT_IMPLEMENTED.
The supplied board transcripts show successful manual runs. This new runner has
not been hardware-validated; local checks use mocked utilities and device metadata.
The menu-to-target-to-report flow was checked using a fragmented simulated serial
link and mocked memtester/nandtest. Frames matched the reference's active encoder.
Checks also cover malformed frames, stale request IDs and cleanup.
