"""Settings tab for the game editor."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
import unicodedata
from typing import Dict, Any, Optional, Callable

from ...core.services import GameService
from ...utils import format_filetypes_for_dialog


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
            #self.start_bg_path_var.set(settings.get('start_background_path', ''))

            # Background scaling options
            #self.bg_scale_enable_var.set(settings.get('bg_scale_enable', False))
            #self.bg_scale_w_var.set(settings.get('bg_scale_w', ''))
            #self.bg_scale_h_var.set(settings.get('bg_scale_h', ''))
            #self.bg_scale_keep_ratio_var.set(settings.get('bg_scale_keep_ratio', True))

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



            # Handle thumbnail copy (optional)
            src_thumb = self.thumb_path_var.get().strip()
            if src_thumb:
                try:
                    # Dosya varlığını kontrol et
                    if not os.path.isfile(src_thumb):
                        messagebox.showwarning("Uyarı", "Seçilen küçük resim dosyası bulunamadı. Ayarlar kaydedildi ancak thumbnail eklenmedi.")
                    else:
                        # Dosya uzantısını kontrol et
                        valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
                        if not src_thumb.lower().endswith(valid_extensions):
                            messagebox.showwarning("Uyarı", "Geçersiz dosya formatı. Sadece PNG, JPG, JPEG, BMP veya GIF dosyaları desteklenir.")
                        else:
                            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
                            dst_dir = os.path.join(project_root, 'assets', 'games', str(game_id), 'thumbnails')
                            
                            # Hedef dizini oluştur
                            try:
                                os.makedirs(dst_dir, exist_ok=True)
                            except OSError as dir_err:
                                raise OSError(f"Hedef dizin oluşturulamadı: {dir_err}")
                            
                            basename = os.path.basename(src_thumb)
                            safe_name = self._sanitize_filename(basename)
                            dst_path = self._avoid_collision(dst_dir, safe_name)
                            
                            # Dosyayı kopyala (kaynak ve hedef aynı değilse)
                            if os.path.abspath(src_thumb) != os.path.abspath(dst_path):
                                try:
                                    shutil.copy2(src_thumb, dst_path)
                                except (IOError, OSError) as copy_err:
                                    raise IOError(f"Dosya kopyalanamadı: {copy_err}")
                            
                            # Veritabanına kaydet
                            rel_dst_path = os.path.relpath(dst_path, project_root).replace('\\', '/')
                            self.game_service.update_setting(game_id, 'thumbnail_path', rel_dst_path)
                except Exception as copy_err:
                    messagebox.showwarning("Uyarı", f"Küçük resim işlenirken hata oluştu: {str(copy_err)}\nDiğer ayarlar kaydedildi.")

            # Handle music copy (optional)
            src_music = self.music_path_var.get().strip()
            if src_music:
                try:
                    # Dosya varlığını kontrol et
                    if not os.path.isfile(src_music):
                        messagebox.showwarning("Uyarı", "Seçilen müzik dosyası bulunamadı. Ayarlar kaydedildi ancak müzik eklenmedi.")
                    else:
                        # Dosya uzantısını kontrol et
                        valid_extensions = ('.mp3', '.wav', '.ogg')
                        if not src_music.lower().endswith(valid_extensions):
                            messagebox.showwarning("Uyarı", "Geçersiz dosya formatı. Sadece MP3, WAV veya OGG dosyaları desteklenir.")
                        else:
                            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
                            dst_dir = os.path.join(project_root, 'assets', 'games', str(game_id), 'audio')
                            
                            # Hedef dizini oluştur
                            try:
                                os.makedirs(dst_dir, exist_ok=True)
                            except OSError as dir_err:
                                raise OSError(f"Hedef dizin oluşturulamadı: {dir_err}")
                            
                            basename = os.path.basename(src_music)
                            safe_name = self._sanitize_filename(basename)
                            dst_path = self._avoid_collision(dst_dir, safe_name)
                            
                            # Dosyayı kopyala (kaynak ve hedef aynı değilse)
                            if os.path.abspath(src_music) != os.path.abspath(dst_path):
                                try:
                                    shutil.copy2(src_music, dst_path)
                                except (IOError, OSError) as copy_err:
                                    raise IOError(f"Dosya kopyalanamadı: {copy_err}")
                            
                            # Veritabanına kaydet
                            rel_dst_path = os.path.relpath(dst_path, project_root).replace('\\', '/')
                            self.game_service.update_setting(game_id, 'music_path', rel_dst_path)
                except Exception as copy_err:
                    messagebox.showwarning("Uyarı", f"Müzik işlenirken hata oluştu: {str(copy_err)}\nDiğer ayarlar kaydedildi.")

            # Save description
            new_desc = self.game_description_text.get("1.0", tk.END).strip()
            game = self.game_service.get_game(game_id)
            if game and new_desc != (game.description or ""):
                self.game_service.update_game(game_id, game.name, new_desc)
            
            messagebox.showinfo("Başarılı", "Ayarlar başarıyla kaydedildi.")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar kaydedilirken bir hata oluştu: {str(e)}")

    def _browse_thumbnail(self) -> None:
        """Thumbnail görsel dosyası seçmek için dosya diyaloğu açar."""
        try:
            # Platform-agnostic dosya türleri
            filetypes = format_filetypes_for_dialog([
                ("Görüntü Dosyaları", "*.png *.jpg *.jpeg *.bmp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("Bitmap", "*.bmp"),
                ("Tüm Dosyalar", "*.*")
            ])
            
            file_path = filedialog.askopenfilename(
                title="Küçük Resim Seç",
                filetypes=filetypes
            )
            if file_path:
                # Dosyanın var olduğunu ve okunabilir olduğunu kontrol et
                if not os.path.isfile(file_path):
                    messagebox.showerror("Hata", "Seçilen dosya bulunamadı.")
                    return
                
                # Dosya boyutunu kontrol et (örn. max 10MB)
                file_size = os.path.getsize(file_path)
                if file_size > 10 * 1024 * 1024:  # 10MB
                    messagebox.showwarning("Uyarı", "Seçilen dosya çok büyük (max 10MB).")
                    return
                
                self.thumb_path_var.set(file_path)
        except Exception as e:
            messagebox.showerror("Hata", f"Dosya seçilirken bir hata oluştu: {str(e)}")

    def _browse_music(self) -> None:
        """Müzik dosyası seçmek için dosya diyaloğu açar."""
        try:
            # Platform-agnostic dosya türleri
            filetypes = format_filetypes_for_dialog([
                ("Ses Dosyaları", "*.mp3 *.wav *.ogg"),
                ("MP3", "*.mp3"),
                ("WAV", "*.wav"),
                ("OGG", "*.ogg"),
                ("Tüm Dosyalar", "*.*")
            ])
            
            file_path = filedialog.askopenfilename(
                title="Müzik Seç",
                filetypes=filetypes
            )
            if file_path:
                # Dosyanın var olduğunu ve okunabilir olduğunu kontrol et
                if not os.path.isfile(file_path):
                    messagebox.showerror("Hata", "Seçilen dosya bulunamadı.")
                    return
                
                # Dosya boyutunu kontrol et (örn. max 50MB)
                file_size = os.path.getsize(file_path)
                if file_size > 50 * 1024 * 1024:  # 50MB
                    messagebox.showwarning("Uyarı", "Seçilen dosya çok büyük (max 50MB).")
                    return
                
                self.music_path_var.set(file_path)
        except Exception as e:
            messagebox.showerror("Hata", f"Dosya seçilirken bir hata oluştu: {str(e)}")

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


