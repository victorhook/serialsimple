from dataclasses import asdict, dataclass
import json
from pathlib import Path
from queue import Queue
from threading import Thread
import time
import tkinter as tk
from tkinter import ttk
from typing import List
from serial import Serial
from serial.tools import list_ports


APP_NAME = 'serialsimple'
APP_VERSION = '0.0.1'
APP_AUTHOR = 'Victor Krook'

TERMINATORS = {
    'LF': b'\n',
    'CR': b'\r',
    'CR_LF': b'\r\n',
    'LF_CR': b'\n\r'
}


@dataclass
class Settings:
    baud: int = 115200
    port: str = ''
    terminator: str = 'LF'
    geometry: str = '400x800'

    SETTINGS_PATH = Path(__file__).parent.joinpath('settings.json')

    def save(self) -> None:
        with open(self.SETTINGS_PATH, 'w') as f:
            json.dump(asdict(self), f, indent=4)

    @classmethod
    def open(cls) -> 'Settings':
        try:
            with open(cls.SETTINGS_PATH) as f:
                data = json.load(f)
                return Settings(**data)
        except Exception:
            settings = Settings()
            settings.save()
            return settings


class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self._setup()
        
        self.style = ttk.Style()
        self.style.theme_use('clam')

        self._serial: Serial = None

        self.settings = Settings.open()
        self.protocol("WM_DELETE_WINDOW", self._save_settings)

        self._baud = tk.StringVar()
        self._port = tk.StringVar()
        self._terminator = tk.StringVar()
        self._tx_var = tk.StringVar()
        self._tx_var.set('')
        self._baud.set(self.settings.baud)
        self._port.set(self.settings.port)
        self._terminator.set(self.settings.terminator)

        pad = {'padx': 5, 'pady': 5}

        self.frame_control = tk.Frame(self)
        self.combo_ports = ttk.Combobox(self.frame_control, state='readonly',
                                        textvariable=self._port)
        self.combo_terminators = ttk.Combobox(self.frame_control,
                                              state='readonly',
                                              values=list(TERMINATORS.keys()),
                                              textvariable=self._terminator)
        self.entry_baud = tk.Entry(self.frame_control, textvariable=self._baud)
        self.button_connect = tk.Button(self.frame_control, text='Connect',
                                        command=self._connect)
        self.button_disconnect = tk.Button(self.frame_control,
                                           text='Disonnect',
                                           command=self._disconnect)
        # Labels
        label_port = tk.Label(self.frame_control, text='Port')
        label_baud = tk.Label(self.frame_control, text='Baud')
        label_terminator = tk.Label(self.frame_control, text='Terminator')
        label_port.grid(row=0, column=0, **pad, sticky=tk.W)
        label_baud.grid(row=1, column=0, **pad, sticky=tk.W)
        label_terminator.grid(row=2, column=0, **pad, sticky=tk.W)
        # Input
        self.combo_ports.grid(row=0, column=1, **pad, sticky=tk.W)
        self.entry_baud.grid(row=1, column=1, **pad, sticky=tk.W)
        self.combo_terminators.grid(row=2, column=1, **pad, sticky=tk.W)
        # Buttons
        self.button_connect.grid(row=0, column=2, **pad)
        self.button_disconnect.grid(row=1, column=2, **pad)

        self.msgs = []
        self.msgs_i = 0

        # -- Main frame -- #
        self.frame_main = tk.Frame(self)
        self.output = tk.Text(self.frame_main)

        self.frame_send = tk.Frame(self.frame_main)
        
        self.entry_send = tk.Entry(self.frame_send, textvariable=self._tx_var)
        self.entry_send.bind('<Return>', lambda *_: self._send())
        self.entry_send.bind('<KeyPress-Down>', lambda *_: self._down())
        self.entry_send.bind('<KeyPress-Up>', lambda *_: self._up())
        self.c = ttk.Combobox(self.frame_send)
        self.button_send = tk.Button(self.frame_send, text='Send',
                                     command=self._send)
        self.entry_send.pack(side=tk.LEFT, expand=True, fill=tk.X, **pad)
        self.button_send.pack(side=tk.LEFT, **pad)
        self.c.pack(expand=True, fill=tk.X)
        
        self.ports: List[str] = []

        self.output.pack(expand=True, fill=tk.BOTH)
        self.frame_send.pack(fill=tk.BOTH)

        pad = {'padx': 10, 'pady': 20}
        self.frame_control.pack(**pad, anchor=tk.W)
        self.frame_main.pack(expand=True, fill=tk.BOTH, **pad)

        Thread(target=self._port_watcher, daemon=True).start()
        self._tx = Queue()

        # Setup
        self.iconbitmap(Path(__file__).parent.joinpath('app.ico'))
        self.title(f'{APP_NAME} - {APP_VERSION}')
        self.geometry(self.settings.geometry)
        self._update()
        self.mainloop()

    def _save_settings(self) -> None:
        self.settings.baud = int(self._baud.get())
        self.settings.port = self._port.get()
        self.settings.terminator = self._terminator.get()
        self.settings.geometry = self.geometry()
        self.settings.save()
        self._disconnect()
        self.destroy()

    def _set_msg_index(self, index: int) -> None:
        self.msgs_i = index
        if self.msgs_i >= len(self.msgs):
            self.msgs_i = len(self.msgs) - 1
        if self.msgs_i < 0:
            self.msgs_i = 0
        self._update()

    def _up(self) -> None:
        self._set_msg_index(self.msgs_i + 1)

    def _down(self) -> None:
        self._set_msg_index(self.msgs_i - 1)

    def _send(self) -> None:
        tx = self._tx_var.get()
        self.msgs.append(tx)
        self._update()
        if tx and self._serial is not None:
            self._tx.put(tx)
            self._tx_var.set('')

    def _connect(self) -> None:
        if self._serial is not None:
            return

        baud = int(self._baud.get())
        port = self._port.get()

        if not port:
            return

        self._serial = Serial(port, baud)
        print(f'Opened serial port {self._serial.port}')

        Thread(target=self._communicater, daemon=True).start()
        self._update()

    def _disconnect(self) -> None:
        if self._serial is None:
            return
        print(f'Closing serial port {self._serial.port}')
        self._serial.close()
        self._serial = None
        self._update()

    def _setup(self) -> None:
        pass

    def _update(self) -> None:
        self.c['values'] = list(reversed(self.msgs))
        if self.msgs:
            self.c.current(self.msgs_i)
        self.combo_ports['values'] = self.ports

        if self.ports and not self._port.get():
            self.combo_ports.current(0)

        self.button_connect.config(state='disabled')
        self.button_disconnect.config(state='disabled')
        if self._serial:
            self.button_disconnect.config(state='normal')
        else:
            self.button_connect.config(state='normal')

    # -- Threads -- #
    def _communicater(self) -> None:
        self._serial.timeout = 0
        try:
            while self._serial:
                data = self._serial.read()
                while data:
                    try:
                        data = data.decode('utf-8')
                    except UnicodeDecodeError:
                        data = repr(data)
                    self.output.insert(tk.END, data)
                    self.output.see(tk.END)
                    data = self._serial.read()

                term_tx = self._terminator.get()
                term_tx = TERMINATORS[term_tx]

                while not self._tx.empty():
                    tx = self._tx.get()
                    tx = tx.encode('utf-8')
                    self._serial.write(tx + term_tx)

                time.sleep(.05)

        except Exception:
            # Means we've probably disconnected
            pass

    def _port_watcher(self) -> None:
        while self._serial is None:
            ports = [port.device for port in list_ports.comports()]
            if ports != self.ports:
                self.ports = ports
                self._update()
            time.sleep(.1)


if __name__ == '__main__':
    app = App()
