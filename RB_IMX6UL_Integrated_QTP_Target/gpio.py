"""GPIO sysfs operations shared by target tests."""
from pathlib import Path
import time


def prepare_output(gpio_path):
    path = Path(gpio_path)
    if not path.name.startswith("gpio") or not path.name[4:].isdigit():
        raise ValueError("Invalid GPIO sysfs path: " + str(path))
    if not path.exists():
        Path("/sys/class/gpio/export").write_text(path.name[4:], encoding="ascii")
        deadline = time.monotonic() + 1.0
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
    if not path.exists():
        raise OSError("GPIO path was not created: " + str(path))
    path.joinpath("direction").write_text("out", encoding="ascii")
    return path


def toggle_output(gpio_path, seconds=2, output_callback=None):
    path = prepare_output(gpio_path)
    value_path = path / "value"
    value_path.write_text("0", encoding="ascii")
    if output_callback is not None:
        output_callback("[GPIO] {} ON for {} seconds\n".format(path.name, seconds))
    time.sleep(seconds)
    value_path.write_text("1", encoding="ascii")
    if output_callback is not None:
        output_callback("[GPIO] {} OFF for {} seconds\n".format(path.name, seconds))
    time.sleep(seconds)
    return {"gpio": int(path.name[4:]), "on_seconds": seconds, "off_seconds": seconds}


def prepare_input(gpio_path):
    path = Path(gpio_path)
    if not path.name.startswith("gpio") or not path.name[4:].isdigit():
        raise ValueError("Invalid GPIO sysfs path: " + str(path))
    if not path.exists():
        Path("/sys/class/gpio/export").write_text(path.name[4:], encoding="ascii")
        deadline = time.monotonic() + 1.0
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
    if not path.exists():
        raise OSError("GPIO path was not created: " + str(path))
    path.joinpath("direction").write_text("in", encoding="ascii")
    return path


def wait_for_active_low_press(gpio_path, output_callback=None):
    path = prepare_input(gpio_path)
    value_path = path / "value"
    if value_path.read_text(encoding="ascii").strip() == "0":
        if output_callback is not None:
            output_callback("[GPIO] Release the User Switch.\n")
        while value_path.read_text(encoding="ascii").strip() != "1":
            time.sleep(0.05)
    if output_callback is not None:
        output_callback("[GPIO] Press the User Switch now.\n")
    while value_path.read_text(encoding="ascii").strip() != "0":
        time.sleep(0.05)
    time.sleep(0.05)
    if value_path.read_text(encoding="ascii").strip() != "0":
        raise OSError("User Switch input did not remain active after debounce.")
    if output_callback is not None:
        output_callback("[GPIO] User Switch pressed: value=0\n")
    return {"gpio": int(path.name[4:]), "released_value": 1, "pressed_value": 0}
