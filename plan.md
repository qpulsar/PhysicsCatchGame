# FizikselB Oyunu Geliştirme Planı

Bu plan, mevcut kod tabanını kullanarak sepetten düşen nesneleri toplama oyununu geliştirmek için gereken adımları özetlemektedir.

## Bölüm 1: Editör Geliştirmeleri (`tkinter/ttk`)

### 1.1. Sprite Yönetim Arayüzü
Oyun içerisindeki nesnelerin görsellerini yönetmek için esnek bir yapı kurulacak.

-   **Yeni Sekme:** Editöre "Sprite Yönetimi" adında yeni bir sekme eklenecek.
-   **Sprite Sheet Yükleme:** Kullanıcının bilgisayarından bir sprite sheet (tek bir resim dosyası içinde birden çok görsel barındıran dosya) seçip yüklemesine olanak sağlanacak.
-   **Görsel Seçim Alanı:** Yüklenen sprite sheet bir canvas üzerinde gösterilecek. Kullanıcı bu canvas üzerinde fare ile bir dikdörtgen çizerek sprite'ın koordinatlarını (x, y, genişlik, yükseklik) belirleyebilecek.
-   **Sprite-İfade İlişkisi:** Tanımlanan her sprite, "İfadeler" sekmesindeki bir ifade (örneğin "bakır tel", "plastik tarak") ile ilişkilendirilecek. Bu sayede oyunda hangi ifadenin hangi görselle düşeceği belirlenecek.

### 1.2. Seviye Yönetimi Detayları
Her seviyenin kendine özgü kurallarının ve hedeflerinin olabilmesi için seviye ayarları detaylandırılacak.

-   **Hedef Belirleme:** "Seviyeler" sekmesinde, her seviye için oyuncunun yakalaması gereken "hedef kategori" (ör: "iletkenler") veya "hedef ifadeler" seçilebilecek bir arayüz eklenecek.
-   **Seviye Ayarları:** Her seviye için aşağıdaki gibi özel ayarların yapılabileceği alanlar eklenecek:
    -   Nesnelerin düşme hızı.
    -   Ekranda aynı anda bulunabilecek maksimum nesne sayısı.
    -   Seviyeyi tamamlamak için gereken skor veya yakalanan doğru nesne sayısı.
    -   O seviyedeki yanlış yapma hakkı.

### 1.3. Oyunlaştırma (Gamification) - Rozet Yönetimi
Oyuncuları motive etmek için bir rozet sistemi eklenecek.

-   **Yeni Sekme:** Editöre "Rozetler" adında yeni bir sekme eklenecek.
-   **Rozet Tanımlama:** Bu sekmede yeni rozetler oluşturulabilecek. Her rozet için:
    -   Ad (ör: "İletken Uzmanı").
    -   Açıklama (ör: "10 iletkeni hatasız yakaladın!").
    -   Görsel (basit bir resim dosyası).
    -   Kazanma koşulu (ör: `seviye=2`, `hatasız_yakalama_serisi=10`).

## Bölüm 2: Oyun Mekanikleri (`pygame`)

### 2.1. Konu Seçim Ekranı (Tamamlandı)
Oyuncu, oynamak istediği konuyu (editörde oluşturulmuş oyun) seçebilecek.

-   **Menü:** Oyunun başlangıcına, veritabanında kayıtlı olan oyun konularını listeleyen bir menü ekranı eklenecek.

### 2.2. Dinamik Veri Yükleme
Oyun, seçilen konuya göre kendini yapılandıracak.

-   **Veri Akışı:** `LevelManager` ve diğer yöneticiler, oyuncunun menüden seçtiği konunun verilerini (seviyeler, ifadeler, sprite'lar, rozetler) veritabanından okuyacak şekilde güncellenecek.

### 2.3. Sprite Entegrasyonu
Metin tabanlı düşen nesneler, görsellerle değiştirilecek.

-   **Görselleştirme:** `Item` sınıfı, artık sadece metin değil, veritabanından gelen sprite sheet ve koordinat bilgilerini kullanarak ilgili görseli ekranda gösterecek şekilde güncellenecek.

### 2.4. Rozet Kazanma Sistemi

### 2.5. Oyun Bilgi Ekranı (Tamamlandı)
Seçilen oyun için ad, açıklama/kuralların gösterildiği ve "Başla" düğmesi ile oyuna geçiş yapılan ekran eklendi.
Oyun, oyuncunun başarılarını takip edecek ve rozetleri verecek.

-   **Takip Mekanizması:** Oyuncunun ilerlemesini (yakalanan nesneler, tamamlanan seviyeler, yapılan hatalar) takip eden bir sistem geliştirilecek.
-   **Rozet Bildirimi:** Bir rozetin kazanma koşulu sağlandığında ekranda bir bildirim gösterilecek.

## Bölüm 3: Veritabanı Değişiklikleri (`game_data.db`)

Yukarıdaki özellikleri desteklemek için veritabanı şeması güncellenecek.

-   **Yeni Tablolar:**
    -   `Sprites`: Yüklenen sprite sheet dosyalarını tutar (`sprite_id`, `game_id`, `dosya_yolu`).
    -   `SpriteDefinitions`: Bir sprite sheet içerisindeki her bir görselin tanımını tutar (`definition_id`, `sprite_id`, `ifade_id`, `x`, `y`, `genislik`, `yukseklik`).
    -   `Badges`: Tanımlanan rozetleri tutar (`badge_id`, `game_id`, `ad`, `aciklama`, `resim_yolu`, `kazanma_kosulu`).
-   **Tablo Güncellemeleri:**
    -   `Levels` tablosuna seviyeye özel ayarlar için yeni kolonlar eklenecek (`hedef_kategori_id`, `nesne_hizi` vb.).
