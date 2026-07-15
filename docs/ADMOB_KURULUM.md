# 📺 AdMob Kurulumu — Bilal'e Anlatır Gibi

Amaç: Gerçek ödüllü reklamların çalışması için AdMob'dan **2 kimlik** almak:
1. **AdMob App ID** (`ca-app-pub-XXXX~YYYY`)
2. **Ödüllü Reklam Birimi ID'si** (`ca-app-pub-XXXX/ZZZZ`)

Bu ikisini bana verince koda gömerim (test kimliklerinin yerine), gerçek reklamlar başlar.

---

## Adım 1 — AdMob'a giriş
- **admob.google.com** → Google hesabınla giriş yap.
- İlk kez giriyorsan: ülke (Türkiye), saat dilimi, şartları kabul et. (Arka planda bir AdSense/ödeme hesabı açılır — para almak için sonra ödeme bilgisi girilecek, ama reklamlar bundan önce de çalışır.)

## Adım 2 — Uygulamayı ekle
- Sol menü **Apps → Add app** (Uygulama ekle).
- Platform: **iOS**.
- "Is your app listed on the App Store?" → **Yes** → arama kutusuna **Bil ya da Düş** yaz ve seç (App Store'da yayında olduğu için bulunur).
  - Bulamazsa: **No** seçip elle ekle (uygulama adı: Bil ya da Düş, bundle: `com.bilyadadus.app`), sonra mağaza yayınına bağlarsın.
- Ekleyince sana bir **App ID** verir: `ca-app-pub-................~............` → **bunu not al** (bana vereceğin 1. değer).

## Adım 3 — Ödüllü reklam birimi oluştur
- Az önce eklediğin uygulamaya gir → **Ad units → Add ad unit** (Reklam birimi ekle).
- Tür: **Rewarded** (Ödüllü) seç.
- İsim: `BilYaDaDus Ödüllü` (ne yazsan olur).
- **Create** → sana bir **Ad unit ID** verir: `ca-app-pub-................/............` → **bunu not al** (bana vereceğin 2. değer).

## Adım 4 — Bana ver, gerisini ben yaparım
Şu iki satırı bana yolla:
```
App ID:        ca-app-pub-....~....
Ödüllü birim:  ca-app-pub-..../....
```
Ben bunları Info.plist ve ad_service.dart'a koyarım (test kimliklerinin yerine), yeni build alırız → gerçek reklamlar çalışır.

---

## Adım 5 — Ödeme (parayı almak için, acele yok)
- AdMob → **Payments** → ödeme profili (ad/adres, vergi bilgisi, banka/IBAN).
- Reklamlar bunu beklemeden çalışır; para **eşiği geçince** (~100$) hesabına yatar. İlk günlerde gelir küçük olacağından bunu sonra da halledebilirsin.

---

## ⚠️ Önemli uyarılar
- **Kendi reklamına TIKLAMA / kendini izletme** (gerçek reklamlarda). Google bunu "geçersiz trafik" sayar, hesabı kapatabilir. Test için zaten test reklamları var (kod öyle ayarlı).
- **Yeni uygulama onayı:** AdMob yeni uygulamayı incelerken birkaç gün "sınırlı reklam" gösterebilir; sonra tam açılır. Bu normal, test reklamları hep çalışır.
- **App Store beyanı:** Reklam eklediğimiz için "reklamsız" diyemiyoruz; gizlilik anketini "reklam gösterimi" içerecek şekilde güncelliyorum (kişiselleştirilmemiş/izlemesiz reklam seçeceğiz — IDFA/izleme izni istemeden, en temiz yol).

Takıldığın adımda ekran görüntüsü at, tam yeri gösteririm.
