"""İndirme açılış sayfası (reklam hedefi + profil linki).

NEDEN VAR: Meta (Instagram/Facebook) reklamlarında DOĞRUDAN App Store linki
hedef gösterilemiyor — "web sitesine git" hedefli reklam reddediliyor, yalnızca
"profili ziyaret et" onaylanıyordu (o da kullanıcıyı mağazaya götürmediği için
indirme getirmiyor). Kendi alan adımızdaki normal bir web sayfası ise sorunsuz
kabul edilir. Bu sayfa reklamın hedefi olur, kullanıcı buradan mağazaya gider.

BONUS — ATRİBÜSYON: ?src=ig gibi bir etiketle gelen ziyaret ve mağaza tıklaması
Redis'te günlük sayılır (landing:view/click:<gün>:<kaynak>). Böylece "Instagram
reklamı kaç tıklama getirdi" sorusu tahmine değil sayıya dayanır.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from fastapi import Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.redis_client import get_redis

router = APIRouter()

APP_STORE_URL = "https://apps.apple.com/tr/app/id6784295523"
# Play yayına girince burası doldurulacak (kapalı test sürecinde boş).
PLAY_STORE_URL = ""

_ICON_B64 = "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"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _platform(request: Request) -> str:
    """Ziyaretçinin cihazı (ios/android/other) — user-agent'tan kabaca.

    NEDEN: Reklam cihaz ayrımı yapmadığında gelen trafiğin büyük kısmı Android
    olabiliyor; sayfada yalnızca App Store butonu olduğu için o kullanıcılar
    dönüşmeden çıkıyor. Bu sayaç "bütçenin ne kadarı indiremeyecek kişilere
    gidiyor" sorusunu ölçülebilir kılar.
    """
    ua = (request.headers.get("user-agent") or "").lower()
    if "android" in ua:
        return "android"
    if "iphone" in ua or "ipad" in ua or "ipod" in ua:
        return "ios"
    return "other"


async def _count(kind: str, src: str) -> None:
    """Ziyaret/tıklama sayacı (best-effort; Redis yoksa sayfa yine çalışır)."""
    try:
        redis = await get_redis()
        key = f"landing:{kind}:{_today()}:{(src or 'direct')[:24]}"
        await redis.incr(key)
        await redis.expire(key, 90 * 24 * 3600)
    except Exception:
        pass


@router.get("/indir", response_class=HTMLResponse, include_in_schema=False)
@router.get("/download", response_class=HTMLResponse, include_in_schema=False)
async def landing(request: Request, src: str = Query(default="direct")) -> HTMLResponse:
    """Reklam/bio hedefi: markalı indirme sayfası.

    Otomatik yönlendirme YAPMAZ — reklam incelemelerinde "gösterilen sayfa ile
    gidilen yer farklı" şüphesi doğurmasın diye kullanıcı butona basar.
    """
    await _count("view", src)
    plat = _platform(request)
    await _count(f"view_{plat}", src)
    play_block = (
        f'<a class="btn btn-ghost" href="/indir/go?store=play&src={src}">Google Play</a>'
        if PLAY_STORE_URL
        else '<div class="soon">Android sürümü çok yakında 🤖</div>'
    )
    html = f"""<!doctype html>
<html lang="tr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Bil ya da Düş — Canlı bilgi yarışması</title>
<meta name="description" content="12 kişi, 5 soru, tek şampiyon. Yanlış bilen kapaktan düşer! Ücretsiz indir.">
<meta property="og:title" content="Bil ya da Düş">
<meta property="og:description" content="12 kişi, 5 soru, tek şampiyon. Yanlış bilen kapaktan düşer!">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display',Segoe UI,Roboto,Helvetica,Arial,sans-serif;
 background:radial-gradient(120% 80% at 50% 0%,#1c2450 0%,#0e1230 55%,#090b20 100%);
 color:#fff;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:28px 20px}}
.wrap{{width:100%;max-width:460px;text-align:center}}
.icon{{width:104px;height:104px;border-radius:26px;box-shadow:0 18px 50px rgba(255,150,20,.35);margin:0 auto 22px;display:block}}
h1{{font-size:34px;font-weight:900;letter-spacing:-.5px;line-height:1.15}}
h1 span{{color:#ffc107}}
.tag{{margin:12px 0 26px;font-size:17px;font-weight:700;line-height:1.5;color:rgba(255,255,255,.8)}}
.tag b{{color:#ff5252}}
.feats{{margin:30px 0 0;display:flex;flex-direction:column;gap:10px;text-align:left}}
.feat{{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.12);border-radius:16px;
 padding:14px 16px;font-size:15px;font-weight:600;color:rgba(255,255,255,.9)}}
.btn{{display:block;padding:18px 20px;border-radius:18px;font-size:19px;font-weight:900;text-decoration:none;
 margin-bottom:12px;transition:transform .12s}}
.btn:active{{transform:scale(.97)}}
.btn-main{{background:linear-gradient(135deg,#ffd54f,#ff8f00);color:#12132b;box-shadow:0 14px 36px rgba(255,150,20,.4)}}
.btn-ghost{{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.18);color:#fff}}
.soon{{padding:15px;border-radius:16px;background:rgba(255,255,255,.05);
 border:1px dashed rgba(255,255,255,.2);color:rgba(255,255,255,.6);font-size:14px;font-weight:600}}
.free{{margin-top:14px;font-size:13px;color:rgba(255,255,255,.45)}}
</style></head>
<body><div class="wrap">
 <img class="icon" alt="Bil ya da Düş" src="data:image/png;base64,{_ICON_B64}">
 <h1>BİL YA DA <span>DÜŞ</span></h1>
 <div class="tag">12 kişi · 5 soru · tek şampiyon<br>Yanlış bilen <b>KAPAKTAN DÜŞER</b> 🔥</div>
 <a class="btn btn-main" id="ios" href="{APP_STORE_URL}"
    onclick="try{{navigator.sendBeacon('/indir/track?store=ios&src={src}')}}catch(e){{}}">App Store'dan Ücretsiz İndir</a>
 {play_block}
 <div class="free">Ücretsiz • Misafir olarak anında oyna</div>
 <div class="feats">
  <div class="feat">🎮 Gerçek rakiplerle CANLI yarış</div>
  <div class="feat">⚡ 90 saniyede bir maç — beklemek yok</div>
  <div class="feat">🏆 Zor Mod'da ödül havuzu: 1.'ye 700 altın</div>
  <div class="feat">🧠 Genel kültür, tarih, bilim, müzik, sinema</div>
 </div>
</div>
<script>
// GERÇEK ziyaretçi ölçümü: sayfa görünür durumda 1.5 sn kalırsa say.
// Instagram reklam ön-yüklemesi (prefetch) sayfayı arka planda çeker; bu koşul
// onu saymaz → "kaç kişi GERÇEKTEN geldi" sorusunun dürüst cevabı.
(function(){{
  var sent=false;
  function ping(){{
    if(sent||document.visibilityState!=='visible')return;
    sent=true;
    try{{navigator.sendBeacon('/indir/track?kind=real_view&src={src}')}}catch(e){{}}
  }}
  setTimeout(ping,1500);
  document.addEventListener('visibilitychange',function(){{setTimeout(ping,1500)}});
}})();
</script>
</body></html>"""
    return HTMLResponse(content=html)


@router.get("/indir/go", include_in_schema=False)
async def landing_go(
    store: str = Query(default="ios"), src: str = Query(default="direct")
) -> RedirectResponse:
    """Mağazaya yönlendir + tıklamayı say (atribüsyonun ölçüldüğü yer)."""
    await _count(f"click_{'play' if store == 'play' else 'ios'}", src)
    target = PLAY_STORE_URL if (store == "play" and PLAY_STORE_URL) else APP_STORE_URL
    return RedirectResponse(url=target, status_code=302)


@router.get("/indir/track", include_in_schema=False)
@router.post("/indir/track", include_in_schema=False)
async def landing_track(
    store: str = Query(default="ios"),
    src: str = Query(default="direct"),
    kind: str = Query(default=""),
) -> Response:
    """Mağaza butonuna basıldığını say (yönlendirme YOK, 204 döner).

    NEDEN: Buton artık doğrudan apps.apple.com'a gidiyor — Instagram/Facebook
    IN-APP TARAYICISI kendi alan adımızdaki 302 zincirini bazen engelliyor ve
    kullanıcı mağazaya hiç ulaşamıyordu (137 ziyaret / 0 tıklama tablosu).
    Sayım artık sendBeacon ile ayrı yapılır, kullanıcının yolunu kesmez.
    """
    if kind == "real_view":
        await _count("real_view", src)
    else:
        await _count(f"click_{'play' if store == 'play' else 'ios'}", src)
    return Response(status_code=204)


# --- Reklam için ANINDA yönlendirme ------------------------------------------
# /indir markalı bir sayfa gösterir (bio linki için iyi). Reklamda ise araya
# sayfa girmesi dönüşümü öldürüyordu (65 iOS ziyaret → 1 tıklama). Bu uç,
# kullanıcıyı hiç oyalamadan mağazaya atar — diğer oyun reklamlarındaki davranış.
#
# NEDEN 302 DEĞİL DE JS/meta-refresh: Instagram/Facebook IN-APP tarayıcısı kendi
# alan adımızdan apps.apple.com'a giden sunucu yönlendirmesini engelleyebiliyor.
# Tarayıcı içinde çalışan window.location.replace + <meta refresh> ikilisi bu
# ortamlarda güvenilir; üstüne görünür bir yedek buton bırakılır ki hiçbir
# senaryoda kullanıcı boş ekranda kalmasın.
_REDIRECT_HTML = """<!doctype html><html lang="tr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bil ya da Düş</title>
<meta http-equiv="refresh" content="0;url={target}">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
 background:radial-gradient(120% 80% at 50% 0%,#1c2450 0%,#0e1230 55%,#090b20 100%);
 color:#fff;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}}
.box{{text-align:center}}
.sp{{width:44px;height:44px;margin:0 auto 20px;border:4px solid rgba(255,193,7,.25);
 border-top-color:#ffc107;border-radius:50%;animation:r .8s linear infinite}}
@keyframes r{{to{{transform:rotate(360deg)}}}}
h1{{font-size:22px;font-weight:900;letter-spacing:.3px}} h1 span{{color:#ffc107}}
p{{margin-top:10px;font-size:15px;color:rgba(255,255,255,.6)}}
a{{display:inline-block;margin-top:22px;padding:14px 26px;border-radius:14px;
 background:linear-gradient(135deg,#ffd54f,#ff8f00);color:#12132b;font-weight:900;
 font-size:16px;text-decoration:none}}
</style></head><body><div class="box">
<div class="sp"></div>
<h1>BİL YA DA <span>DÜŞ</span></h1>
<p>App Store'a yönlendiriliyorsun…</p>
<a href="{target}">Açılmadıysa buraya bas</a>
</div>
<script>location.replace("{target}");</script>
</body></html>"""


@router.get("/app", response_class=HTMLResponse, include_in_schema=False)
async def app_redirect(
    request: Request, src: str = Query(default="direct")
) -> HTMLResponse:
    """Reklam hedefi: kullanıcıyı ANINDA mağazaya gönderir.

    Android ziyaretçi (Play sürümü henüz yokken) mağazada bulamayacağı için
    markalı /indir sayfasına düşer — orada "Android çok yakında" mesajı var.
    """
    plat = _platform(request)
    await _count("view", src)
    await _count(f"view_{plat}", src)

    if plat == "android" and not PLAY_STORE_URL:
        return HTMLResponse(
            content=f'<meta http-equiv="refresh" content="0;url=/indir?src={src}">',
            status_code=200,
        )

    target = PLAY_STORE_URL if (plat == "android" and PLAY_STORE_URL) else APP_STORE_URL
    await _count(f"click_{'play' if (plat == 'android' and PLAY_STORE_URL) else 'ios'}", src)
    return HTMLResponse(content=_REDIRECT_HTML.format(target=target))
