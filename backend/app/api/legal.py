"""Herkese açık (auth'suz) yasal sayfalar — Gizlilik Politikası ve Kullanım Şartları (EULA).

App Store Connect, uygulama gönderimi için herkese açık bir "Privacy Policy URL"
zorunlu kılar; abonelik (Guideline 3.1.2) için de bir EULA/Kullanım Şartları
bağlantısı gerekir. Bu router, deploy edildiğinde:

    GET /legal/privacy  → Gizlilik Politikası (text/html)
    GET /legal/terms    → Kullanım Şartları / EULA (text/html)

uçlarını AUTH GEREKTİRMEDEN sunar. Mobil uygulamadaki yasal linkler de bu
URL'lere işaret edebilir. Harici bağımlılık yoktur; tek sayfa, mobil-dostu,
inline CSS'li HTML döndürülür.

İçerik kaynağı: mobile/assets/legal/{privacy_policy,terms_of_service}.md
taslakları + docs/appstore/04_privacy.md ile tutarlıdır.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

# Destek / iletişim e-postası. Tek yerden değiştirilebilsin diye sabit.
SUPPORT_EMAIL = "guvenser09@gmail.com"
LAST_UPDATED = "2026"

# Ortak, mobil-dostu inline CSS. Harici font/asset yok.
_BASE_CSS = """
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
      Helvetica, Arial, sans-serif;
    line-height: 1.6;
    color: #1a1a1a;
    background: #ffffff;
    -webkit-text-size-adjust: 100%;
  }
  .wrap { max-width: 760px; margin: 0 auto; padding: 24px 18px 64px; }
  h1 { font-size: 1.6rem; line-height: 1.25; margin: 0 0 4px; }
  h2 { font-size: 1.15rem; margin: 28px 0 8px; }
  p, li { font-size: 1rem; }
  ul { padding-left: 1.2rem; }
  li { margin: 4px 0; }
  a { color: #2563eb; word-break: break-word; }
  .meta { color: #666; font-size: .9rem; margin: 0 0 20px; }
  .intro { margin-top: 16px; }
  footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e5e5;
    color: #666; font-size: .85rem; }
  @media (prefers-color-scheme: dark) {
    body { color: #e8e8e8; background: #0f0f10; }
    .meta, footer { color: #9a9a9a; }
    a { color: #6ea8ff; }
    footer { border-top-color: #2a2a2c; }
  }
"""


def _page(title: str, body_html: str) -> str:
    """Tam bir HTML sayfası üretir (ortak <head> + gövde)."""
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="all">
  <title>{title} — Bil ya da Düş</title>
  <style>{_BASE_CSS}</style>
</head>
<body>
  <div class="wrap">
    {body_html}
    <footer>
      Bil ya da Düş · İletişim:
      <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>
    </footer>
  </div>
</body>
</html>"""


_PRIVACY_BODY = f"""
    <h1>Gizlilik Politikası</h1>
    <p class="meta">Yürürlük Tarihi: {LAST_UPDATED} · Son Güncelleme: {LAST_UPDATED}</p>

    <p class="intro">Bu Gizlilik Politikası, “Bil ya da Düş” mobil uygulamasını
    (“Uygulama”) kullandığınızda kişisel verilerinizin nasıl toplandığını,
    kullanıldığını ve korunduğunu açıklar. Uygulamayı kullanarak bu politikayı
    kabul etmiş olursunuz.</p>

    <h2>1. Veri Sorumlusu ve İletişim</h2>
    <p>Uygulama, geliştirici tarafından işletilmektedir. Veri sorumlusu sıfatıyla
    kişisel verilerinizi 6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) ve
    geçerli olduğu hallerde Avrupa Genel Veri Koruma Tüzüğü (GDPR) kapsamında
    işliyoruz. Sorularınız için:
    <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.</p>

    <h2>2. Topladığımız Veriler</h2>
    <ul>
      <li><strong>Hesap bilgileri:</strong> E-posta adresi ve/veya telefon
      numarası, kullanıcı adı, görünen ad ve sistemce atanan kullanıcı kimliği
      (ID).</li>
      <li><strong>Oyun verileri:</strong> Oyun istatistikleri, skorlar, liderlik
      tablosu sıralaması, oynanan maçlar ve eşleşme geçmişi.</li>
      <li><strong>Cihaz kimliği (misafir girişi):</strong> "Misafir olarak
      oyna" seçeneğinde, hesabınızı cihazınıza bağlamak için uygulamanın
      ürettiği rastgele bir cihaz kimliği saklanır. Bu kimlik reklam veya
      izleme amacıyla kullanılmaz.</li>
      <li><strong>Satın alma kayıtları:</strong> Uygulamanın güncel sürümünde
      <strong>uygulama içi satın alım yoktur</strong>; uygulama tamamen
      ücretsizdir. İleride uygulama içi satın alım sunulursa yalnızca işlem
      doğrulama kayıtları tutulur. <strong>Kredi kartı / ödeme aracı
      bilgilerinizi hiçbir durumda biz saklamayız</strong>; olası ödemeler
      Apple App Store veya Google Play üzerinden işlenir.</li>
      <li><strong>Bildirim (push) token'ı:</strong> Bildirimlere izin verirseniz,
      cihazınıza bildirim ulaştırabilmek için Firebase Cloud Messaging (Google)
      tarafından üretilen bir bildirim token'ı saklanır. Yalnızca oyun bildirimi
      göndermek için kullanılır; reklam veya izleme amacıyla kullanılmaz
      (bkz. Bölüm 5).</li>
    </ul>

    <h2>3. Reklamlar ve İzleme</h2>
    <p>Uygulamada <strong>ödüllü (isteğe bağlı) reklamlar</strong> gösterilir:
    yalnızca siz "reklam izle" seçeneğine dokunursanız çalışır ve karşılığında
    oyun içi altın/kalkan kazanırsınız. Reklamlar <strong>Google AdMob</strong>
    ile sunulur ve <strong>kişiselleştirilmez (non-personalized)</strong>; reklam
    sunumu için sınırlı cihaz bilgisi işlenebilir. Sizi diğer şirketlerin uygulama
    ve web sitelerinde <strong>izlemeyiz (no cross-app tracking)</strong>, reklam
    tanımlayıcısını (IDFA) izleme amacıyla kullanmayız ve bu nedenle izleme izni
    istemeyiz. Verilerinizi pazarlama amacıyla üçüncü taraflara
    <strong>satmayız</strong>. Bildirim token'ı reklam/izleme amacıyla
    kullanılmaz.</p>

    <h2>4. Verileri Kullanım Amaçlarımız</h2>
    <ul>
      <li>Hesabınızı oluşturmak, oturum açmanızı sağlamak ve kimliğinizi
      doğrulamak.</li>
      <li>Oyun deneyimini sunmak: eşleştirme yapmak, skor ve liderlik
      tablolarını yönetmek.</li>
      <li>Size oyunla ilgili bildirimler göndermek (bkz. Bölüm 5).</li>
      <li>(Sunulması halinde) uygulama içi satın alımları işlemek ve
      doğrulamak.</li>
      <li>Hizmetin güvenliğini sağlamak, kötüye kullanımı ve hileyi önlemek.</li>
      <li>Yasal yükümlülüklerimizi yerine getirmek.</li>
    </ul>

    <h2>5. Anlık Bildirimler (Push)</h2>
    <p>Uygulama, <strong>izniniz olduğu takdirde</strong> cihazınıza anlık
    bildirim gönderir. Bildirim izni işletim sistemi tarafından sorulur ve
    <strong>tamamen isteğe bağlıdır</strong>; izin vermezseniz uygulamanın tüm
    özellikleri normal şekilde çalışır.</p>
    <ul>
      <li><strong>Ne saklarız:</strong> Yalnızca bildirim token'ı, cihaz
      platformu (iOS/Android) ve son güncelleme zamanı.</li>
      <li><strong>Ne için:</strong> Yalnızca oyunla ilgili bildirimler — günlük
      ödül serisi hatırlatması, günün sorusu duyurusu, tekrar oyuna davet.</li>
      <li><strong>Ne için DEĞİL:</strong> Reklam, profilleme veya sizi başka
      uygulama/sitelerde izleme amacıyla <strong>kullanılmaz</strong>; üçüncü
      taraflara <strong>satılmaz</strong>.</li>
      <li><strong>Sınırlar:</strong> Gece bildirim göndermeyiz (23:00–10:00
      sessiz saat) ve kişi başına günde en fazla bir bildirim göndeririz.</li>
      <li><strong>Kapatma:</strong> Cihazınızın Ayarlar → Bildirimler → Bil ya da
      Düş bölümünden istediğiniz zaman kapatabilirsiniz. Hesabınızı sildiğinizde
      bildirim token'ınız da silinir.</li>
    </ul>

    <h2>6. Üçüncü Taraflar ve Veri Paylaşımı</h2>
    <p>Verileriniz yalnızca hizmetin sunulması için gerekli ölçüde paylaşılır
    (ör. sunucu barındırma sağlayıcısı). Uygulama içi satın alım sunulması
    halinde, satın alımların işlenmesi ve doğrulanması amacıyla <strong>Apple
    App Store</strong> ve <strong>Google Play</strong> ile paylaşılabilir. Anlık
    bildirimlerin cihazınıza ulaştırılması için bildirim token'ı ve bildirim
    içeriği <strong>Google (Firebase Cloud Messaging)</strong> ve
    <strong>Apple (APNs)</strong> üzerinden iletilir. Bunun dışında verilerinizi
    reklam veya pazarlama amacıyla üçüncü taraflarla paylaşmayız.</p>

    <h2>7. Veri Saklama, Silme ve Hesabınızı Silme</h2>
    <p>Kişisel verilerinizi, hesabınız aktif olduğu sürece veya yasal
    yükümlülükler gerektirdiği ölçüde saklarız.</p>
    <ul>
      <li><strong>Uygulama içinden hesap silme:</strong> Hesabınızı ve ilişkili
      kişisel verilerinizi doğrudan uygulama içinden (Hesap Ayarları) silebilirsiniz.
      Hesap silindiğinde kişisel verileriniz — <strong>bildirim token'ınız
      dâhil</strong> — yasal saklama yükümlülükleri saklı kalmak kaydıyla, makul
      bir süre içinde silinir veya anonim hale getirilir.</li>
      <li>Bazı işlem kayıtları (ör. satın alma faturaları) yasal nedenlerle daha
      uzun süre saklanabilir.</li>
    </ul>

    <h2>8. KVKK / GDPR Kapsamındaki Haklarınız</h2>
    <ul>
      <li>Verilerinize <strong>erişim</strong> ve işlenip işlenmediğini öğrenme,</li>
      <li>Eksik veya yanlış verilerin <strong>düzeltilmesini</strong> isteme,</li>
      <li>Verilerinizin <strong>silinmesini</strong> talep etme,</li>
      <li>İşlemeye <strong>itiraz</strong> etme ve kısıtlama,</li>
      <li>Veri taşınabilirliği talep etme ve açık rızayı geri çekme.</li>
    </ul>
    <p>Bu haklarınızı kullanmak için
    <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a> adresine başvurabilirsiniz.</p>

    <h2>9. Çocukların Gizliliği</h2>
    <p>Uygulama 13 yaşın altındaki çocuklara yönelik değildir ve bilerek bu
    yaştaki çocuklardan veri toplamayız.</p>

    <h2>10. Veri Güvenliği</h2>
    <p>Verilerinizi yetkisiz erişime karşı korumak için makul teknik ve idari
    önlemler (ör. şifreli iletişim, erişim kontrolü) alıyoruz. Ancak internet
    üzerinden hiçbir iletim yönteminin %100 güvenli olmadığını hatırlatırız.</p>

    <h2>11. Bu Politikadaki Değişiklikler</h2>
    <p>Bu Gizlilik Politikasını zaman zaman güncelleyebiliriz. Güncel sürüm her
    zaman bu sayfada yayınlanır.</p>
"""


_TERMS_BODY = f"""
    <h1>Kullanım Şartları (EULA)</h1>
    <p class="meta">Yürürlük Tarihi: {LAST_UPDATED} · Son Güncelleme: {LAST_UPDATED}</p>

    <p class="intro">Bu Kullanım Şartları (“Şartlar”), “Bil ya da Düş” mobil
    uygulamasının (“Uygulama”) kullanımınızı düzenleyen son kullanıcı lisans
    sözleşmesidir (EULA). Uygulamayı kullanarak bu Şartları kabul etmiş olursunuz.
    Kabul etmiyorsanız Uygulamayı kullanmayınız.</p>

    <h2>1. Hizmetin Tanımı</h2>
    <p>Uygulama; gerçek zamanlı, çok oyunculu bir bilgi yarışması (trivia)
    deneyimidir. Maçlara katılabilir, skorlarınızı ve liderlik tablosundaki
    sıralamanızı görebilirsiniz. Uygulamanın güncel sürümü tamamen ücretsizdir.</p>

    <h2>2. Hesap Kuralları</h2>
    <ul>
      <li>Hesap oluştururken verdiğiniz bilgilerin doğru ve güncel olması gerekir.</li>
      <li>Hesabınızın ve şifrenizin güvenliğinden siz sorumlusunuz.</li>
      <li>Her kişi yalnızca kendi adına hesap açabilir; hesabınızı devredemezsiniz.</li>
      <li>13 yaşından küçük kişiler Uygulamayı kullanamaz.</li>
    </ul>

    <h2>3. Uygun Olmayan Davranışlar</h2>
    <p>Uygulamayı kullanırken aşağıdakileri yapmamayı kabul edersiniz:</p>
    <ul>
      <li>Hile yapmak, bot/otomatik araç kullanmak veya oyun bütünlüğünü bozmak,</li>
      <li>Diğer kullanıcılara taciz, hakaret, tehdit veya saldırgan davranışta
      bulunmak,</li>
      <li>Yasa dışı, müstehcen veya başkalarının haklarını ihlal eden içerik
      paylaşmak,</li>
      <li>Uygulamanın güvenliğini, sunucularını veya altyapısını tehlikeye
      atmaya çalışmak,</li>
      <li>Başka bir kullanıcının hesabına izinsiz erişmek.</li>
    </ul>
    <p>Bu kurallara aykırı davranış, hesabınızın askıya alınması veya
    kapatılmasıyla sonuçlanabilir.</p>

    <h2>4. Uygulama İçi Satın Almalar, Abonelik ve Otomatik Yenileme</h2>
    <ul>
      <li>Uygulamanın güncel sürümü <strong>tamamen ücretsizdir</strong> ve
      gerçek parayla uygulama içi satın alım içermez. Uygulama ileride sanal
      para (altın) paketleri ve <strong>Premium abonelik</strong> gibi uygulama
      içi satın alımlar sunabilir; aşağıdaki koşullar bu durumda geçerli olur.
      Tüm satın alımlar Apple App Store veya Google Play üzerinden işlenir ve
      ilgili mağazanın kurallarına tabidir.</li>
      <li><strong>Otomatik yenileme:</strong> Sunulması halinde Premium
      abonelik, geçerli dönem sonunda otomatik olarak yenilenir. Mevcut dönem
      bitmeden en az 24 saat önce iptal etmediğiniz sürece ücret bir sonraki
      dönem için tahsil edilir.</li>
      <li><strong>İptal:</strong> Aboneliğinizi istediğiniz zaman cihazınızdaki
      App Store veya Google Play hesap ayarlarından yönetebilir ve iptal
      edebilirsiniz. İptal, mevcut faturalandırma döneminin sonunda yürürlüğe girer.</li>
      <li>Sanal para ve eşyaların gerçek bir para değeri yoktur; gerçek paraya
      çevrilemez, Uygulama dışında devredilemez veya satılamaz. Size yalnızca
      Uygulama içinde kullanım için sınırlı, kişisel ve devredilemez bir lisans
      verilir.</li>
      <li>Geri ödemeler, satın alımın yapıldığı mağazanın (Apple/Google) iade
      politikalarına tabidir.</li>
    </ul>

    <h2>5. Fikri Mülkiyet</h2>
    <p>Uygulama; tasarımı, logosu, metinleri, soruları, grafikleri, ses öğeleri ve
    yazılımı dâhil tüm içerikleriyle bize veya lisans verenlerimize aittir. Önceden
    yazılı izin almadan bu içerikleri kopyalayamaz, dağıtamaz veya türev eser
    oluşturamazsınız.</p>

    <h2>6. Sorumluluk Reddi</h2>
    <ul>
      <li>Uygulama “olduğu gibi” ve “mevcut haliyle” sunulur; kesintisiz, hatasız
      veya güvenli çalışacağına dair açık ya da zımni garanti vermeyiz.</li>
      <li>Yürürlükteki yasaların izin verdiği azami ölçüde, Uygulamanın
      kullanımından doğan dolaylı, arızi veya sonuç niteliğindeki zararlardan
      sorumlu değiliz.</li>
    </ul>

    <h2>7. Fesih</h2>
    <p>Bu Şartları ihlal etmeniz hâlinde hesabınızı askıya alma veya sonlandırma
    hakkımız saklıdır. Hesabınızı dilediğiniz zaman uygulama içinden silebilirsiniz.</p>

    <h2>8. Yürürlük, Değişiklikler ve Geçerli Hukuk</h2>
    <p>Bu Şartlar Türkiye Cumhuriyeti hukukuna tabidir. Şartları zaman zaman
    güncelleyebiliriz; değişiklikten sonra Uygulamayı kullanmaya devam etmeniz
    güncel Şartları kabul ettiğiniz anlamına gelir. Güncel sürüm her zaman bu
    sayfada yayınlanır.</p>

    <h2>9. İletişim</h2>
    <p>Sorularınız için: <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
"""


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy() -> HTMLResponse:
    """Herkese açık Gizlilik Politikası (auth gerektirmez)."""
    return HTMLResponse(content=_page("Gizlilik Politikası", _PRIVACY_BODY))


@router.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms_of_service() -> HTMLResponse:
    """Herkese açık Kullanım Şartları / EULA (auth gerektirmez)."""
    return HTMLResponse(content=_page("Kullanım Şartları", _TERMS_BODY))
