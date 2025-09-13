"""Settings tab for the game editor."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
import unicodedata
from PIL import Image
from typing import Dict, Any, Optional, Callable

from ...core.services import GameService


class SettingsTab:
    """Tab for managing game settings."""
    
    def __init__(self, parent, game_service: GameService):
        """Initialize the settings tab.
        
        Args:
            parent: Parent widget.
            game_service: Service for game operations.
        """
        self.parent = parent
        self.game_service = game_service
        self.current_game_id = None
        
        # Create the main frame for this tab
        self.frame = ttk.Frame(parent)
        
        # Settings form
        self._setup_settings_form()
        
        # Track if we've loaded settings at least once
        self._initialized = False
    
    def _setup_settings_form(self) -> None:
        """Set up the settings form."""
        # Main container
        container = ttk.Frame(self.frame, padding="10")
        container.pack(fill=tk.BOTH, expand=True)
        
        # Form fields
        ttk.Label(container, text="Toplam Seviye Sayısı:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.total_levels = ttk.Spinbox(container, from_=1, to=100, width=10)
        self.total_levels.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(container, text="Varsayılan Yanlış Cevap Yüzdesi (%):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.default_wrong_percentage = ttk.Spinbox(container, from_=0, to=100, width=10)
        self.default_wrong_percentage.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(container, text="Varsayılan Öğe Hızı:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.default_item_speed = ttk.Spinbox(container, from_=0.1, to=10.0, increment=0.1, width=10)
        self.default_item_speed.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(container, text="Varsayılan Maksimum Öğe Sayısı:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.default_max_items = ttk.Spinbox(container, from_=1, to=20, width=10)
        self.default_max_items.grid(row=3, column=1, sticky="w", padx=5, pady=5)

        # Background image selection
        ttk.Label(container, text="Başlangıç Arkaplan Görseli:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.start_bg_path_var = tk.StringVar()
        bg_frame = ttk.Frame(container)
        bg_frame.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        self.start_bg_entry = ttk.Entry(bg_frame, textvariable=self.start_bg_path_var, width=32)
        self.start_bg_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(bg_frame, text="Seç...", command=self._browse_start_bg).pack(side=tk.LEFT)

        # Background scaling options
        self.bg_scale_enable_var = tk.BooleanVar(value=False)
        self.bg_scale_keep_ratio_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(container, text="Yeniden boyutlandır", variable=self.bg_scale_enable_var).grid(row=5, column=1, sticky="w", padx=5)
        scale_row = ttk.Frame(container)
        scale_row.grid(row=6, column=1, sticky="w", padx=5, pady=(0,5))
        ttk.Label(scale_row, text="Genişlik:").pack(side=tk.LEFT)
        self.bg_scale_w_var = tk.StringVar()
        ttk.Entry(scale_row, textvariable=self.bg_scale_w_var, width=7).pack(side=tk.LEFT, padx=(2,8))
        ttk.Label(scale_row, text="Yükseklik:").pack(side=tk.LEFT)
        self.bg_scale_h_var = tk.StringVar()
        ttk.Entry(scale_row, textvariable=self.bg_scale_h_var, width=7).pack(side=tk.LEFT, padx=(2,8))
        ttk.Checkbutton(scale_row, text="Oranı koru", variable=self.bg_scale_keep_ratio_var).pack(side=tk.LEFT)

        # Thumbnail selection
        ttk.Label(container, text="Oyun Küçük Resmi (Thumbnail):").grid(row=7, column=0, sticky="e", padx=5, pady=5)
        self.thumb_path_var = tk.StringVar()
        thumb_frame = ttk.Frame(container)
        thumb_frame.grid(row=7, column=1, sticky="w", padx=5, pady=5)
        self.thumb_entry = ttk.Entry(thumb_frame, textvariable=self.thumb_path_var, width=32)
        self.thumb_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(thumb_frame, text="Seç...", command=self._browse_thumbnail).pack(side=tk.LEFT)

        # Music selection
        ttk.Label(container, text="Arkaplan Müziği (BGM):").grid(row=8, column=0, sticky="e", padx=5, pady=5)
        self.music_path_var = tk.StringVar()
        music_frame = ttk.Frame(container)
        music_frame.grid(row=8, column=1, sticky="w", padx=5, pady=5)
        self.music_entry = ttk.Entry(music_frame, textvariable=self.music_path_var, width=32)
        self.music_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(music_frame, text="Seç...", command=self._browse_music).pack(side=tk.LEFT)

        # Game description editor
        ttk.Label(container, text="Oyun Açıklaması:").grid(row=9, column=0, sticky="ne", padx=5, pady=5)
        self.game_description_text = tk.Text(container, height=6, width=50, wrap="word")
        self.game_description_text.grid(row=9, column=1, sticky="ew", padx=5, pady=5)
        
        # Save button
        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=10, column=0, columnspan=2, pady=20)
        
        ttk.Button(
            btn_frame, 
            text="Ayarları Kaydet", 
            command=self.save_settings
        ).pack(side=tk.TOP, pady=10)
    
    def refresh(self) -> None:
        """Refresh the settings form with current values."""
        # Get the current game ID from the parent window
        parent = self.frame.winfo_toplevel()
        if not hasattr(parent, 'current_game_id') or parent.current_game_id is None:
            # Clear the form if no game is selected
            if self._initialized:
                self._clear_form()
            return
            
        game_id = parent.current_game_id
        
        # Only update if the game has changed
        if self.current_game_id == game_id and self._initialized:
            return
            
        self.current_game_id = game_id
        
        try:
            # Get settings for the current game
            settings = self.game_service.get_settings(game_id)
            
            # Update form fields
            self.total_levels.delete(0, tk.END)
            self.total_levels.insert(0, settings.get('total_levels', '10'))
            
            self.default_wrong_percentage.delete(0, tk.END)
            self.default_wrong_percentage.insert(0, settings.get('default_wrong_percentage', '20'))
            
            self.default_item_speed.delete(0, tk.END)
            self.default_item_speed.insert(0, settings.get('default_item_speed', '2.0'))
            
            self.default_max_items.delete(0, tk.END)
            self.default_max_items.insert(0, settings.get('default_max_items', '5'))

            # Background path
            self.start_bg_path_var.set(settings.get('start_background_path', ''))

            # Background scaling options
            self.bg_scale_enable_var.set(settings.get('bg_scale_enable', False))
            self.bg_scale_w_var.set(settings.get('bg_scale_w', ''))
            self.bg_scale_h_var.set(settings.get('bg_scale_h', ''))
            self.bg_scale_keep_ratio_var.set(settings.get('bg_scale_keep_ratio', True))

            # Thumbnail and music
            self.thumb_path_var.set(settings.get('thumbnail_path', ''))
            self.music_path_var.set(settings.get('music_path', ''))

            # Load current game description
            game = self.game_service.get_game(game_id)
            self.game_description_text.delete("1.0", tk.END)
            self.game_description_text.insert("1.0", getattr(game, 'description', '') or '')
            
            self._initialized = True
            
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar yüklenirken bir hata oluştu: {str(e)}")
    
    def _clear_form(self) -> None:
        """Clear all form fields."""
        for widget in [self.total_levels, self.default_wrong_percentage, 
                      self.default_item_speed, self.default_max_items]:
            widget.delete(0, tk.END)
            widget.insert(0, "")
        self.start_bg_path_var.set("")
        self.bg_scale_w_var.set("")
        self.bg_scale_h_var.set("")
        self.thumb_path_var.set("")
        self.music_path_var.set("")
        self.game_description_text.delete("1.0", tk.END)
        
        self.current_game_id = None
        self._initialized = False
    
    def save_settings(self) -> None:
        """Save the current settings."""
        # Get the current game ID from the parent window
        parent = self.frame.winfo_toplevel()
        if not hasattr(parent, 'current_game_id') or parent.current_game_id is None:
            messagebox.showerror("Hata", "Lütfen önce bir oyun seçin.")
            return
            
        game_id = parent.current_game_id
        
        try:
            settings = {
                'total_levels': self.total_levels.get(),
                'default_wrong_percentage': self.default_wrong_percentage.get(),
                'default_item_speed': self.default_item_speed.get(),
                'default_max_items': self.default_max_items.get()
            }
            
            # Validate required numeric inputs (background path is optional)
            for key in ['total_levels', 'default_wrong_percentage', 'default_item_speed', 'default_max_items']:
                if not settings.get(key):
                    messagebox.showerror("Hata", f"Lütfen tüm alanları doldurun: {key}")
                    return
            
            # Convert and validate numeric values
            try:
                total_levels = int(settings['total_levels'])
                wrong_percent = int(settings['default_wrong_percentage'])
                item_speed = float(settings['default_item_speed'])
                max_items = int(settings['default_max_items'])
                
                if total_levels < 1 or total_levels > 100:
                    raise ValueError("Toplam seviye sayısı 1-100 arasında olmalıdır.")
                if wrong_percent < 0 or wrong_percent > 100:
                    raise ValueError("Yanlış cevap yüzdesi 0-100 arasında olmalıdır.")
                if item_speed <= 0 or item_speed > 10:
                    raise ValueError("Öğe hızı 0.1-10.0 arasında olmalıdır.")
                if max_items < 1 or max_items > 20:
                    raise ValueError("Maksimum öğe sayısı 1-20 arasında olmalıdır.")
                    
            except ValueError as e:
                messagebox.showerror("Geçersiz Değer", str(e))
                return
            
            # Save numeric settings
            for key, value in settings.items():
                self.game_service.update_setting(game_id, key, value)

            # Handle background image copy (optional) with scaling
            src_bg_path = self.start_bg_path_var.get().strip()
            if src_bg_path:
                try:
                    dst_dir = os.path.join('assets', 'games', str(game_id), 'backgrounds')
                    os.makedirs(dst_dir, exist_ok=True)
                    dst_path = self._resize_and_copy_image(
                        src_bg_path,
                        dst_dir,
                        self.bg_scale_enable_var.get(),
                        self.bg_scale_w_var.get().strip(),
                        self.bg_scale_h_var.get().strip(),
                        self.bg_scale_keep_ratio_var.get()
                    )
                    rel_dst_path = dst_path.replace('\\', '/')
                    self.game_service.update_setting(game_id, 'start_background_path', rel_dst_path)
                except Exception as copy_err:
                    messagebox.showwarning("Uyarı", f"Arkaplan kopyalanamadı: {copy_err}")

            # Handle thumbnail copy (optional)
            src_thumb = self.thumb_path_var.get().strip()
            if src_thumb:
                try:
                    if not os.path.isfile(src_thumb):
                        raise FileNotFoundError("Seçilen küçük resim dosyası bulunamadı.")
                    dst_dir = os.path.join('assets', 'games', str(game_id), 'thumbnails')
                    os.makedirs(dst_dir, exist_ok=True)
                    basename = os.path.basename(src_thumb)
                    safe_name = self._sanitize_filename(basename)
                    dst_path = self._avoid_collision(dst_dir, safe_name)
                    if os.path.abspath(src_thumb) != os.path.abspath(dst_path):
                        shutil.copy2(src_thumb, dst_path)
                    rel_dst_path = dst_path.replace('\\', '/')
                    self.game_service.update_setting(game_id, 'thumbnail_path', rel_dst_path)
                except Exception as copy_err:
                    messagebox.showwarning("Uyarı", f"Küçük resim kopyalanamadı: {copy_err}")

            # Handle music copy (optional)
            src_music = self.music_path_var.get().strip()
            if src_music:
                try:
                    if not os.path.isfile(src_music):
                        raise FileNotFoundError("Seçilen müzik dosyası bulunamadı.")
                    dst_dir = os.path.join('assets', 'games', str(game_id), 'audio')
                    os.makedirs(dst_dir, exist_ok=True)
                    basename = os.path.basename(src_music)
                    safe_name = self._sanitize_filename(basename)
                    dst_path = self._avoid_collision(dst_dir, safe_name)
                    if os.path.abspath(src_music) != os.path.abspath(dst_path):
                        shutil.copy2(src_music, dst_path)
                    rel_dst_path = dst_path.replace('\\', '/')
                    self.game_service.update_setting(game_id, 'music_path', rel_dst_path)
                except Exception as copy_err:
                    messagebox.showwarning("Uyarı", f"Müzik kopyalanamadı: {copy_err}")

            # Save description
            new_desc = self.game_description_text.get("1.0", tk.END).strip()
            game = self.game_service.get_game(game_id)
            if game and new_desc != (game.description or ""):
                self.game_service.update_game(game_id, game.name, new_desc)
            
            messagebox.showinfo("Başarılı", "Ayarlar başarıyla kaydedildi.")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar kaydedilirken bir hata oluştu: {str(e)}")

    def _browse_start_bg(self) -> None:
        """Open a file dialog to select a background image."""
        file_path = filedialog.askopenfilename(
            title="Arkaplan Görseli Seç",
            filetypes=[
                ("Görüntü Dosyaları", "*.png;*.jpg;*.jpeg;*.bmp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg;*.jpeg"),
                ("Bitmap", "*.bmp"),
                ("Tümü", "*.*")
            ]
        )
        if file_path:
            self.start_bg_path_var.set(file_path)

    def _browse_thumbnail(self) -> None:
        """Open a file dialog to select a thumbnail image."""
        file_path = filedialog.askopenfilename(
            title="Küçük Resim Seç",
            filetypes=[
                ("Görüntü Dosyaları", "*.png;*.jpg;*.jpeg;*.bmp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg;*.jpeg"),
                ("Bitmap", "*.bmp"),
                ("Tümü", "*.*")
            ]
        )
        if file_path:
            self.thumb_path_var.set(file_path)

    def _browse_music(self) -> None:
        """Open a file dialog to select a music file."""
        file_path = filedialog.askopenfilename(
            title="Müzik Seç",
            filetypes=[
                ("Ses Dosyaları", "*.mp3;*.wav;*.ogg"),
                ("MP3", "*.mp3"),
                ("WAV", "*.wav"),
                ("OGG", "*.ogg"),
                ("Tümü", "*.*")
            ]
        )
        if file_path:
            self.music_path_var.set(file_path)

    def _sanitize_filename(self, name: str) -> str:
        """Convert filename to ASCII lowercase and replace unsafe chars with underscores."""
        name = name.strip().lower()
        # Normalize and strip non-ASCII
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')
        # Split extension
        base, ext = os.path.splitext(name)
        # Keep only safe chars
        safe_base = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in base)
        safe_ext = ''.join(c if c.isalnum() else '' for c in ext)
        ext = ('.' + safe_ext) if safe_ext else ''
        if not safe_base:
            safe_base = 'file'
        return safe_base + ext

    def _avoid_collision(self, directory: str, filename: str) -> str:
        """If filename exists in directory, append counter to avoid overwrite."""
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base}_{counter}{ext}")
            counter += 1
        return candidate

    def _resize_and_copy_image(self, src_path: str, dst_dir: str, enable_scale: bool, w_str: str, h_str: str, keep_ratio: bool) -> str:
        if not os.path.isfile(src_path):
            raise FileNotFoundError("Kaynak dosya bulunamadı")
        basename = os.path.basename(src_path)
        safe_name = self._sanitize_filename(basename)
        dst_path = self._avoid_collision(dst_dir, safe_name)
        if not enable_scale:
            if os.path.abspath(src_path) != os.path.abspath(dst_path):
                shutil.copy2(src_path, dst_path)
            return dst_path
        # Determine size
        img = Image.open(src_path)
        orig_w, orig_h = img.size
        new_w = int(w_str) if w_str.isdigit() and int(w_str) > 0 else None
        new_h = int(h_str) if h_str.isdigit() and int(h_str) > 0 else None
        if keep_ratio:
            if new_w and not new_h:
                new_h = int(round(orig_h * (new_w / orig_w)))
            elif new_h and not new_w:
                new_w = int(round(orig_w * (new_h / orig_h)))
            elif new_w and new_h:
                # Prefer width to compute height
                new_h = int(round(orig_h * (new_w / orig_w)))
            else:
                # No size provided, fallback to original copy
                if os.path.abspath(src_path) != os.path.abspath(dst_path):
                    shutil.copy2(src_path, dst_path)
                return dst_path
        else:
            # Not keeping ratio: require at least one dim
            if not new_w and not new_h:
                if os.path.abspath(src_path) != os.path.abspath(dst_path):
                    shutil.copy2(src_path, dst_path)
                return dst_path
            if not new_w:
                new_w = orig_w
            if not new_h:
                new_h = orig_h
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        # Save with same extension
        resized.save(dst_path)
        return dst_path
