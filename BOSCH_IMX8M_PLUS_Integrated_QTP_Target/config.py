"""BOSCH-IMX8M-PLUS target configuration constants."""

BOARD_NAME = "BOSCH-IMX8M-PLUS"
SRC_SBMR2_ADDR = "0x30390070"

# UART device paths.
X_UART1 = "/dev/ttymxc0"  # Debug console
X_UART3 = "/dev/ttymxc2"  # QTP console

QTP_CONSOLE = X_UART3
BAUDRATE = 115200

BT_HCI = "hci0"
BT_USB_ID = "0cf3:e500"
BT_SCAN_SECONDS = 15
BT_SERVICE = "bluetooth.service"
BT_CONTROLLER_TIMEOUT = 20
BT_LOG_FILE = "/qtp_log/usb_bluetooth.txt"

TPM_DEVICES = ("/dev/tpm0", "/dev/tpmrm0")
TPM_TCTI = "device:/dev/tpmrm0"
TPM_COMMAND_TIMEOUT = 60
TPM_RANDOM_BYTES = 16
TPM_TEST_TEXT = "My Secret Password\n"
TPM_LOG_FILE = "/qtp_log/tpm.txt"
PCIE_DEVICE = "00:00.0"
PCIE_VENDOR = "Synopsys"
PCIE_DRIVER = "pcieport"
PCIE_COMMAND_TIMEOUT = 15
PCIE_LOG_FILE = "/qtp_log/pcie.txt"

HDMI_FBTEST_TIMEOUT = 120
HDMI_LOG_FILE = "/qtp_log/hdmi.txt"
CAN_LOG_FILE = "/qtp_log/can_test.txt"
HDMI_WESTON_SERVICE = "weston.service"
HDMI_WESTON_SOCKET = "weston.socket"

CAN_INTERFACES = ("can0", "can1")
CAN_BITRATE = 500000
CAN_RX_TIMEOUT = 5
CAN_TEST_FRAMES = ("123#1122334455667788", "456#AABBCCDDEEFF0011")

ETH_INTERFACES = {0: "eth0", 1: "eth1"}
ETH_DURATION = 60
ETH_PORT = 5201
ETH_INTERVAL = 10
ETH_LINK_TIMEOUT = 10
ETH_MIN_MBPS = 0  # No board-specific throughput threshold supplied.

SD_DEVICE = "/dev/mmcblk1p5"
SD_MOUNT_POINT = "/mnt/sd_test"
SD_FILE_SIZE = 10 * 1024 * 1024
SD_CHUNK_SIZE = 1024 * 1024
SD_ITERATIONS = 5
SD_LOG_FILE = "/qtp_log/sd_card.txt"

LED_ON_TIME = 2
LED_OFF_TIME = 2
LEDS = {
    "led1": {
        "path": "/sys/class/leds/led1",
        "gpio": "GPIO2_IO06",
        "gpiochip": "gpiochip1",
        "line": 6,
    },
    "led2": {
        "path": "/sys/class/leds/led2",
        "gpio": "GPIO2_IO07",
        "gpiochip": "gpiochip1",
        "line": 7,
    },
    "led3": {
        "path": "/sys/class/leds/led3",
        "gpio": "GPIO2_IO08",
        "gpiochip": "gpiochip1",
        "line": 8,
    },
    "led4": {
        "path": "/sys/class/leds/led4",
        "gpio": "GPIO2_IO09",
        "gpiochip": "gpiochip1",
        "line": 9,
    },
}
