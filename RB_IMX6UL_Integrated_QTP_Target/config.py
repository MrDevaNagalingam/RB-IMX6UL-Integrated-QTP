"""RB-IMX6UL target configuration constants."""

BOARD_NAME = "RB-IMX6UL"

# UART device paths from the user's latest board notes.
X_UART1 = "/dev/ttymxc0"  # debug console
X_UART2 = "/dev/ttymxc1"  # RS232 / QTP console
X_UART3 = "/dev/ttymxc2"  # MikroBUS and expansion header
X_UART5 = "/dev/ttymxc4"  # BLE and Wi-Fi
X_UART6 = "/dev/ttymxc5"  # RS485

QTP_CONSOLE = X_UART2
BAUDRATE = 115200

# ADC raw input paths from /sys/bus/iio/devices/iio:device0.
ADC1_GPIO1_1_IN1 = "/sys/bus/iio/devices/iio:device0/in_voltage1_raw"
ADC1_GPIO1_3_IN3 = "/sys/bus/iio/devices/iio:device0/in_voltage3_raw"
ADC1_VOLTAGE_SCALE = "/sys/bus/iio/devices/iio:device0/in_voltage_scale"

TARGET_LOG_DIR = "/home/root/qtp_logs"

DDR_TEST = "memtester 10M 1"
NAND_RW_TEST = "nandtest -k -p 1 -o 0x1e700000 -l 0xA00000 /dev/mtd2"
