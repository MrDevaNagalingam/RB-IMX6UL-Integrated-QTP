# Hardware mapping

Board: BOSCH-IMX8M-PLUS. Revision and running BSP version: unconfirmed.

| Signal | Role | Linux device / address | Evidence |
|---|---|---|---|
| UART3 | QTP console | `/dev/ttymxc2` | User request |
| SRC_SBMR2 | Boot-mode status register | `0x30390070` | User sample code |

QTP uses 115200 baud, 8N1, no flow control by default. The host serial port is
selected at startup.

TC-01 reads `SRC_SBMR2` with `devmem2` and decodes `BOOT_MODE[3:0]` from bits
`[27:24]`.
