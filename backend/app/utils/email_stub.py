"""E-posta gönderim stub'ı.

Şimdilik gerçek e-posta göndermez; sadece log'a yazar. İleride buraya
SMTP / SendGrid / Amazon SES gibi gerçek bir sağlayıcı entegre edilecek.
Tüm e-posta çıkışları bu tek noktadan geçsin ki sağlayıcı değişimi kolay olsun.
"""

import logging

logger = logging.getLogger("app.email")


async def send_email(to: str, subject: str, body: str) -> None:
    """Bir e-posta 'gönder' (şimdilik sadece log'a yazar).

    Args:
        to: Alıcı e-posta adresi.
        subject: E-posta konusu.
        body: E-posta gövdesi (düz metin).

    Not: Üretimde burada gerçek bir e-posta sağlayıcısı çağrılacak.
    Şu an hiçbir ağ çağrısı yapılmaz; sadece geliştirme görünürlüğü için loglanır.
    """
    logger.info(
        "[EMAIL STUB] Gönderiliyor -> to=%s | subject=%s\n%s",
        to,
        subject,
        body,
    )
