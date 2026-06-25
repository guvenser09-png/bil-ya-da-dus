# 05 — Ekran Görüntüleri (Screenshots)

App Store Connect > Uygulama > **Distribution > (dil) > App Previews and Screenshots** altında yüklenir.

> ⚠️ Görüntüler **gerçek cihaz veya simülatör** çıktısı olmalı; mockup/uydurma/yanıltıcı arayüz olamaz (Guideline 2.3 — Accurate Metadata). Gösterilen ekranlar uygulamada gerçekten var olmalı.

> ⚠️ Görüntülerde **fiyat/abonelik vurgusu yanıltıcı olmamalı**, başka platformların düğmeleri (Android) görünmemeli, yer tutucu/lorem ipsum olmamalı.

---

## Zorunlu boyutlar (2025+ kuralları)

Apple artık tek bir **en büyük iPhone boyutu** zorunlu kılar ve bunu küçük ekranlara otomatik ölçekler. Yine de net görünüm için ana boyutları yükleyin.

### iPhone (ZORUNLU)
| Slot | Cihaz örneği | Çözünürlük (px, portrait) | Zorunlu? |
|---|---|---|---|
| **6.9"** | iPhone 16 Pro Max / 15 Pro Max | **1320 × 2868** | **Evet (birincil zorunlu)** |
| 6.7" | iPhone 14 Plus / 15 Plus | 1290 × 2796 | Önerilir (6.9" varsa Apple ölçekler) |
| 6.5" (opsiyonel eski) | iPhone 11 Pro Max | 1242 × 2688 | Opsiyonel |

> Pratik öneri: **6.9" (1320×2868)** setini hazırlayın; Apple bunu daha küçük iPhone'lara otomatik kullanır. Mümkünse 6.7"yi de ekleyin.

### iPad (yalnızca uygulama iPad'i destekliyorsa ZORUNLU)
| Slot | Çözünürlük (px, portrait) |
|---|---|
| **13"** (iPad Pro 12.9"/13") | **2064 × 2752** (veya 2048 × 2732) |

> ⚠️ **Karar:** Flutter uygulaması iPad'i destekliyorsa (Runner hedefi "iPhone" yerine "Universal" ise) iPad ekran görüntüsü **zorunludur**. iPad'i desteklemek istemiyorsanız Xcode'da hedefi yalnızca iPhone yapın; o zaman iPad görüntüsü gerekmez. İlk sürümde **yalnızca iPhone** önerilir (daha az iş, daha az ret riski).

---

## Adet

- Slot başına **minimum 1**, **maksimum 10** görüntü.
- **Önerilen: 5–6 görüntü** (mağazada ilk 3'ü en görünür; en güçlüleri başa koyun).

---

## Önerilen 5–6 kare (sıralı)

| # | Ekran | Ne göstermeli | Üzerine yazı (caption) önerisi |
|---|---|---|---|
| 1 | **Ana ekran / Hero** | Oyunun kimliği, "Oyna" butonu, logo | "20 kişilik canlı bilgi savaşı" |
| 2 | **Lobi / Eşleşme** | 20 oyuncunun toplandığı bekleme arenası | "Arenaya 20 oyuncu giriyor" |
| 3 | **Oyun sorusu** | Aktif soru + şıklar + geri sayım | "Doğru bil, hayatta kal!" |
| 4 | **Eleme / Sıralama** | Düşenler + kalanlar canlı sıralama | "Yanlış cevap = eleme" |
| 5 | **Turnuva arenası** | Ranked/turnuva ekranı, ödüller | "Beceri temelli turnuvalar" |
| 6 | **Mağaza / Karakterler** | Altınla alınan karakterler + altın paketleri | "Altın topla, karakterini seç" |

> Üzerine yazı (overlay caption) opsiyoneldir ama dönüşümü artırır. Yazılar Türkçe olmalı (birincil dil tr). EN listesi eklerseniz İngilizce caption'lı ayrı set hazırlayın.

---

## Nasıl üretilir

1. **Simülatör:** Xcode > iPhone 16 Pro Max simülatörü aç → uygulamayı çalıştır → `Cmd+S` ile ekran görüntüsü (otomatik doğru çözünürlükte kaydeder).
   - ⚠️ Backend canlı olmalı ki gerçek lobi/oyun ekranları görünsün (`DEPLOY.md`).
2. **Gerçek cihaz:** iPhone'da yan tuş + ses açma ile screenshot; sonra doğru piksele ölçekleyin (Apple kesin çözünürlük ister).
3. **Caption/çerçeve eklemek:** Figma/Canva ile metin overlay; çıktı tam piksel boyutunda (1320×2868) PNG/JPG olmalı.

> Durum çubuğu temiz görünsün (tam pil, tam sinyal). Simülatörde `xcrun simctl status_bar` ile ayarlanabilir.

---

## App Preview videosu (opsiyonel)
- 15–30 sn, dikey, cihaz çözünürlüğünde. İlk sürüm için zorunlu değil; sonra eklenebilir.

---

## Kontrol listesi
- [ ] 6.9" (1320×2868) seti, 5–6 kare hazır.
- [ ] (Opsiyonel) 6.7" seti.
- [ ] iPad destekleniyorsa 13" seti; desteklenmiyorsa hedef yalnızca iPhone.
- [ ] Tüm kareler gerçek uygulama ekranları (backend canlıyken çekildi).
- [ ] Android/diğer platform öğesi, lorem ipsum, yanıltıcı içerik YOK.
- [ ] App ikonu 1024×1024 PNG (alfa yok, köşe yuvarlatma yok) ayrıca hazır.
