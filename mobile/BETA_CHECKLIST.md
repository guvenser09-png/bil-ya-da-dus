# QuizRoyale — Beta Test Kontrol Listesi

**Versiyon:** 0.9.0-beta  
**Test Tarihi:** ___________  
**Test Eden:** ___________  
**Platform:** Android / iOS (işaretle)

---

## 1. Kurulum

- [ ] Uygulama mağazadan (TestFlight / Internal Track) başarıyla indirildi
- [ ] Uygulama açılışta çökmedi
- [ ] Splash ekranı sorunsuz göründü
- [ ] Onboarding slide'ları (3-4 ekran) doğru göründü ve atlanabildi
- [ ] Kayıt akışı tamamlandı (e-posta veya Google ile)
- [ ] Giriş akışı tamamlandı (giriş sonrası ana menüye yönlendirdi)
- [ ] Şifremi unuttum akışı çalıştı
- [ ] Bildirim izni sorusu göründü
- [ ] Kamera izni (QR kod için) sorusu göründü

**Notlar:**
```

```

---

## 2. Kritik Akışlar

### 2.1 Hızlı Maç Akışı
- [ ] "Hızlı Maç" butonu çalıştı
- [ ] Lobi ekranı açıldı, oyuncu sayacı güncellendi (X/20)
- [ ] 20 saniye geri sayım doğru çalıştı
- [ ] Oyun 20 saniye sonra başladı
- [ ] Tur 1 — Doğru/Yanlış sorusu göründü, 5 saniyelik sayaç çalıştı
- [ ] Doğru cevap → yeşil animasyon + puan göründü
- [ ] Yanlış cevap → kırmızı animasyon + düşme efekti çalıştı
- [ ] Tur 2 — Görsel soru (bayrak/logo) göründü
- [ ] Tur 3 — Karşılaştırma sorusu göründü
- [ ] Tur 4 — 4 şıklı soru göründü
- [ ] Tur 5 — Slider ekranı açıldı
- [ ] Slider sürüklenebildi, değer güncellendi
- [ ] Haptic feedback slider sürüklerken hissedildi
- [ ] "Kilitle" butonu çalıştı
- [ ] Süre bitince sonuçlar göründü
- [ ] Sonuç ekranında kazanan, skor ve ödüller göründü
- [ ] "Tekrar Oyna" butonu yeni lobiye götürdü
- [ ] "Ana Menü" butonu ana menüye döndü

**Notlar:**
```

```

### 2.2 Eleme Akışı
- [ ] Elenince ekranda düşme animasyonu oynamadı
- [ ] Elenen oyuncu sıradan çıktı
- [ ] Elenince "izle ve geri dön" rewarded reklam teklifi çıktı
- [ ] Rewarded reklamı izleyince oyuna devam edildi
- [ ] İkinci kez elenince reklam teklifi çıkmadı (1 kez/oyun)

**Notlar:**
```

```

### 2.3 Profil
- [ ] Profil ekranı açıldı
- [ ] Avatar göründü
- [ ] İstatistikler doğru (oynanan, kazanma %)
- [ ] Rozetler göründü
- [ ] Bio düzenlenebildi (140 karakter limiti çalıştı)
- [ ] Üyelik tarihi doğru

**Notlar:**
```

```

### 2.4 Leaderboard
- [ ] Günlük tab açıldı ve liste yüklendi
- [ ] Haftalık tab açıldı
- [ ] Tüm Zamanlar tab açıldı
- [ ] Arkadaşlar tab açıldı
- [ ] Kendi sıran altta sabit bar'da göründü
- [ ] Top 3 podyum animasyonu çalıştı
- [ ] Başka oyuncunun profiline tıklandı ve açıldı
- [ ] Sezon geri sayımı göründü

**Notlar:**
```

```

### 2.5 Arkadaşlık
- [ ] Oyun sonu ekranında "Arkadaş Ekle" butonu çalıştı
- [ ] Kullanıcı adıyla arama çalıştı
- [ ] İstek gönderildi
- [ ] Gelen istek bildirimi alındı (push veya uygulama içi)
- [ ] Arkadaş listesi göründü
- [ ] Arkadaşla birlikte oyun oynandı (arkadaşlar tab'ında göründü)

**Notlar:**
```

```

### 2.6 Reklamlar
- [ ] Oyun sonu interstitial reklam açıldı ve kapanabildi (5 sn sonra)
- [ ] Banner reklam lobi bekleme ekranında göründü
- [ ] Rewarded reklam izlenebilir oldu ve ödül verildi
- [ ] Reklam sonrası oyun durumu bozulmadı (puan, skor kaybolmadı)

**Notlar:**
```

```

### 2.7 Ayarlar
- [ ] Ses kapatıldı → oyun sesleri durdu
- [ ] Müzik kapatıldı → lobi/oyun müziği durdu
- [ ] Haptic kapatıldı → titreşim durdu
- [ ] Bildirimler kapatıldı → push bildirimi gelmedi
- [ ] Profil keşif kapatıldı → ayar kaydedildi
- [ ] Uygulama kapatılıp açılınca ayarlar korundu
- [ ] Hesabı sil akışı tamamlandı (onay istedi)

**Notlar:**
```

```

---

## 3. Performans

### 3.1 Hız
- [ ] Uygulama açılışı < 3 saniye (soğuk başlatma)
- [ ] Lobi ekranı < 1 saniyede açıldı
- [ ] Soru ekranı geçişi < 500ms
- [ ] Animasyonlar takılmadan oynadı (60fps hissi)
- [ ] WebSocket bağlantısı stabil kaldı (düşmedi)

### 3.2 Pil ve Isı
- [ ] 15 dakika oyun sonrası cihaz aşırı ısınmadı
- [ ] Pil tüketimi makul göründü

### 3.3 Ağ
- [ ] 4G bağlantıda oyun oynanabildi
- [ ] 3G bağlantıda oyun oynanabildi (yavaş ama stabil)
- [ ] WiFi → 4G geçişinde oyun düşmedi
- [ ] Bağlantı kesilince uygun hata mesajı göründü

**Notlar:**
```

```

---

## 4. Hata İzleme

### 4.1 Crash Kontrolü
- [ ] Sentry'de bu session'a ait crash yok
- [ ] ANR (App Not Responding) olmadı
- [ ] OOM (Out of Memory) olmadı

### 4.2 Gözlemlenen Hatalar

| # | Hata Açıklaması | Adım | Cihaz | Ciddiyet |
|---|-----------------|------|-------|----------|
| 1 | | | | P0/P1/P2 |
| 2 | | | | P0/P1/P2 |
| 3 | | | | P0/P1/P2 |

### 4.3 UI/UX Sorunları

| # | Sorun | Ekran | Görsel (ekran görüntüsü) |
|---|-------|-------|--------------------------|
| 1 | | | |
| 2 | | | |

---

## 5. Geri Bildirim Soruları

Bu bölümü beta testçinin doldurması beklenir:

### 5.1 Genel İzlenim

**Uygulamayı bir arkadaşına nasıl anlatırdın? (2-3 cümle)**
```

```

**İlk oyunun nasıldı? (1-5 puan)**
```
1 - Çok kötü / 2 - Kötü / 3 - İdare eder / 4 - İyi / 5 - Harika
Puanın: 
```

### 5.2 Eğlence Faktörü

**En eğlenceli an neydi?**
```

```

**En can sıkıcı an neydi?**
```

```

**Tekrar oynamak ister misin? (Evet/Hayır/Belki)**
```

```

### 5.3 Eksik Gördüğün Özellikler

**En çok neyi eksik buldun?**
```

```

**Eklemesini istediğin 1 şey ne olurdu?**
```

```

### 5.4 Anlaşılırlık

**Oyunun kurallarını anlamak kolay mıydı?**
```
1 - Çok zor / 2 - Zor / 3 - Orta / 4 - Kolay / 5 - Çok kolay
Puanın: 
```

**Slider final turu sezgisel miydi?**
```
Evet / Hayır — Neden: 
```

### 5.5 Teknik Gözlemler

**Herhangi bir yerde takılma, gecikme fark ettin mi?**
```

```

**Reklam deneyimi nasıldı?**
```
Çok rahatsız edici / Kabul edilebilir / Sorun değil
```

---

## 6. Test Ortamı

**Cihaz:** ___________  
**İşletim Sistemi:** Android ___ / iOS ___  
**RAM:** ___ GB  
**Bağlantı:** WiFi / 4G / 3G  
**Test Tarihi & Saati:** ___________  
**Test Süresi:** ___ dakika  
**Oynanan Oyun Sayısı:** ___  

---

*Beta Checklist v1.0 — QuizRoyale MVP — Hafta 11*
