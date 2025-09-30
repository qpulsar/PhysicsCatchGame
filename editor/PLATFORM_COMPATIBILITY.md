# Platform Uyumluluğu

Bu belge, editörün macOS ve Windows platformlarında sorunsuz çalışması için yapılan iyileştirmeleri açıklar.

## Yapılan İyileştirmeler

### 1. Platform Tespit ve Yardımcı Fonksiyonlar (`editor/utils.py`)

Yeni oluşturulan `utils.py` modülü, platform-bağımsız işlemler için yardımcı fonksiyonlar sağlar:

- **`get_platform()`**: Mevcut işletim sistemini tespit eder ('darwin', 'windows', 'linux')
- **`is_macos()`**, **`is_windows()`**, **`is_linux()`**: Platform kontrolü için boolean fonksiyonlar
- **`format_filetypes_for_dialog()`**: Dosya diyaloğu için dosya türlerini platforma göre formatlar
  - macOS: Uzantılar boşlukla ayrılır (örn: `*.png *.jpg`)
  - Windows: Uzantılar noktalı virgülle ayrılır (örn: `*.png;*.jpg`)
- **`get_path_separator()`**: İşletim sistemine göre yol ayırıcısını döndürür
- **`normalize_path()`**: Yolu işletim sistemine göre normalize eder

### 2. Dosya Diyalogları

Tüm dosya diyalogları (`filedialog.askopenfilename`, `filedialog.askopenfilenames`) artık `format_filetypes_for_dialog()` fonksiyonunu kullanarak platforma uygun dosya türü formatı sağlar.

#### Güncellenen Dosyalar:
- `editor/ui/tabs/settings_tab.py`
  - `_browse_thumbnail()`: Thumbnail görsel seçimi
  - `_browse_music()`: Müzik dosyası seçimi
- `editor/ui/tabs/media_tab.py`
  - `_upload_media()`: Medya dosyası yükleme

### 3. Yol Ayırıcıları

Veritabanında ve dahili depolamada **her zaman forward slash (`/`)** kullanılır. Bu, her iki platformda da tutarlı çalışmayı sağlar.

Dosya sistemi işlemleri için `os.path.join()` ve `os.path.relpath()` kullanılır, bu fonksiyonlar otomatik olarak platforma uygun yol ayırıcılarını kullanır.

### 4. Hata Yönetimi

Tüm dosya diyalogları ve dosya işlemleri için kapsamlı try-except blokları eklendi:
- Dosya varlık kontrolü
- Dosya boyutu kontrolü
- Dosya formatı doğrulaması
- Kullanıcı dostu hata mesajları

## Kullanım Örnekleri

### Platform Kontrolü
```python
from editor.utils import is_macos, is_windows

if is_macos():
    print("macOS üzerinde çalışıyor")
elif is_windows():
    print("Windows üzerinde çalışıyor")
```

### Dosya Diyaloğu
```python
from tkinter import filedialog
from editor.utils import format_filetypes_for_dialog

# Platform-bağımsız dosya türleri
filetypes = format_filetypes_for_dialog([
    ("Görüntü Dosyaları", "*.png *.jpg *.jpeg"),
    ("Tüm Dosyalar", "*.*")
])

file_path = filedialog.askopenfilename(
    title="Dosya Seç",
    filetypes=filetypes
)
```

### Yol Normalizasyonu
```python
from editor.utils import normalize_path

# Platforma uygun yol
path = normalize_path("assets/images/sprite.png")
```

## Test Edilmesi Gerekenler

### macOS
- [x] Thumbnail seçimi
- [x] Müzik dosyası seçimi
- [x] Medya yükleme
- [ ] Tüm dosya diyalogları

### Windows
- [ ] Thumbnail seçimi
- [ ] Müzik dosyası seçimi
- [ ] Medya yükleme
- [ ] Tüm dosya diyalogları
- [ ] Yol ayırıcı işlemleri

## Bilinen Sorunlar

Şu anda bilinen platform-spesifik sorun bulunmamaktadır.

## Gelecek İyileştirmeler

1. Tüm dosya işlemlerinde `pathlib.Path` kullanımına geçiş
2. Platform-spesifik UI tema ayarları
3. Otomatik platform testi için CI/CD entegrasyonu
