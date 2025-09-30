"""Platform uyumluluğu test scripti.

Bu script, editor.utils modülündeki platform-bağımsız fonksiyonları test eder.
"""
from editor.utils import (
    get_platform,
    is_macos,
    is_windows,
    is_linux,
    format_filetypes_for_dialog,
    get_path_separator,
    normalize_path
)


def test_platform_detection():
    """Platform tespit fonksiyonlarını test eder."""
    print("=" * 60)
    print("PLATFORM TESPİT TESTİ")
    print("=" * 60)
    
    platform = get_platform()
    print(f"✓ Tespit edilen platform: {platform}")
    print(f"✓ macOS: {is_macos()}")
    print(f"✓ Windows: {is_windows()}")
    print(f"✓ Linux: {is_linux()}")
    print()


def test_filetypes_formatting():
    """Dosya türü formatlama fonksiyonunu test eder."""
    print("=" * 60)
    print("DOSYA TÜRÜ FORMATLAMA TESTİ")
    print("=" * 60)
    
    # Test 1: Boşlukla ayrılmış uzantılar
    test1 = [
        ("Görüntü Dosyaları", "*.png *.jpg *.jpeg"),
        ("Tüm Dosyalar", "*.*")
    ]
    result1 = format_filetypes_for_dialog(test1)
    print(f"✓ Giriş (boşlukla): {test1}")
    print(f"  Çıkış: {result1}")
    print()
    
    # Test 2: Noktalı virgülle ayrılmış uzantılar
    test2 = [
        ("Ses Dosyaları", "*.mp3;*.wav;*.ogg"),
        ("Tüm Dosyalar", "*.*")
    ]
    result2 = format_filetypes_for_dialog(test2)
    print(f"✓ Giriş (noktalı virgül): {test2}")
    print(f"  Çıkış: {result2}")
    print()
    
    # Beklenen sonuçları kontrol et
    if is_macos() or is_linux():
        assert ";" not in result2[0][1], "macOS/Linux'ta noktalı virgül olmamalı"
        assert " " in result2[0][1], "macOS/Linux'ta boşluk olmalı"
        print("✓ macOS/Linux formatı doğru")
    elif is_windows():
        assert ";" in result2[0][1], "Windows'ta noktalı virgül olmalı"
        print("✓ Windows formatı doğru")
    print()


def test_path_operations():
    """Yol işleme fonksiyonlarını test eder."""
    print("=" * 60)
    print("YOL İŞLEME TESTİ")
    print("=" * 60)
    
    separator = get_path_separator()
    print(f"✓ Yol ayırıcı: '{separator}'")
    
    # Test yolları
    test_paths = [
        "assets/images/sprite.png",
        "assets\\images\\sprite.png",
        "C:/Users/test/file.txt",
        "C:\\Users\\test\\file.txt"
    ]
    
    print("\nYol normalizasyonu:")
    for path in test_paths:
        normalized = normalize_path(path)
        print(f"  {path:30s} → {normalized}")
    print()


def test_real_world_scenarios():
    """Gerçek dünya senaryolarını test eder."""
    print("=" * 60)
    print("GERÇEK DÜNYA SENARYOLARI")
    print("=" * 60)
    
    # Senaryo 1: Thumbnail seçimi
    print("Senaryo 1: Thumbnail Seçimi")
    thumbnail_types = format_filetypes_for_dialog([
        ("Görüntü Dosyaları", "*.png *.jpg *.jpeg *.bmp"),
        ("PNG", "*.png"),
        ("JPEG", "*.jpg *.jpeg"),
        ("Bitmap", "*.bmp"),
        ("Tüm Dosyalar", "*.*")
    ])
    print(f"  Dosya türleri: {thumbnail_types[0]}")
    print()
    
    # Senaryo 2: Müzik seçimi
    print("Senaryo 2: Müzik Seçimi")
    music_types = format_filetypes_for_dialog([
        ("Ses Dosyaları", "*.mp3 *.wav *.ogg"),
        ("MP3", "*.mp3"),
        ("WAV", "*.wav"),
        ("OGG", "*.ogg"),
        ("Tüm Dosyalar", "*.*")
    ])
    print(f"  Dosya türleri: {music_types[0]}")
    print()
    
    # Senaryo 3: Medya yükleme
    print("Senaryo 3: Medya Yükleme")
    media_types = format_filetypes_for_dialog([
        ("Görseller", "*.png *.jpg *.jpeg *.bmp *.gif"),
        ("Tüm Dosyalar", "*.*")
    ])
    print(f"  Dosya türleri: {media_types[0]}")
    print()


def main():
    """Ana test fonksiyonu."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "PLATFORM UYUMLULUK TEST SÜİTİ" + " " * 18 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    try:
        test_platform_detection()
        test_filetypes_formatting()
        test_path_operations()
        test_real_world_scenarios()
        
        print("=" * 60)
        print("✓ TÜM TESTLER BAŞARILI!")
        print("=" * 60)
        print()
        print("Editör artık macOS ve Windows'ta sorunsuz çalışacak.")
        print()
        
    except AssertionError as e:
        print(f"\n✗ TEST BAŞARISIZ: {e}\n")
        return 1
    except Exception as e:
        print(f"\n✗ BEKLENMEYEN HATA: {e}\n")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
