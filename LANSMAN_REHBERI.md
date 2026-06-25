# QuizRoyale — Lansman Rehberi

## 1. App Store Connect Adımları

### 1.1 Uygulama Oluşturma
- App Store Connect > "Yeni Uygulama" > iOS platformu seç
- Bundle ID: `com.quizroyale.app`
- SKU: `QUIZROYALE_TR_001`
- Birincil dil: Türkçe
- Uygulama adı: `QuizRoyale`

### 1.2 Türkçe Metadata

**Uygulama Başlığı (30 karakter):**
```
QuizRoyale – Canlı Trivia
```

**Altyazı (30 karakter):**
```
20 kişi, 5 tur, 1 şampiyon!
```

**Açıklama (4000 karakter):**
```
QuizRoyale — Türkiye'nin ilk canlı battle royale trivia oyunu!

20 oyuncu aynı anda yarışır. Her turda yanlış cevap verenler elenir.
Son ayakta kalan kazanır. Sen de şampiyon olabilir misin?

NASIL OYNANIR?
• "Hızlı Maç"a bas, 20 saniyelik lobiye katıl
• 5 turda soru tiplerini aş: Doğru/Yanlış, Görsel, Karşılaştırma, 4 Şıklı, Slider Tahmini
• Yanlış cevap? Ekrandan düş! (Fall Guys gibi)
• Final turunda en doğru tahmini yapan şampiyon olur!

ÖZELLİKLER
✓ Gerçek zamanlı 20 kişilik maçlar
✓ 5 farklı soru türü, her turda farklı meydan okuma
✓ Eğlenceli düşme animasyonları
✓ Günlük/Haftalık/Tüm Zamanlar liderlik tablosu
✓ Emoji reaksiyonları ile sosyal etkileşim
✓ Arkadaşlarını ekle, kim daha iyi gör!
✓ 2-3 dakikada tam bir maç — her an oynayabilirsin

Popüler kültür, genel kültür, spor, bilim, Türkiye'ye özel sorular ve daha fazlası!

Ücretsiz oyna, herkesle yarış, şampiyon ol!
```

**Arama Anahtar Kelimeleri (100 karakter):**
```
trivia,quiz,bilgi yarışması,canlı oyun,battle royale,eğlence,arkadaş,rekabet
```

### 1.3 Ekran Görüntüleri Gereksinimleri

Her boyut için gerekli görseller:
- **6.7" (iPhone 14 Pro Max):** 1290 × 2796 px — 3 adet minimum
- **6.5" (iPhone 11 Pro Max):** 1242 × 2688 px
- **5.5" (iPhone 8 Plus):** 1242 × 2208 px
- **iPad Pro 12.9":** 2048 × 2732 px

**Önerilen ekran görüntüsü sırası:**
1. Ana menü — "Hızlı Maç" vurgulanmış
2. Lobi bekleme — "12/20 oyuncu" sayacı
3. Oyun ekranı — soru ve avatarlar
4. Düşme animasyonu — elenme anı
5. Liderlik tablosu — podyum görseli

### 1.4 Gizlilik Beyanı
- Gizlilik politikası URL'si ekle: `https://quizroyale.com/privacy`
- Veri toplama beyan: Kullanıcı adı, e-posta, oyun verisi, reklam tanımlayıcı
- Üçüncü taraflarla paylaşım: Firebase, AdMob, analitik

### 1.5 Fiyatlandırma
- Uygulama ücretsiz
- Uygulama içi satın alma: Gem paketleri (3. ayda eklenecek)
- Reklam destekli model

---

## 2. Google Play Store Adımları

### 2.1 Uygulama Oluşturma
- Google Play Console > "Uygulama oluştur"
- Uygulama adı: `QuizRoyale`
- Varsayılan dil: Türkçe (tr)
- Uygulama türü: Oyun
- Ücretsiz

### 2.2 Play Store Türkçe Metadata

**Kısa Açıklama (80 karakter):**
```
20 kişilik canlı trivia battle royale! Soruları bil, rakipleri geç, kazan!
```

**Tam Açıklama:** (App Store açıklamasını kullan, biraz düzenle)

**Uygulama Kategorisi:** Kelime & Trivia

**İçerik Derecelendirmesi:**
- PEGI/IARC anketi doldur
- Şiddet: Yok | Cinsel İçerik: Yok | Kumar: Yok | Reklam: Var

### 2.3 Play Store Görseller
- **Öne Çıkan Grafik:** 1024 × 500 px
- **Uygulama Simgesi:** 512 × 512 px
- **Ekran Görüntüleri:** Min 2, max 8 adet (mobil)
- **Tanıtım Videosu (Opsiyonel):** YouTube URL

### 2.4 Uygulama İmzalama
- Play App Signing aktif et (Google yönetir)
- Upload key ayrı sakla (`.jks` dosyası)
- `key.properties` Git'e commit etme!

---

## 3. KVKK Uyum Kontrol Listesi

### 3.1 Zorunlu Belgeler
- [ ] Aydınlatma Metni hazır ve erişilebilir
- [ ] Gizlilik Politikası hazır (`/privacy` endpoint)
- [ ] Kullanım Koşulları hazır (`/terms` endpoint)
- [ ] KVKK uyum beyanı imzalandı

### 3.2 Teknik Gereksinimler
- [ ] Kullanıcı kaydında açık rıza onay kutusu mevcut
- [ ] Pazarlama e-postası için ayrı onay (opt-in)
- [ ] Hesap silme özelliği mevcut (Ayarlar > Hesabı Sil)
- [ ] Veri ihracat özelliği mevcut (kullanıcı verisi indirme)
- [ ] Çerez/reklam tanımlayıcı için onay akışı (Android 13+ / iOS 14.5+)
- [ ] Firebase Analytics için `analytics_storage` onayı
- [ ] AdMob için `ad_storage` onayı

### 3.3 Veri Minimizasyonu
- Yaş ve cinsiyet bilgisi isteğe bağlı
- Telefon rehberi erişimi sadece isteğe bağlı arkadaş önerisi için
- Kamera sadece QR okuma için
- Konum verisi toplanmıyor

### 3.4 Veri Saklama Politikası
- Hesap silinince: 30 gün içinde tüm veriler imha
- Oyun log'ları: 90 gün saklanır, sonra anonim
- Leaderboard: 3 sezon (9 ay) saklanır
- Reklam tanımlayıcılar: Kullanıcı reddettiğinde anında silinir

---

## 4. Soft Launch Stratejisi

### 4.1 Aşama 1 — Türkiye (1. ve 2. Hafta)

**Hedef:**
- 500-1.000 gerçek kullanıcı
- Kritik crash'leri tespit et
- Lobi doluluk oranını ölç

**Kanallar:**
- Twitter/X: Lansman duyurusu + demo video
- Instagram Reels: Gameplay klibi (15-30 sn)
- Reddit r/Turkey, r/mobilegaming
- Product Hunt (Türkiye arkadaş ağı)
- Teknoloji blog'ları (Webtekno, ShiftDelete, Donanımhaber)

**Hedef Metrikler:**
- Crash rate < %1
- D1 retention > %20
- Ortalama oyun/kullanıcı/gün > 3
- Lobi doluluk oranı > %80

### 4.2 Aşama 2 — Global (3. Hafta+)

Türkiye sonuçları iyi ise:
- İngilizce soru seti tamamla (en az 500 soru)
- App Store / Play Store metadata İngilizce ekle
- Hedef pazarlar: Almanya (Türk diaspora), ABD, İngiltere
- ASO optimizasyonu: İngilizce anahtar kelimeler

### 4.3 Geri Dönüş Planı

Lobi doluluk oranı < %50 ise:
- Bot oranını geçici olarak %100'e çıkar
- Lobi geri sayımı 30 saniyeye uzat
- Sosyal paylaşım teşviki ekle (arkadaşını davet et = coin)

---

## 5. İzlenecek Kritik Metrikler

### 5.1 Teknik Sağlık
| Metrik | Hedef | Kritik Eşik |
|--------|-------|-------------|
| Crash rate | < %0.5 | > %1 → acil hotfix |
| ANR rate | < %0.1 | > %0.5 → acil |
| API response time (p95) | < 200ms | > 500ms → alarm |
| WebSocket drop rate | < %2 | > %5 → alarm |

### 5.2 Kullanıcı Davranışı
| Metrik | Hedef | Açıklama |
|--------|-------|---------|
| D1 Retention | > %20 | İlk günden geri dönüş |
| D7 Retention | > %12 | Alışkanlık testi |
| D30 Retention | > %8 | Uzun vadeli bağlılık |
| Ortalama oturum | 3-5 dk | Kısa ama yoğun |
| Oyun/kullanıcı/gün | > 3 | Tekrar oynama isteği |

### 5.3 İş Metrikleri
| Metrik | Hedef | |
|--------|-------|-|
| Lobi fill rate | > %80 | Oyun başlama başarısı |
| Bot oranı | < %50 | Gerçek oyuncu yoğunluğu |
| Reklam görüntüleme | > %60 | İzleyen oranı |
| Reklam iptali | < %30 | Rewarded reklam tamamlama |

---

## 6. İlk 2 Hafta Sosyal Medya Takvimi

### Gün 1 — Lansman
- Twitter/X: "QuizRoyale yayında! 20 kişiyle canlı trivia savaşı. İndir ve dene!" + App Store linki
- Instagram: Gameplay trailer Reels (15 sn)
- TikTok: Ekran kaydı highlight (eleme anı)

### Gün 2
- Tweet thread: "QuizRoyale nasıl çalışır? 5 adımda anlattım:"
- Instagram Story: Arkadaşını etiketle challenge

### Gün 3-5
- Kullanıcı feedbacklerini RT/repost et
- Bug report var ise şeffaf iletişim: "Bildirdiniz, düzelttik ✓"

### Gün 7 — 1. Hafta Özeti
- "İlk haftada X oyun oynandı!" paylaşımı
- Top 3 oyuncu highlight (leaderboard ekran görüntüsü)

### Gün 10
- "Günlük challenge" özelliğini tanıt
- Influencer micro-collab (10K-100K takipçi, gaming nişi)

### Gün 14
- 2. Hafta retention tweet: "X kullanıcı her gün geri dönüyor"
- Play Store review push: Uygulama içinde rating isteği aktif et

---

## 7. Post-Launch Hotfix SLA'ları

### P0 — Kritik (Oyun oynanamaz)
**Tanım:** Crash, lobi başlamıyor, giriş yapılamıyor, ödeme çalışmıyor
**Yanıt Süresi:** 30 dakika içinde kabul
**Çözüm Süresi:** 2 saat içinde hotfix yayına
**Aksiyon:** Tüm ekip alarm, gerekirse sunucu rollback

### P1 — Yüksek (Özellik bozuk)
**Tanım:** Leaderboard güncellenmiyor, animasyon bozuk, ses çalışmıyor
**Yanıt Süresi:** 2 saat
**Çözüm Süresi:** 24 saat
**Aksiyon:** Developer 1 kişi atanır, düzeltme + review + release

### P2 — Orta (Kozmetik / UX sorunu)
**Tanım:** UI hizalaması, küçük metin hatası, eksik çeviri
**Yanıt Süresi:** 24 saat
**Çözüm Süresi:** 1 hafta
**Aksiyon:** Sonraki sprint backlog'una alınır

### Hotfix Süreci
1. Sentry alarm → Slack #alerts kanalı
2. Sorumlu developer bug'ı repro eder
3. Fix branch açılır: `hotfix/p0-login-crash`
4. Hızlı code review (1 kişi yeterli P0 için)
5. Staging'e deploy, smoke test
6. Production deploy
7. Sentry'de düzeldi mi doğrula
8. Post-mortem 48 saat içinde (P0/P1 için)

---

## 8. Store Rating Stratejisi

- İlk 3 oyun sonrası (başarılı tamamlama): in-app rating isteği göster
- Kötü deneyim sonrası (elenme, reklam, hata): ASLA rating isteme
- Rating isteği reddedilirse: 30 gün sonra tekrar sor
- Hedef: App Store 4.5+, Play Store 4.3+

---

*Lansman Rehberi v1.0 — 15 Mayıs 2026 — QuizRoyale MVP*
