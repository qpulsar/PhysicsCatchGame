"""Media management tab for shared game assets.

This tab works over the root-level `assets/` directory (not per-game) and provides:
- Uploading media with slugified filenames
- Image preview
- Audio play/stop for supported formats
- Description field (per-game usage) stored in `assets/metadata.json`
- Image preparation tools: scale to 1024x768, scale by percentage
"""
from __future__ import annotations

import os
import json
import unicodedata
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Optional, List

from PIL import Image, ImageTk
from ...utils import format_filetypes_for_dialog

# Pygame is used only for audio preview (lazy init)
try:
    import pygame
    _HAVE_PYGAME = True
except Exception:
    _HAVE_PYGAME = False


class MediaTab:
    """UI tab for managing shared media assets under `assets/`.

    Attributes:
        frame: Root ttk.Frame for this tab.
    """

    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
    AUDIO_EXTS = {".wav", ".ogg", ".mp3", ".midi", ".mid"}

    def __init__(self, parent, game_service):
        """Initialize the Media tab UI.

        Args:
            parent: The parent widget (Notebook).
            game_service: Service to fetch current game data (only used to know game_id for descriptions).
        """
        self.parent = parent
        self.game_service = game_service
        self.current_game_id: Optional[int] = None  # artık açıklamalarda kullanılmıyor (global)

        # Proje köküne göre assets kökünü belirle (çalışma dizininden bağımsız)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        self.assets_root = os.path.join(project_root, "assets")
        # Klasörler: background, sprite, audio (music), sfx
        self.dir_backgrounds = os.path.join(self.assets_root, "images", "backgrounds")
        self.dir_sprites = os.path.join(self.assets_root, "images", "sprites")
        self.dir_audio_music = os.path.join(self.assets_root, "audio", "music")
        self.dir_audio_sfx = os.path.join(self.assets_root, "audio", "sfx")
        os.makedirs(self.dir_backgrounds, exist_ok=True)
        os.makedirs(self.dir_sprites, exist_ok=True)
        os.makedirs(self.dir_audio_music, exist_ok=True)
        os.makedirs(self.dir_audio_sfx, exist_ok=True)

        self.metadata_path = os.path.join(self.assets_root, "metadata.json")
        self.metadata: Dict[str, Dict[str, str]] = self._load_metadata()

        self._preview_img_ref = None
        self._audio_playing_path: Optional[str] = None

        self.frame = ttk.Frame(parent)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)

        # OS üzerinden taşınmış/yüklenmiş medya ile metadata'yı senkronize et
        self._sync_assets_metadata()

        self._build_ui()
        self.refresh()

    def _ensure_audio_ready(self) -> bool:
        """Ensure pygame and mixer are initialized lazily on demand.

        Returns True if audio is ready to play, False otherwise.
        """
        if not _HAVE_PYGAME:
            return False
        try:
            if not pygame.get_init():
                pygame.init()
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            return True
        except Exception as e:
            # Disable buttons to avoid repeated errors
            try:
                self.play_btn.config(state="disabled")
                self.stop_btn.config(state="disabled")
            except Exception:
                pass
            messagebox.showwarning("Ses", f"Ses sistemi başlatılamadı: {e}")
            return False

    def _build_ui(self) -> None:
        """Build the two-pane UI: left list, right preview and actions."""
        # Left: file list with type filter and upload
        left = ttk.Frame(self.frame, padding=5)
        left.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        ttk.Label(left, text="Tür").grid(row=0, column=0, sticky="w")
        self.type_var = tk.StringVar(value="background")
        type_combo = ttk.Combobox(left, textvariable=self.type_var, state="readonly",
                                  values=["background", "audio", "sfx", "sprite"])
        type_combo.grid(row=0, column=1, sticky="ew", padx=4)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._reload_list())

        self.tree = ttk.Treeview(left, columns=("name", "path"), show="headings", selectmode="browse")
        self.tree.heading("name", text="Ad")
        self.tree.heading("path", text="Yol")
        self.tree.column("name", width=160)
        self.tree.column("path", width=260)
        self.tree.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 4))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())

        btn_row = ttk.Frame(left)
        btn_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Button(btn_row, text="Yükle...", command=self._upload_media).pack(side=tk.LEFT, padx=2)
        self.delete_btn = ttk.Button(btn_row, text="Sil", command=self._delete_selected)
        self.delete_btn.pack(side=tk.LEFT, padx=2)

        # Right: preview and details
        right = ttk.Frame(self.frame, padding=5)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # Preview area
        prev_group = ttk.LabelFrame(right, text="Önizleme", padding=5)
        prev_group.grid(row=0, column=0, sticky="nsew")
        prev_group.rowconfigure(0, weight=1)
        prev_group.columnconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(prev_group, background="white", height=260)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")

        audio_row = ttk.Frame(prev_group)
        audio_row.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.play_btn = ttk.Button(audio_row, text="▶ Oynat", command=self._play_audio, state="disabled")
        self.stop_btn = ttk.Button(audio_row, text="■ Durdur", command=self._stop_audio, state="disabled")
        self.play_btn.pack(side=tk.LEFT, padx=2)
        self.stop_btn.pack(side=tk.LEFT, padx=2)

        # Details and actions
        details = ttk.LabelFrame(right, text="Detaylar", padding=8)
        details.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        details.columnconfigure(1, weight=1)

        ttk.Label(details, text="Seçili Dosya:").grid(row=0, column=0, sticky="e")
        self.sel_name_var = tk.StringVar()
        ttk.Label(details, textvariable=self.sel_name_var).grid(row=0, column=1, sticky="w")

        ttk.Label(details, text="Açıklama:").grid(row=1, column=0, sticky="ne", pady=4)
        self.desc_text = tk.Text(details, height=3, width=40, wrap="word")
        self.desc_text.grid(row=1, column=1, sticky="ew")

        # File info rows
        info_frame = ttk.Frame(details)
        info_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        info_frame.columnconfigure(1, weight=1)

        ttk.Label(info_frame, text="Tür:").grid(row=0, column=0, sticky="e")
        self.info_type_var = tk.StringVar()
        ttk.Label(info_frame, textvariable=self.info_type_var).grid(row=0, column=1, sticky="w")

        ttk.Label(info_frame, text="Boyut:").grid(row=1, column=0, sticky="e")
        self.info_size_var = tk.StringVar()
        ttk.Label(info_frame, textvariable=self.info_size_var).grid(row=1, column=1, sticky="w")

        ttk.Label(info_frame, text="Çözünürlük:").grid(row=2, column=0, sticky="e")
        self.info_resolution_var = tk.StringVar()
        ttk.Label(info_frame, textvariable=self.info_resolution_var).grid(row=2, column=1, sticky="w")

        ttk.Label(info_frame, text="Süre:").grid(row=3, column=0, sticky="e")
        self.info_duration_var = tk.StringVar()
        ttk.Label(info_frame, textvariable=self.info_duration_var).grid(row=3, column=1, sticky="w")

        ttk.Label(info_frame, text="Örnekleme / Kanal / Bit:").grid(row=4, column=0, sticky="e")
        self.info_audio_params_var = tk.StringVar()
        ttk.Label(info_frame, textvariable=self.info_audio_params_var).grid(row=4, column=1, sticky="w")

        act_row = ttk.Frame(details)
        act_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(act_row, text="Açıklamayı Kaydet", command=self._save_description).pack(side=tk.LEFT, padx=2)

        # Image tools
        tools = ttk.LabelFrame(right, text="Görsel Hazırlama Araçları", padding=8)
        tools.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        ttk.Button(tools, text="1024x768'e Ölçekle (kopya)", command=self._scale_1024_768).pack(side=tk.LEFT, padx=4)
        ttk.Label(tools, text="%").pack(side=tk.LEFT)
        self.scale_percent_var = tk.StringVar(value="50")
        ttk.Entry(tools, textvariable=self.scale_percent_var, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools, text="Oransal Ölçekle (kopya)", command=self._scale_percent).pack(side=tk.LEFT, padx=4)

    def refresh(self) -> None:
        """Refresh the tab and list files (descriptions are global)."""
        self._reload_list()
        self._update_preview_controls(None)

    def _reload_list(self) -> None:
        """Reload the file list based on selected type."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        base_dir = self._current_dir()
        try:
            files = []
            for root, _, fnames in os.walk(base_dir):
                for fname in fnames:
                    path = os.path.join(root, fname)
                    rel = os.path.relpath(path, self.assets_root)
                    files.append((fname, rel))
            files.sort(key=lambda x: x[0].lower())
            for name, rel in files:
                self.tree.insert("", tk.END, iid=rel, values=(name, rel))
        except FileNotFoundError:
            os.makedirs(base_dir, exist_ok=True)

    def _current_dir(self) -> str:
        """Return the directory for the current selected type.

        background -> assets/images/backgrounds
        sprite     -> assets/images/sprites
        audio      -> assets/audio/music
        sfx        -> assets/audio/sfx
        """
        t = self.type_var.get()
        if t == "background":
            return self.dir_backgrounds
        if t == "sprite":
            return self.dir_sprites
        if t == "audio":
            return self.dir_audio_music
        # default sfx
        return self.dir_audio_sfx

    def _on_select(self) -> None:
        """Handle selection changes and update preview/details."""
        sel = self.tree.selection()
        if not sel:
            self._update_preview_controls(None)
            return
        rel = sel[0]
        abs_path = os.path.join(self.assets_root, rel)
        self.sel_name_var.set(os.path.basename(rel))
        self._load_preview(abs_path)
        self._update_file_info(abs_path)
        self._load_description(rel)

    def _load_preview(self, path: str) -> None:
        """Load preview for images; enable audio controls for audio files."""
        self.preview_canvas.delete("all")
        self._preview_img_ref = None
        self._update_preview_controls(path)
        if path is None:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in self.IMAGE_EXTS and os.path.isfile(path):
            try:
                img = Image.open(path)
                img.thumbnail((420, 260), Image.LANCZOS)
                self._preview_img_ref = ImageTk.PhotoImage(img)
                self.preview_canvas.create_image(10, 10, anchor="nw", image=self._preview_img_ref)
            except Exception as e:
                messagebox.showerror("Önizleme Hatası", str(e))

    def _update_file_info(self, path: Optional[str]) -> None:
        """Update file info labels based on selected file."""
        # Reset fields
        self.info_type_var.set("")
        self.info_size_var.set("")
        self.info_resolution_var.set("")
        self.info_duration_var.set("")
        self.info_audio_params_var.set("")
        if not path or not os.path.isfile(path):
            return
        ext = os.path.splitext(path)[1].lower()
        ftype = "Görsel" if ext in self.IMAGE_EXTS else ("Ses" if ext in self.AUDIO_EXTS else "Dosya")
        self.info_type_var.set(ftype)
        try:
            size_bytes = os.path.getsize(path)
            self.info_size_var.set(self._format_bytes(size_bytes))
        except Exception:
            pass
        # Image details
        if ext in self.IMAGE_EXTS:
            try:
                img = Image.open(path)
                w, h = img.size
                self.info_resolution_var.set(f"{w} x {h} px")
            except Exception:
                pass
        # Audio details
        if ext in {".wav", ".wave"}:
            # Use wave module for detailed info
            try:
                import wave, contextlib
                with contextlib.closing(wave.open(path, 'rb')) as wf:
                    nch = wf.getnchannels()
                    sw = wf.getsampwidth()  # bytes
                    fr = wf.getframerate()
                    nframes = wf.getnframes()
                    duration = nframes / float(fr) if fr else 0.0
                    self.info_duration_var.set(self._format_seconds(duration))
                    self.info_audio_params_var.set(f"{fr} Hz / {nch} ch / {sw * 8} bit")
            except Exception:
                pass
        elif ext in {".ogg", ".mp3", ".midi", ".mid"}:
            # Try pygame for duration if available
            if _HAVE_PYGAME and self._ensure_audio_ready():
                try:
                    snd = pygame.mixer.Sound(path)
                    dur = snd.get_length()
                    self.info_duration_var.set(self._format_seconds(dur))
                except Exception:
                    pass

    def _update_preview_controls(self, path: Optional[str]) -> None:
        """Enable/disable audio controls depending on selected file."""
        self.play_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in self.AUDIO_EXTS and _HAVE_PYGAME:
            self.play_btn.config(state="normal")
            self.stop_btn.config(state="normal")

    def _upload_media(self) -> None:
        """Open file dialog and copy selected file into assets with sanitized name."""
        t = self.type_var.get()
        if t in ("background", "sprite"):
            exts = [("Görseller", "*.png *.jpg *.jpeg *.bmp *.gif"), ("Tüm Dosyalar", "*.*")]
        else:
            exts = [("Ses", "*.wav *.ogg *.mp3 *.midi *.mid"), ("Tüm Dosyalar", "*.*")]
        
        # Platform-agnostic dosya türleri
        exts = format_filetypes_for_dialog(exts)
        paths = filedialog.askopenfilenames(title="Medya Seç", filetypes=exts)
        if not paths:
            return
        dst_dir = self._current_dir()
        os.makedirs(dst_dir, exist_ok=True)
        copied = 0
        for p in paths:
            try:
                safe = self._sanitize_filename(os.path.basename(p))
                dst = self._avoid_collision(dst_dir, safe)
                with open(p, 'rb') as rf, open(dst, 'wb') as wf:
                    wf.write(rf.read())
                copied += 1
            except Exception as e:
                messagebox.showerror("Kopyalama Hatası", f"{os.path.basename(p)}: {e}")
        if copied:
            self._reload_list()

    def _delete_selected(self) -> None:
        """Delete selected media file after confirmation."""
        sel = self.tree.selection()
        if not sel:
            return
        rel = sel[0]
        abs_path = os.path.join(self.assets_root, rel)
        if not os.path.isfile(abs_path):
            return
        if not messagebox.askyesno("Sil", f"{os.path.basename(rel)} dosyasını silmek istediğinize emin misiniz?"):
            return
        try:
            os.remove(abs_path)
            # Also remove metadata for all games for this file
            self.metadata.pop(rel, None)
            self._save_metadata()
            self._reload_list()
            self.preview_canvas.delete("all")
            self.sel_name_var.set("")
            self.desc_text.delete("1.0", "end")
        except Exception as e:
            messagebox.showerror("Silme Hatası", str(e))

    def _play_audio(self) -> None:
        """Play selected audio using pygame mixer if available."""
        if not _HAVE_PYGAME:
            messagebox.showwarning("Ses", "Pygame kurulu değil. requirements.txt içinden yükleyin.")
            return
        if not self._ensure_audio_ready():
            return
        sel = self.tree.selection()
        if not sel:
            return
        rel = sel[0]
        path = os.path.join(self.assets_root, rel)
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            self._audio_playing_path = path
        except Exception as e:
            messagebox.showerror("Ses Çalma Hatası", str(e))

    def _stop_audio(self) -> None:
        """Stop audio playback if playing."""
        if not _HAVE_PYGAME:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._audio_playing_path = None

    def _save_description(self) -> None:
        """Save global description for selected file into assets/metadata.json.

        The structure becomes: { "relative/path.ext": { "description": "desc" } }
        """
        sel = self.tree.selection()
        if not sel:
            return
        rel = sel[0]
        text = self.desc_text.get("1.0", "end-1c").strip()
        if rel not in self.metadata:
            self.metadata[rel] = {}
        self.metadata[rel]["description"] = text
        self._save_metadata()
        messagebox.showinfo("Kayıt", "Açıklama kaydedildi.")

    def _format_bytes(self, size: int) -> str:
        """Format bytes to human-readable string."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def _format_seconds(self, secs: float) -> str:
        """Format seconds to mm:ss.mmm or hh:mm:ss depending on length."""
        try:
            if secs < 0:
                secs = 0
            hours = int(secs // 3600)
            mins = int((secs % 3600) // 60)
            rem = secs % 60
            if hours:
                return f"{hours:02d}:{mins:02d}:{int(rem):02d}"
            else:
                return f"{mins:02d}:{rem:05.2f}"
        except Exception:
            return ""

    def _load_description(self, rel: str) -> None:
        """Load global description from metadata for the selected file."""
        self.desc_text.delete("1.0", "end")
        data = self.metadata.get(rel, {})
        desc = data.get("description", "")
        if desc:
            self.desc_text.insert("1.0", desc)

    def _scale_1024_768(self) -> None:
        """Scale selected image to 1024x768 and save as copy (suffix _1024x768)."""
        self._scale_image_to_fixed((1024, 768), suffix="_1024x768")

    def _scale_percent(self) -> None:
        """Scale selected image by percentage from input and save as copy."""
        try:
            percent = float(self.scale_percent_var.get())
            if percent <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Geçersiz Değer", "Lütfen geçerli bir yüzde girin.")
            return
        self._scale_image_percent(percent)

    def _scale_image_to_fixed(self, size: tuple[int, int], suffix: str) -> None:
        """Scale the selected image to a fixed size and save as a copy.

        Args:
            size: (width, height)
            suffix: Filename suffix before extension for the copy.
        """
        sel = self.tree.selection()
        if not sel:
            return
        rel = sel[0]
        src = os.path.join(self.assets_root, rel)
        ext = os.path.splitext(src)[1].lower()
        if ext not in self.IMAGE_EXTS:
            messagebox.showwarning("Görsel", "Bu işlem yalnızca görseller için geçerlidir.")
            return
        try:
            img = Image.open(src)
            img = img.resize(size, Image.LANCZOS)
            base, ext = os.path.splitext(os.path.basename(src))
            dst_name = f"{base}{suffix}{ext}"
            dst = self._avoid_collision(os.path.dirname(src), dst_name)
            img.save(dst)
            self._reload_list()
            # Reselect original
            if self.tree.exists(rel):
                self.tree.selection_set(rel)
            messagebox.showinfo("Kayıt", os.path.basename(dst) + " oluşturuldu.")
        except Exception as e:
            messagebox.showerror("İşleme Hatası", str(e))

    def _scale_image_percent(self, percent: float) -> None:
        """Scale selected image by percent and save as copy.

        Args:
            percent: Percentage like 50 for 50%.
        """
        sel = self.tree.selection()
        if not sel:
            return
        rel = sel[0]
        src = os.path.join(self.assets_root, rel)
        ext = os.path.splitext(src)[1].lower()
        if ext not in self.IMAGE_EXTS:
            messagebox.showwarning("Görsel", "Bu işlem yalnızca görseller için geçerlidir.")
            return
        try:
            img = Image.open(src)
            w, h = img.size
            nw = max(1, int(w * percent / 100.0))
            nh = max(1, int(h * percent / 100.0))
            img = img.resize((nw, nh), Image.LANCZOS)
            base, ext = os.path.splitext(os.path.basename(src))
            suffix = f"_{int(percent)}pct"
            dst_name = f"{base}{suffix}{ext}"
            dst = self._avoid_collision(os.path.dirname(src), dst_name)
            img.save(dst)
            self._reload_list()
            if self.tree.exists(rel):
                self.tree.selection_set(rel)
            messagebox.showinfo("Kayıt", os.path.basename(dst) + " oluşturuldu.")
        except Exception as e:
            messagebox.showerror("İşleme Hatası", str(e))

    def _sanitize_filename(self, name: str) -> str:
        """Slugify-like sanitize similar to sprite service rules.

        Keeps ASCII, replaces spaces and invalid chars with underscore, keeps extension alnum only.
        """
        name = name.strip().lower()
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')
        base, ext = os.path.splitext(name)
        safe_base = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in base)
        safe_ext = ''.join(c if c.isalnum() else '' for c in ext)
        ext = ('.' + safe_ext) if safe_ext else ''
        if not safe_base:
            safe_base = 'file'
        return safe_base + ext

    def _avoid_collision(self, directory: str, filename: str) -> str:
        """Avoid filename collisions by appending incremental suffixes."""
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base}_{counter}{ext}")
            counter += 1
        return candidate

    def _load_metadata(self) -> Dict[str, Dict[str, str]]:
        """Load metadata JSON if exists, otherwise return empty mapping."""
        try:
            if os.path.isfile(self.metadata_path):
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
        return {}

    def _save_metadata(self) -> None:
        """Persist metadata JSON to disk under assets/metadata.json."""
        try:
            os.makedirs(self.assets_root, exist_ok=True)
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Metadata Hatası", str(e))

    def _sync_assets_metadata(self) -> None:
        """Scan assets directories and ensure metadata keys exist for each file.

        - Yeni bulunan dosyalar için boş bir kayıt ({} veya mevcutsa korunur) oluşturur.
        - Artık mevcut olmayan dosyaların metadata kayıtlarını temizler.
        """
        try:
            existing_keys = set(self.metadata.keys())
            current_files: List[str] = []
            # Yalnızca kendi yönettiğimiz alt klasörleri tara
            for base in (self.dir_backgrounds, self.dir_sprites, self.dir_audio_music, self.dir_audio_sfx):
                if not os.path.isdir(base):
                    continue
                for root, _, fnames in os.walk(base):
                    for fname in fnames:
                        path = os.path.join(root, fname)
                        rel = os.path.relpath(path, self.assets_root).replace('\\', '/')
                        current_files.append(rel)

            # Eksik anahtarları ekle
            changed = False
            for rel in current_files:
                if rel not in self.metadata:
                    self.metadata[rel] = {}
                    changed = True

            # Var olmayanları temizle
            for key in list(existing_keys):
                if key not in current_files:
                    self.metadata.pop(key, None)
                    changed = True

            if changed:
                self._save_metadata()
        except Exception:
            # Sessiz geç; bu senkronizasyon kritik değil
            pass
