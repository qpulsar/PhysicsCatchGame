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
    """Yolu işletim sistemine göre normalize eder.
    
    Args:
        path: Normalize edilecek yol
    
    Returns:
        Normalize edilmiş yol
    """
    if is_windows():
        return path.replace('/', '\\')
    else:
        return path.replace('\\', '/')
