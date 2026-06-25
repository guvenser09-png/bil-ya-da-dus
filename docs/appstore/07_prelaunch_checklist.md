# 07 — Gönderim Öncesi Kontrol Listesi (tek sayfa)

Bil ya da Düş 1.0.0'ı incelemeye göndermeden önce her maddeyi işaretleyin.

---

## 0. KRİTİK ÖN KOŞUL
- [ ] **Üretim backend deploy edildi** (`DEPLOY.md`), `https://<domain>/health` → 200.
- [ ] Soru bankası production DB'ye seed'lendi.
- [ ] `IAP_SANDBOX=false`, `APPLE_SHARED_SECRET`, `APPLE_BUNDLE_ID=com.bilyadadus.app`, `DEBUG=false` ayarlı.

## 1. Hesap & uyum
- [ ] Apple Developer Program aktif.
- [ ] Agreements, Tax & Banking **tamamlandı**.
- [ ] App ID `com.bilyadadus.app` + In-App Purchase capability.

## 2. Binary
- [ ] Bundle ID Xcode = Portal = `com.bilyadadus.app`.
- [ ] Build: `flutter build ipa --release --dart-define=API_BASE_URL=https://<prod> --dart-define=WS_BASE_URL=wss://<prod>` (TLS, doğru domain).
- [ ] Version 1.0.0, Build numarası benzersiz/artan.
- [ ] App Store Connect'e yüklendi, "Processing" bitti.
- [ ] Export Compliance yanıtlandı (özel şifreleme yok → No).
- [ ] TestFlight'ta uçtan uca test edildi (giriş, maç, IAP sandbox) — çökme yok.

## 3. Metadata (01)
- [ ] Name `Bil ya da Düş`, Subtitle, Promo, Description, Keywords.
- [ ] Support URL (çalışıyor), Marketing URL (ops.), Copyright.
- [ ] Birincil: Games > Trivia, İkincil: Games > Word.
- [ ] Sürüm notları (1.0.0).
- [ ] App Review Information: **çalışan test hesabı** + iletişim + review notes + canlı backend URL.

## 4. IAP (03)
- [ ] 4 Consumable altın paketi (id/fiyat/tr lokalizasyon/review screenshot).
- [ ] "Premium" grubu + monthly/yearly (seviyeler, lokalizasyon, yenileme metni, review screenshot).
- [ ] App-Specific Shared Secret → backend.
- [ ] **Tüm IAP'ler 1.0.0 sürümüne dahil edildi**, "Ready to Submit".
- [ ] Paywall'da 5 zorunlu madde (başlık/süre/fiyat/yenileme metni/gizlilik+EULA bağlantısı).

## 5. Gizlilik (04)
- [ ] App Privacy anketi gerçek toplamayla uyumlu; **"Used to Track You" boş** (izleme yok).
- [ ] Privacy Policy URL yayında ve girildi.
- [ ] EULA: Apple standart (boş) veya kendi EULA'nız License Agreement'ta.
- [ ] **Uygulama içinden hesap silme** mevcut (5.1.1(v)).

## 6. Ekran görüntüleri (05)
- [ ] 6.9" (1320×2868) seti, 5–6 kare, gerçek uygulama ekranları (backend canlıyken).
- [ ] iPad destekleniyorsa 13" seti; değilse hedef yalnızca iPhone.
- [ ] App ikonu 1024×1024 (alfa yok, köşe yuvarlatma yok).
- [ ] Android/yanıltıcı/placeholder öğe yok.

## 7. Yaş derecelendirme (02)
- [ ] Anket dolduruldu; şiddet/cinsellik/kumar = Yok.
- [ ] Sohbet/kullanıcı iletişimi durumu doğru beyan edildi (varsa report+block mevcut).

## 8. Son
- [ ] Age Rating, Privacy, Build, IAP, Screenshots, Metadata hepsi yeşil.
- [ ] **Submit to App Review** tıklandı.
- [ ] Yayın modu seçildi (Manual / Automatic release).
