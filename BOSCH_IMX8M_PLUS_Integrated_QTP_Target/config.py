"""BOSCH-IMX8M-PLUS target configuration constants."""

BOARD_NAME = "BOSCH-IMX8M-PLUS"
SRC_SBMR2_ADDR = "0x30390070"

# UART device paths.
X_UART1 = "/dev/ttymxc0"  # Debug console
X_UART3 = "/dev/ttymxc2"  # QTP console

QTP_CONSOLE = X_UART3
BAUDRATE = 115200

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
