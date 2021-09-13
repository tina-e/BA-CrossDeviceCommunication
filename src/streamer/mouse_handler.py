import errno
import subprocess
import time
from wmctrl import Window
from event_types import get_device_by_button
from evdev import UInput, ecodes, AbsInfo, InputDevice


class EventHandlerEvdev():
    def __init__(self, configurator):
        self.config = configurator
        self.cap_mouse = {
            ecodes.EV_KEY: [ecodes.KEY_POWER, ecodes.BTN_LEFT, ecodes.BTN_MOUSE, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE],
            ecodes.EV_REL: [ecodes.REL_WHEEL],
            ecodes.EV_ABS: [
                (ecodes.ABS_X, AbsInfo(value=0, min=0, max=self.config.RESOLUTION_X, fuzz=0, flat=0, resolution=31)),
                (ecodes.ABS_Y, AbsInfo(0, 0, self.config.RESOLUTION_Y, 0, 0, 31)),
                (ecodes.ABS_PRESSURE, AbsInfo(0, 0, 4000, 0, 0, 31))],
        }
        self.mouse_ui = None
        self.key_ui = None
        self.dropping = False

    def create_device(self):
        self.mouse_ui = UInput(self.cap_mouse, name='mouse', version=0x3)
        self.key_ui = UInput.from_device(InputDevice(self.config.KEYBOARD_DEVICE_PATH), InputDevice(self.config.MOUSE_DEVICE_PATH), name='key')

        subprocess.check_output("xinput create-master master", shell=True)
        self.master_pointer_id = subprocess.check_output("xinput list --id-only 'master pointer'", shell=True).strip().decode()
        self.master_keyboard_id = subprocess.check_output("xinput list --id-only 'master keyboard'", shell=True).strip().decode()

        self.mouse_id = subprocess.check_output(f"xinput list --id-only 'pointer:mouse'", shell=True).strip().decode()
        self.click_id = subprocess.check_output(f"xinput list --id-only 'keyboard:mouse'", shell=True).strip().decode()
        self.scroll_id = subprocess.check_output(f"xinput list --id-only 'pointer:key'", shell=True).strip().decode()
        self.key_id = subprocess.check_output(f"xinput list --id-only 'keyboard:key'", shell=True).strip().decode()

        subprocess.check_output(f"xinput reattach {self.mouse_id} {self.master_pointer_id}", shell=True)
        subprocess.check_output(f"xinput reattach {self.scroll_id} {self.master_pointer_id}", shell=True)
        subprocess.check_output(f"xinput reattach {self.click_id} {self.master_keyboard_id}", shell=True)
        subprocess.check_output(f"xinput reattach {self.key_id} {self.master_keyboard_id}", shell=True)

        self.map_mouse_movement(0, 0)

    def map_mouse_movement(self, x, y):
        try:
            x = x + self.config.START_X
            y = y + self.config.START_Y
            self.mouse_ui.write(ecodes.EV_ABS, ecodes.ABS_X, x)
            self.mouse_ui.write(ecodes.EV_ABS, ecodes.ABS_Y, y)
            self.mouse_ui.syn()
            time.sleep(0.006)
        except OSError as err:
            if err.errno == errno.EBADFD:
                return

    def map_mouse_click(self, x, y, button, was_pressed):
        self.mouse_ui.write(ecodes.EV_KEY, get_device_by_button(button), was_pressed)
        if not was_pressed: self.key_ui.syn()

    def map_mouse_scroll(self, dx, dy):
        self.mouse_ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, dy)
        self.key_ui.syn()

    def map_keyboard(self, key, value):
        self.key_ui.write(ecodes.EV_KEY, key, value)
        if value != 1: self.key_ui.syn()

    def simulate_drop(self, x_drop, y_drop):
        self.dropping = True
        time.sleep(1)
        dragon_wins = Window.by_name('dragon')
        print(dragon_wins)
        dragon_win = dragon_wins[0]
        x_drag = int(dragon_win.x + (dragon_win.w / 2))
        y_drag = int(dragon_win.y + (dragon_win.h / 2))

        self.mouse_ui.write(ecodes.EV_ABS, ecodes.ABS_X, x_drag)
        self.mouse_ui.write(ecodes.EV_ABS, ecodes.ABS_Y, y_drag)
        self.mouse_ui.syn()
        time.sleep(1)

        self.mouse_ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
        self.mouse_ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 2)
        self.mouse_ui.syn()
        time.sleep(1)

        self.mouse_ui.write(ecodes.EV_ABS, ecodes.REL_X, (x_drop + self.config.START_X) - x_drag)
        self.mouse_ui.write(ecodes.EV_ABS, ecodes.REL_Y, (y_drop + self.config.START_Y) - y_drag)
        self.mouse_ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 2)
        self.mouse_ui.syn()

        self.mouse_ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 2)
        self.mouse_ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
        self.mouse_ui.syn()
        time.sleep(0.006)
        self.dropping = False

    def remove_device(self):
        self.mouse_ui.close()
        self.key_ui.close()
        subprocess.check_output(f"xinput remove-master {self.master_pointer_id}", shell=True)
