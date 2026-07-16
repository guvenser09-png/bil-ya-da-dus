import 'package:flutter/material.dart';

/// Parlak ALTIN para ikonu — 🪙 emojisinin yerine kullanılır.
///
/// Emoji iOS'ta gümüş/soluk göründüğü için para birimi her yerde bu vektörel
/// ikonla gösterilir: radyal altın gradyan (açık sarı → amber → koyu amber),
/// ince koyu-altın kenarlık, çift jant görünümü veren iç halka, sol üstte
/// parlaklık beneği ve hafif alt gölge.
///
/// Satır içinde metinle hizalı durur (Row içinde Text yanında); `size`
/// mevcut fontSize ile orantılı verilmelidir (genelde fontSize ±2).
class GoldCoin extends StatelessWidget {
  const GoldCoin({super.key, this.size = 16});

  /// Paranın çapı (mantıksal px).
  final double size;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size.square(size),
      painter: const _GoldCoinPainter(),
    );
  }
}

class _GoldCoinPainter extends CustomPainter {
  const _GoldCoinPainter();

  // Renk paleti — merkezden kenara ısınan altın tonları.
  static const _light = Color(0xFFFFE082); // merkez: açık sarı
  static const _mid = Color(0xFFFFC107); // gövde: amber
  static const _dark = Color(0xFFFF8F00); // kenar: koyu amber/turuncu
  static const _rim = Color(0xFFB26A00); // kenarlık/jant: koyu altın

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = size.width / 2;
    final coinR = r * 0.92; // alt gölgeye yer bırak

    // Hafif alt gölge — parayı zeminden ayırır.
    canvas.drawCircle(
      c.translate(0, r * 0.09),
      coinR,
      Paint()..color = const Color(0x2E000000),
    );

    // Gövde — sol üstten aydınlanan radyal altın gradyanı.
    canvas.drawCircle(
      c,
      coinR,
      Paint()
        ..shader = const RadialGradient(
          center: Alignment(-0.35, -0.4),
          radius: 1.15,
          colors: [_light, _mid, _dark],
          stops: [0.0, 0.55, 1.0],
        ).createShader(Rect.fromCircle(center: c, radius: coinR)),
    );

    // Dış kenarlık — ince koyu-altın çember.
    final rimW = (size.width * 0.07).clamp(0.7, 2.4);
    canvas.drawCircle(
      c,
      coinR - rimW / 2,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = rimW
        ..color = _rim,
    );

    // İç halka — çift jant görünümü (basılmış madeni para hissi).
    canvas.drawCircle(
      c,
      coinR * 0.62,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = rimW * 0.8
        ..color = _rim.withValues(alpha: 0.55),
    );

    // Parlaklık beneği — sol üstte yumuşak highlight.
    final hl = Offset(c.dx - coinR * 0.38, c.dy - coinR * 0.44);
    canvas.drawOval(
      Rect.fromCenter(center: hl, width: coinR * 0.58, height: coinR * 0.36),
      Paint()
        ..shader = RadialGradient(
          colors: [
            Colors.white.withValues(alpha: 0.85),
            Colors.white.withValues(alpha: 0.0),
          ],
        ).createShader(Rect.fromCircle(center: hl, radius: coinR * 0.36)),
    );
  }

  @override
  bool shouldRepaint(covariant _GoldCoinPainter oldDelegate) => false;
}
