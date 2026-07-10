import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:quizroyale/core/theme/app_theme.dart';

/// 🎆 Tam ekran havai fişek animasyonu — YALNIZCA kazananın sonuç ekranında.
///
/// CustomPainter tabanlı hafif parçacık sistemi:
///  - 6 ardışık patlama, rastgele konum/renk (tema paleti: pembe/mint/altın/mor)
///  - kıvılcımlar yerçekimiyle düşerek söner
///  - ~4.5 sn sürer ve BİTER (loop yok) → performans dostu
///  - tek AnimationController, dispose temiz; dokunuşları engellemez.
class FireworksOverlay extends StatefulWidget {
  const FireworksOverlay({super.key});

  @override
  State<FireworksOverlay> createState() => _FireworksOverlayState();
}

class _FireworksOverlayState extends State<FireworksOverlay>
    with SingleTickerProviderStateMixin {
  static const _duration = Duration(milliseconds: 4500);

  late final AnimationController _controller =
      AnimationController(vsync: this, duration: _duration)..forward();

  // Patlamalar bir kez, sabit tohumla üretilir (build başına yeniden üretim yok).
  late final List<_Burst> _bursts = _makeBursts();

  static List<_Burst> _makeBursts() {
    final rnd = math.Random();
    const palette = [
      AppTheme.cPrimaryContainer, // hot pink
      AppTheme.cPrimary, // açık pembe
      AppTheme.cTertiary, // mint
      AppTheme.gold, // altın
      AppTheme.cSecondary, // lavanta
      AppTheme.cSecondaryContainer, // mor
    ];
    final bursts = <_Burst>[];
    const count = 6; // 5-7 arası; 6 patlama ~4.5 sn'ye rahat yayılır
    for (var i = 0; i < count; i++) {
      // Patlamalar zamana yayılır: her biri toplamın ~%30'u kadar yaşar.
      final start = i / count * 0.68 + rnd.nextDouble() * 0.05;
      final sparks = <_Spark>[];
      final sparkCount = 26 + rnd.nextInt(10);
      final color = palette[rnd.nextInt(palette.length)];
      for (var s = 0; s < sparkCount; s++) {
        final angle = (s / sparkCount) * 2 * math.pi + rnd.nextDouble() * 0.2;
        sparks.add(_Spark(
          angle: angle,
          speed: 0.55 + rnd.nextDouble() * 0.55,
          size: 1.6 + rnd.nextDouble() * 1.8,
        ));
      }
      bursts.add(_Burst(
        // Konum: ekranın üst 2/3'ünde rastgele (butonların üstü).
        center: Offset(0.12 + rnd.nextDouble() * 0.76,
            0.10 + rnd.nextDouble() * 0.45),
        start: start,
        life: 0.32, // her patlamanın ömrü (toplam sürenin oranı)
        color: color,
        radius: 0.30 + rnd.nextDouble() * 0.16,
        sparks: sparks,
      ));
    }
    return bursts;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (_, __) {
          // Animasyon bitti → hiçbir şey çizme (ağaçta kalsa da maliyetsiz).
          if (_controller.isCompleted) return const SizedBox.shrink();
          return CustomPaint(
            size: Size.infinite,
            painter: _FireworksPainter(t: _controller.value, bursts: _bursts),
          );
        },
      ),
    );
  }
}

/// Tek bir havai fişek patlaması (merkez + kıvılcım listesi).
class _Burst {
  const _Burst({
    required this.center,
    required this.start,
    required this.life,
    required this.color,
    required this.radius,
    required this.sparks,
  });

  /// Ekran oranı cinsinden merkez (0..1).
  final Offset center;

  /// Toplam animasyon içinde başlangıç anı (0..1).
  final double start;

  /// Patlamanın ömrü (toplam sürenin oranı).
  final double life;

  final Color color;

  /// Maks. saçılma yarıçapı (kısa kenar oranı).
  final double radius;

  final List<_Spark> sparks;
}

/// Tek kıvılcım: açı + hız + boyut (deterministik, önceden üretilir).
class _Spark {
  const _Spark({required this.angle, required this.speed, required this.size});
  final double angle;
  final double speed;
  final double size;
}

class _FireworksPainter extends CustomPainter {
  _FireworksPainter({required this.t, required this.bursts});

  final double t;
  final List<_Burst> bursts;

  @override
  void paint(Canvas canvas, Size size) {
    final short = math.min(size.width, size.height);
    final paint = Paint()..style = PaintingStyle.fill;

    for (final b in bursts) {
      // Bu patlamanın yerel zamanı (0..1); henüz başlamadı/bitti → atla.
      final lt = (t - b.start) / b.life;
      if (lt <= 0 || lt >= 1) continue;

      // Saçılma: hızlı başlar, sürtünmeyle yavaşlar (easeOut).
      final spread = Curves.easeOutCubic.transform(lt);
      // Sönme: ömrün son yarısında kıvılcımlar kaybolur.
      final fade = lt < 0.5 ? 1.0 : (1 - (lt - 0.5) / 0.5);
      // Yerçekimi: zamanla artan aşağı kayma.
      final gravity = 0.22 * short * lt * lt;

      final cx = b.center.dx * size.width;
      final cy = b.center.dy * size.height;
      final maxR = b.radius * short;

      for (final s in b.sparks) {
        final r = maxR * s.speed * spread;
        final x = cx + math.cos(s.angle) * r;
        final y = cy + math.sin(s.angle) * r + gravity;
        paint.color = b.color.withValues(alpha: 0.9 * fade);
        canvas.drawCircle(Offset(x, y), s.size * (1 - 0.4 * lt), paint);
        // Küçük "kuyruk" — kıvılcımın geldiği yöne doğru soluk iz.
        paint.color = b.color.withValues(alpha: 0.35 * fade);
        final tx = cx + math.cos(s.angle) * r * 0.86;
        final ty = cy + math.sin(s.angle) * r * 0.86 + gravity * 0.9;
        canvas.drawCircle(Offset(tx, ty), s.size * 0.6, paint);
      }

      // Patlama merkezinde kısa süreli parlak çekirdek.
      if (lt < 0.25) {
        paint.color = Colors.white.withValues(alpha: (1 - lt / 0.25) * 0.8);
        canvas.drawCircle(Offset(cx, cy), 5 * (1 - lt / 0.25), paint);
      }
    }
  }

  @override
  bool shouldRepaint(_FireworksPainter oldDelegate) => oldDelegate.t != t;
}
