"""Platform-agnostic utility functions for the editor."""
import platform
import sys
from typing import List, Tuple


def get_platform() -> str:
    """İşletim sistemini tespit eder.
    
    Returns:
        'darwin' (macOS), 'windows', 'linux' veya 'unknown'
    """
    system = platform.system().lower()
    if system == 'darwin':
        return 'darwin'
    elif system == 'windows':
        return 'windows'
    elif system == 'linux':
        return 'linux'
    return 'unknown'


def is_macos() -> bool:
    """macOS üzerinde çalışıp çalışmadığını kontrol eder."""
    return get_platform() == 'darwin'


def is_windows() -> bool:
    """Windows üzerinde çalışıp çalışmadığını kontrol eder."""
    return get_platform() == 'windows'


def is_linux() -> bool:
    """Linux üzerinde çalışıp çalışmadığını kontrol eder."""
    return get_platform() == 'linux'


def format_filetypes_for_dialog(filetypes: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Dosya diyaloğu için dosya türlerini platforma göre formatlar.
    
    macOS: Uzantılar boşlukla ayrılmalı (örn: "*.png *.jpg")
    Windows: Uzantılar noktalı virgülle ayrılabilir (örn: "*.png;*.jpg")
    
    Bu fonksiyon her iki formatı da destekler ve platforma uygun şekilde döndürür.
    
    Args:
        filetypes: (açıklama, uzantılar) tuple'larının listesi
                   Uzantılar boşluk veya noktalı virgülle ayrılmış olabilir
    
    Returns:
        Platforma uygun formatlanmış filetypes listesi
    """
    if is_windows():
        # Windows için noktalı virgülle ayır
        formatted = []
        for label, extensions in filetypes:
            # Boşluklarla ayrılmışsa noktalı virgülle değiştir
            if ' ' in extensions and ';' not in extensions:
                extensions = extensions.replace(' ', ';')
            formatted.append((label, extensions))
        return formatted
    else:
        # macOS ve Linux için boşlukla ayır
        formatted = []
        for label, extensions in filetypes:
            # Noktalı virgülle ayrılmışsa boşlukla değiştir
            if ';' in extensions:
                extensions = extensions.replace(';', ' ')
            formatted.append((label, extensions))
        return formatted


def get_path_separator() -> str:
    """İşletim sistemine göre yol ayırıcısını döndürür.
    
    Returns:
        Windows için '\\', diğerleri için '/'
    """
    return '\\' if is_windows() else '/'


def normalize_path(path: str) -> str:
    """Yolu işletim sistemine göre normalize eder."""
    if is_windows():
        return path.replace('/', '\\')
    else:
        return path.replace('\\', '/')

def get_project_root() -> str:
    """Proje kök dizinini döndürür.
    
    Bundled (.exe) modunda .exe'nin yanındaki dizini,
    Geliştirme modunda ise editor/ klasörünün üstündeki dizini döndürür.
    """
    import os
    if getattr(sys, 'frozen', False):
        # Bundled executable
        return os.path.dirname(sys.executable)
    else:
        # Dev mode (editor/utils.py is in editor/)
        # We need to go up one level to get to the project root
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def pil_to_tkphoto(pil_image):
    """PIL Image nesnesini tkinter PhotoImage'e dönüştürür.
    
    PIL.ImageTk.PhotoImage yerine bu fonksiyonu kullanın.
    ImageTk, dahili olarak _imagingtk C modülüne bağımlıdır ve
    PyInstaller ile paketlenmesinde sorun yaşanmaktadır.
    Bu fonksiyon base64 kodlama ile bu bağımlılığı ortadan kaldırır.
    
    Args:
        pil_image: PIL.Image nesnesi
        
    Returns:
        tkinter.PhotoImage nesnesi
    """
    import io
    import base64
    import tkinter as tk
    
    buffer = io.BytesIO()
    pil_image.save(buffer, format='PNG')
    buffer.seek(0)
    photo_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return tk.PhotoImage(data=photo_data)
