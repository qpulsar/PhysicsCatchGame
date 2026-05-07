import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
from ..core.publisher import PublisherService

class SubmissionDialog(tk.Toplevel):
    """Dialog to collect user info and submit the game."""

    def __init__(self, parent, game_id, db_manager):
        super().__init__(parent)
        self.title("Oyunu İncelemeye Gönder 🚀")
        self.geometry("450x550")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.game_id = game_id
        self.publisher = PublisherService(db_manager)
        
        # Default server URL - can be changed by user if needed
        self.server_url_var = tk.StringVar(value="http://localhost:8000/submit")
        self.first_name_var = tk.StringVar()
        self.last_name_var = tk.StringVar()
        self.email_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        # Header
        ttk.Label(container, text="Oyun Tasarımını Gönder", font=("Segoe UI", 16, "bold")).pack(pady=(0, 10))
        ttk.Label(container, text="Lütfen bilgilerinizi doldurun. Oyununuz paketlenerek inceleme sunucusuna gönderilecektir.", 
                  wraplength=400, justify="center").pack(pady=(0, 20))

        # Form
        def _field(label, var):
            f = ttk.Frame(container)
            f.pack(fill="x", pady=5)
            ttk.Label(f, text=label, width=15, anchor="w").pack(side="left")
            ttk.Entry(f, textvariable=var).pack(side="left", fill="x", expand=True)

        _field("Adınız:", self.first_name_var)
        _field("Soyadınız:", self.last_name_var)
        _field("E-posta:", self.email_var)
        
        ttk.Separator(container, orient="horizontal").pack(fill="x", pady=20)
        
        ttk.Label(container, text="Sunucu Adresi:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Entry(container, textvariable=self.server_url_var).pack(fill="x", pady=(5, 20))

        # Status & Progress
        self.status_label = ttk.Label(container, text="", foreground="#4CAF50")
        self.status_label.pack(pady=5)
        
        self.progress = ttk.Progressbar(container, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=10)

        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(side="bottom", fill="x", pady=(20, 0))

        self.submit_btn = ttk.Button(btn_frame, text="Paketle ve Gönder 📤", style="Accent.TButton", command=self._on_submit)
        self.submit_btn.pack(side="right", padx=5)
        
        ttk.Button(btn_frame, text="İptal", command=self.destroy).pack(side="right")

    def _on_submit(self):
        # Validate
        if not self.first_name_var.get() or not self.last_name_var.get() or not self.email_var.get():
            messagebox.showwarning("Eksik Bilgi", "Lütfen tüm kişisel bilgileri doldurun.")
            return

        self.submit_btn.config(state="disabled")
        self.status_label.config(text="Oyun paketleniyor...", foreground="#a9b7c6")
        self.progress.start(10)

        # Run in thread to keep UI responsive
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            # 1. Package
            zip_path = self.publisher.package_game(self.game_id)
            if not zip_path:
                self.after(0, lambda: self._handle_error("Paketleme sırasında bir hata oluştu."))
                return

            self.after(0, lambda: self.status_label.config(text="Sunucuya gönderiliyor..."))
            
            # 2. Upload
            user_info = {
                "first_name": self.first_name_var.get(),
                "last_name": self.last_name_var.get(),
                "email": self.email_var.get()
            }
            
            result = self.publisher.upload_game(zip_path, user_info, self.server_url_var.get())
            
            if result.get("status") == "success":
                self.after(0, lambda: self._handle_success(result["data"]))
            else:
                self.after(0, lambda: self._handle_error(result.get("message", "Sunucu hatası.")))

        except Exception as e:
            self.after(0, lambda: self._handle_error(str(e)))

    def _handle_success(self, data):
        self.progress.stop()
        self.progress["value"] = 100
        self.status_label.config(text="✅ Başarıyla gönderildi!", foreground="#4CAF50")
        messagebox.showinfo("Başarılı", f"Oyununuz incelemeye gönderildi!\n\nSunucu Yanıtı: {data.get('message', 'Başarılı')}")
        self.destroy()

    def _handle_error(self, msg):
        self.progress.stop()
        self.status_label.config(text="❌ Hata oluştu.", foreground="#f44336")
        self.submit_btn.config(state="normal")
        messagebox.showerror("Gönderim Hatası", f"İşlem başarısız oldu:\n\n{msg}")
