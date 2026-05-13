"""Arduino settings tab for the game editor."""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
from PIL import Image
import sys

from .screens_tab import ScreensTab # Dummy import for order if needed, but we need get_project_root
from ...utils import get_project_root, pil_to_tkphoto

# Proje kökünü yola ekle (arduino.py için)
project_root = get_project_root()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import arduino

FIRMWARE_CODE = """// PhysicsCatchGame Arduino Firmware
const int PIN_BIP = 10;
const int PIN_DOGRU_GREEN = 11;
const int PIN_DOGRU_YELLOW = 12;
const int PIN_YANLIS_RED = 13;
const int PIN_POT = A0;

void setup() {
  Serial.begin(9600);
  pinMode(PIN_BIP, OUTPUT);
  pinMode(PIN_DOGRU_GREEN, OUTPUT);
  pinMode(PIN_DOGRU_YELLOW, OUTPUT);
  pinMode(PIN_YANLIS_RED, OUTPUT);
}

void loop() {
  // Potentiometer reading
  int potValue = analogRead(PIN_POT);
  Serial.print("POT:");
  Serial.println(potValue);

  // Serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\\n');
    command.trim();

    if (command == "BIP") {
      digitalWrite(PIN_BIP, HIGH);
      delay(100);
      digitalWrite(PIN_BIP, LOW);
    } 
    else if (command == "DOGRU") {
      for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_DOGRU_YELLOW, HIGH);
        delay(200);
        digitalWrite(PIN_DOGRU_YELLOW, LOW);
        delay(200);
      }
      digitalWrite(PIN_DOGRU_GREEN, HIGH);
      delay(500);
      digitalWrite(PIN_DOGRU_GREEN, LOW);
    } 
    else if (command == "YANLIS") {
      digitalWrite(PIN_YANLIS_RED, HIGH);
      digitalWrite(PIN_DOGRU_YELLOW, HIGH);
      digitalWrite(PIN_DOGRU_GREEN, HIGH);
      delay(1000);
      digitalWrite(PIN_YANLIS_RED, LOW);
      digitalWrite(PIN_DOGRU_YELLOW, LOW);
      digitalWrite(PIN_DOGRU_GREEN, HIGH); 
      delay(500);
      digitalWrite(PIN_DOGRU_GREEN, LOW);
    }
  }
  delay(100); 
}
"""

class ArduinoTab:
    """Tab for managing Arduino settings and testing."""
    
    def __init__(self, parent, game_service):
        self.parent = parent
        self.game_service = game_service
        self.frame = ttk.Frame(parent)
        self.current_game_id = None
        self._project_root = project_root
        
        self.monitor_running = False
        self.monitor_thread = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Left side: Firmware and Schematic
        left_frame = ttk.Frame(self.frame, padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(left_frame, text="Arduino Firmware (C++)", style="Subheader.TLabel").pack(anchor="w")
        
        code_frame = ttk.Frame(left_frame)
        code_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.code_text = tk.Text(code_frame, height=15, font=("Courier New", 9), wrap="none",
                                background="#1e1e1e", foreground="#d4d4d4", insertbackground="white")
        self.code_text.insert("1.0", FIRMWARE_CODE)
        self.code_text.config(state="disabled")
        
        code_scroll_y = ttk.Scrollbar(code_frame, orient="vertical", command=self.code_text.yview)
        code_scroll_x = ttk.Scrollbar(code_frame, orient="horizontal", command=self.code_text.xview)
        self.code_text.configure(yscrollcommand=code_scroll_y.set, xscrollcommand=code_scroll_x.set)
        
        self.code_text.grid(row=0, column=0, sticky="nsew")
        code_scroll_y.grid(row=0, column=1, sticky="ns")
        code_scroll_x.grid(row=1, column=0, sticky="ew")
        code_frame.columnconfigure(0, weight=1)
        code_frame.rowconfigure(0, weight=1)
        
        ttk.Button(left_frame, text="Kodu Kopyala", command=self._copy_code).pack(pady=5)
        
        # Schematic
        ttk.Label(left_frame, text="Bağlantı Şeması", style="Subheader.TLabel").pack(anchor="w", pady=(10, 0))
        self.schematic_canvas = tk.Canvas(left_frame, width=400, height=300, background="#2b2b2b", highlightthickness=0)
        self.schematic_canvas.pack(fill=tk.BOTH, expand=True, pady=5)
        self._load_schematic()

        # Right side: Settings and Test
        right_frame = ttk.Frame(self.frame, padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Settings
        settings_group = ttk.LabelFrame(right_frame, text="Bağlantı Ayarları", padding=10)
        settings_group.pack(fill=tk.X, pady=5)
        
        ttk.Label(settings_group, text="Port:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(settings_group, textvariable=self.port_var, values=arduino.get_available_ports())
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        
        ttk.Label(settings_group, text="Baud Rate:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.baud_var = tk.StringVar(value="9600")
        self.baud_combo = ttk.Combobox(settings_group, textvariable=self.baud_var, values=["9600", "115200", "57600"])
        self.baud_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        
        ttk.Button(settings_group, text="Portları Yenile", command=self._refresh_ports).grid(row=2, column=0, pady=5)
        self.connect_btn = ttk.Button(settings_group, text="Bağlan", command=self._toggle_connection)
        self.connect_btn.grid(row=2, column=1, pady=5)
        
        # Test Area
        test_group = ttk.LabelFrame(right_frame, text="Test Alanı", padding=10)
        test_group.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ttk.Label(test_group, text="Komut Gönder:").pack(anchor="w", pady=2)
        btn_box = ttk.Frame(test_group)
        btn_box.pack(fill=tk.X, pady=2)
        ttk.Button(btn_box, text="BIP", command=lambda: self._send_cmd("BIP")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_box, text="DOGRU", command=lambda: self._send_cmd("DOGRU")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_box, text="YANLIS", command=lambda: self._send_cmd("YANLIS")).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(test_group, text="Potansiyometre (A0):").pack(anchor="w", pady=(10, 2))
        self.pot_val_var = tk.StringVar(value="Henüz veri yok")
        ttk.Label(test_group, textvariable=self.pot_val_var, font=("Segoe UI", 12, "bold"), foreground="#cc7832").pack(anchor="w")
        
        self.pot_progress = ttk.Progressbar(test_group, orient="horizontal", length=200, mode="determinate", maximum=1023)
        self.pot_progress.pack(fill=tk.X, pady=5)

    def _load_schematic(self):
        img_path = os.path.join(self._project_root, "assets", "unopg.png")
        if os.path.exists(img_path):
            try:
                img = Image.open(img_path)
                # Resize if too big
                img.thumbnail((380, 280))
                self.schematic_photo = pil_to_tkphoto(img)
                self.schematic_canvas.create_image(190, 140, image=self.schematic_photo)
                
                # Draw labels
                self.schematic_canvas.create_text(200, 20, text="PIN 10: Buzzer | PIN 11-13: LEDs | A0: Pot", fill="white", font=("Segoe UI", 8, "bold"))
            except Exception as e:
                self.schematic_canvas.create_text(190, 140, text=f"Resim yüklenemedi: {e}", fill="red")
        else:
             self.schematic_canvas.create_text(190, 140, text="unopg.png bulunamadı", fill="yellow")

    def _copy_code(self):
        self.frame.clipboard_clear()
        self.frame.clipboard_append(FIRMWARE_CODE)
        messagebox.showinfo("Başarılı", "Firmware kodu panoya kopyalandı.")

    def _refresh_ports(self):
        ports = arduino.get_available_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)

    def _toggle_connection(self):
        if not arduino.arduino_connected:
            port = self.port_var.get()
            baud = self.baud_var.get()
            if not port or not baud:
                messagebox.showwarning("Uyarı", "Lütfen port ve baud hızı seçin.")
                return
            if arduino.connect_arduino(port, int(baud)):
                self.connect_btn.config(text="Bağlantıyı Kes", style="Accent.TButton")
                self._start_monitor()
            else:
                messagebox.showerror("Hata", "Porta bağlanılamadı.")
        else:
            self._stop_monitor()
            arduino.close_arduino()
            self.connect_btn.config(text="Bağlan", style="TButton")

    def _send_cmd(self, cmd):
        if arduino.arduino_connected:
            arduino.send_command(cmd)
        else:
            messagebox.showwarning("Bağlantı Yok", "Lütfen önce Arduino'ya bağlanın.")

    def _start_monitor(self):
        self.monitor_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _stop_monitor(self):
        self.monitor_running = False

    def _monitor_loop(self):
        while self.monitor_running:
            line = arduino.read_arduino()
            if line and line.startswith("POT:"):
                try:
                    val = int(line.split(":")[1])
                    self.frame.after(0, lambda v=val: self._update_pot_ui(v))
                except:
                    pass
            import time
            time.sleep(0.1)

    def _update_pot_ui(self, val):
        self.pot_val_var.set(f"Değer: {val}")
        self.pot_progress['value'] = val

    def refresh(self):
        parent_tl = self.frame.winfo_toplevel()
        if hasattr(parent_tl, 'current_game_id'):
            self.current_game_id = parent_tl.current_game_id
        
        if not arduino.arduino_connected:
            self._refresh_ports()
