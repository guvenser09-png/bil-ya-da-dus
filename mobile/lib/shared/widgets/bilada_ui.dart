import 'dart:math' as math;
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:quizroyale/core/theme/app_theme.dart';

/// Stitch tasarımının ortak metin stilleri.
class BiladaText {
  BiladaText._();

  static TextStyle displayXl({Color color = AppTheme.cPrimary, double size = 48}) =>
      GoogleFonts.quicksand(fontSize: size, height: 1.08, fontWeight: FontWeight.w700, color: color, letterSpacing: -1);

  static TextStyle headline({Color color = AppTheme.cOnSurface, double size = 28}) =>
      GoogleFonts.quicksand(fontSize: size, height: 1.14, fontWeight: FontWeight.w700, color: color);

  static TextStyle title({Color color = AppTheme.cOnSurface, double size = 20}) =>
      GoogleFonts.quicksand(fontSize: size, height: 1.2, fontWeight: FontWeight.w700, color: color);

  static TextStyle body({Color color = AppTheme.cOnSurface, double size = 16}) =>
      GoogleFonts.quicksand(fontSize: size, height: 1.4, fontWeight: FontWeight.w500, color: color);

  static TextStyle label({Color color = AppTheme.cOnSurfaceVariant, double size = 12}) =>
      GoogleFonts.quicksand(fontSize: size, height: 1.3, fontWeight: FontWeight.w700, color: color, letterSpacing: 0.6);
}

/// Logo başlığı — "Bil ya da Düş" sert pembe drop-shadow ile.
class BiladaLogo extends StatelessWidget {
  const BiladaLogo({super.key, this.fontSize = 28});
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    return Text(
      'Bil ya da Düş',
      style: GoogleFonts.quicksand(
        fontSize: fontSize,
        fontWeight: FontWeight.w700,
        color: AppTheme.cPrimary,
        letterSpacing: -0.5,
        shadows: const [Shadow(color: Color(0xFF640036), offset: Offset(0, 4), blurRadius: 0)],
      ),
    );
  }
}

/// 3D "chunky" buton — basıldığında aşağı iner, sert alt gölgesi kaybolur.
class ChunkyButton extends StatefulWidget {
  const ChunkyButton({
    super.key,
    required this.onPressed,
    required this.child,
    this.color = AppTheme.cPrimaryContainer,
    this.foreground = AppTheme.cOnPrimaryContainer,
    this.shadowColor = AppTheme.cPrimaryShadow,
    this.height = 60,
    this.expand = true,
    this.borderRadius = 20,
    this.depth = 6,
    this.padding = const EdgeInsets.symmetric(horizontal: 24),
  });

  final VoidCallback? onPressed;
  final Widget child;
  final Color color;
  final Color foreground;
  final Color shadowColor;
  final double height;
  final bool expand;
  final double borderRadius;
  final double depth;
  final EdgeInsets padding;

  @override
  State<ChunkyButton> createState() => _ChunkyButtonState();
}

class _ChunkyButtonState extends State<ChunkyButton> {
  bool _pressed = false;

  void _set(bool v) {
    if (widget.onPressed == null) return;
    setState(() => _pressed = v);
  }

  @override
  Widget build(BuildContext context) {
    final disabled = widget.onPressed == null;
    final dy = _pressed ? widget.depth : 0.0;
    return GestureDetector(
      onTapDown: (_) => _set(true),
      onTapUp: (_) => _set(false),
      onTapCancel: () => _set(false),
      onTap: widget.onPressed,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 80),
        curve: Curves.easeOut,
        height: widget.height,
        width: widget.expand ? double.infinity : null,
        transform: Matrix4.translationValues(0, dy, 0),
        padding: widget.padding,
        margin: EdgeInsets.only(bottom: widget.depth),
        decoration: BoxDecoration(
          color: disabled ? AppTheme.cSurfaceContainerHighest : widget.color,
          borderRadius: BorderRadius.circular(widget.borderRadius),
          boxShadow: disabled
              ? null
              : [
                  BoxShadow(
                    color: widget.shadowColor,
                    offset: Offset(0, widget.depth - dy),
                    blurRadius: 0,
                  ),
                ],
        ),
        child: Center(
          child: DefaultTextStyle(
            style: BiladaText.headline(
              color: disabled ? AppTheme.cOutline : widget.foreground,
              size: 20,
            ),
            child: IconTheme(
              data: IconThemeData(color: disabled ? AppTheme.cOutline : widget.foreground),
              child: widget.child,
            ),
          ),
        ),
      ),
    );
  }
}

/// Buzlu cam kart.
class GlassCard extends StatelessWidget {
  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.borderRadius = 20,
    this.onTap,
    this.color,
    this.border = true,
  });

  final Widget child;
  final EdgeInsets padding;
  final double borderRadius;
  final VoidCallback? onTap;
  final Color? color;
  final bool border;

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(borderRadius);
    final content = ClipRRect(
      borderRadius: radius,
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: color ?? AppTheme.cSurfaceContainer.withValues(alpha: 0.6),
            borderRadius: radius,
            border: border ? Border.all(color: Colors.white.withValues(alpha: 0.1)) : null,
          ),
          child: child,
        ),
      ),
    );
    if (onTap == null) return content;
    return GestureDetector(onTap: onTap, child: content);
  }
}

/// Coin sayacı hapı.
class CoinPill extends StatelessWidget {
  const CoinPill({super.key, required this.coins});
  final int coins;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.cSurfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppTheme.cOutlineVariant),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(_fmt(coins), style: BiladaText.label(color: AppTheme.cPrimary, size: 13)),
          const SizedBox(width: 4),
          const Text('🪙', style: TextStyle(fontSize: 14)),
        ],
      ),
    );
  }

  static String _fmt(int n) {
    final s = n.toString();
    final buf = StringBuffer();
    for (int i = 0; i < s.length; i++) {
      if (i > 0 && (s.length - i) % 3 == 0) buf.write(',');
      buf.write(s[i]);
    }
    return buf.toString();
  }
}

/// Üst uygulama çubuğu (avatar + logo + coin).
class BiladaTopBar extends StatelessWidget implements PreferredSizeWidget {
  const BiladaTopBar({
    super.key,
    this.username = '',
    this.avatarSeed,
    this.coins = 0,
    this.onAvatarTap,
    this.showLogo = true,
    this.compactLogo = false,
  });

  final String username;
  final int? avatarSeed;
  final int coins;
  final VoidCallback? onAvatarTap;
  final bool showLogo;
  final bool compactLogo;

  @override
  Size get preferredSize => const Size.fromHeight(64);

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64 + MediaQuery.of(context).padding.top,
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top,
        left: 20,
        right: 20,
      ),
      decoration: BoxDecoration(
        color: AppTheme.cSurfaceContainer.withValues(alpha: 0.85),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.3), blurRadius: 16)],
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: onAvatarTap,
            child: Row(
              children: [
                BiladaAvatar(seed: avatarSeed ?? 0, name: username, size: 40, ringColor: AppTheme.cPrimary),
                if (username.isNotEmpty) ...[
                  const SizedBox(width: 8),
                  Text(username, style: BiladaText.label(color: AppTheme.cOnSurface, size: 12)),
                ],
              ],
            ),
          ),
          const Spacer(),
          if (showLogo) BiladaLogo(fontSize: compactLogo ? 20 : 24),
          const Spacer(),
          CoinPill(coins: coins),
        ],
      ),
    );
  }
}

/// Yuvarlak avatar — seed'e göre renk + baş harf (görsel yoksa).
class BiladaAvatar extends StatelessWidget {
  const BiladaAvatar({
    super.key,
    required this.seed,
    this.name = '',
    this.size = 48,
    this.ringColor = AppTheme.cPrimaryContainer,
    this.ringWidth = 2,
  });

  final int seed;
  final String name;
  final double size;
  final Color ringColor;
  final double ringWidth;

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.avatarColors[seed.abs() % AppTheme.avatarColors.length];
    final initial = name.isNotEmpty ? name.characters.first.toUpperCase() : '?';
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: ringColor, width: ringWidth),
        gradient: LinearGradient(
          colors: [color, Color.lerp(color, Colors.black, 0.35)!],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      alignment: Alignment.center,
      child: Text(
        initial,
        style: GoogleFonts.quicksand(
          fontSize: size * 0.42,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
    );
  }
}

/// Alt navigasyon — Ana Sayfa / Sıralama / Mağaza / Profil.
class BiladaBottomNav extends StatelessWidget {
  const BiladaBottomNav({super.key, required this.currentIndex, required this.onTap});
  final int currentIndex;
  final ValueChanged<int> onTap;

  static const _items = [
    (Icons.home_rounded, 'Ana Sayfa'),
    (Icons.leaderboard_rounded, 'Sıralama'),
    (Icons.shopping_bag_rounded, 'Mağaza'),
    (Icons.person_rounded, 'Profil'),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(top: 8, left: 16, right: 16, bottom: 8 + MediaQuery.of(context).padding.bottom),
      decoration: BoxDecoration(
        color: AppTheme.cSurfaceContainerHigh.withValues(alpha: 0.92),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.5), blurRadius: 20, offset: const Offset(0, -4))],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          for (int i = 0; i < _items.length; i++) _navItem(i),
        ],
      ),
    );
  }

  Widget _navItem(int i) {
    final active = i == currentIndex;
    final (icon, label) = _items[i];
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => onTap(i),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: EdgeInsets.symmetric(horizontal: active ? 16 : 8, vertical: 6),
        decoration: active
            ? BoxDecoration(
                color: AppTheme.cPrimaryContainer,
                borderRadius: BorderRadius.circular(16),
                boxShadow: const [BoxShadow(color: AppTheme.cPrimaryShadow, offset: Offset(0, 4), blurRadius: 0)],
              )
            : null,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: active ? AppTheme.cOnPrimaryContainer : AppTheme.cOnSurfaceVariant, size: 26),
            const SizedBox(height: 2),
            Text(
              label,
              style: BiladaText.label(
                color: active ? AppTheme.cOnPrimaryContainer : AppTheme.cOnSurfaceVariant,
                size: 11,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Animasyonlu candy arka plan — gradyan + süzülen blurlu lekeler.
class BiladaBackground extends StatefulWidget {
  const BiladaBackground({super.key, this.gradient, this.showFloaters = true});
  final Gradient? gradient;
  final bool showFloaters;

  @override
  State<BiladaBackground> createState() => _BiladaBackgroundState();
}

class _BiladaBackgroundState extends State<BiladaBackground> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(seconds: 8))..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Stack(
        children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(gradient: widget.gradient ?? AppTheme.backgroundGradient),
            ),
          ),
          if (widget.showFloaters)
            AnimatedBuilder(
              animation: _c,
              builder: (context, _) {
                final t = _c.value;
                return Stack(
                  children: [
                    _blob(left: 24, top: 120 + t * 20, color: AppTheme.cPrimaryContainer, size: 120),
                    _blob(right: 16, top: 320 - t * 24, color: AppTheme.cTertiary, size: 100),
                    _blob(left: 40, bottom: 160 + t * 16, color: AppTheme.cSecondaryContainer, size: 90),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }

  Widget _blob({double? left, double? right, double? top, double? bottom, required Color color, required double size}) {
    return Positioned(
      left: left,
      right: right,
      top: top,
      bottom: bottom,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: color.withValues(alpha: 0.12),
          boxShadow: [BoxShadow(color: color.withValues(alpha: 0.18), blurRadius: 60, spreadRadius: 20)],
        ),
      ),
    );
  }
}

/// Dairesel geri sayım halkası.
class CountdownRing extends StatelessWidget {
  const CountdownRing({
    super.key,
    required this.progress,
    required this.label,
    this.size = 128,
    this.color = AppTheme.cTertiary,
    this.trackColor = AppTheme.cSurfaceContainerHighest,
    this.stroke = 10,
    this.sublabel,
  });

  final double progress; // 0..1 kalan
  final String label;
  final double size;
  final Color color;
  final Color trackColor;
  final double stroke;
  final String? sublabel;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _RingPainter(progress.clamp(0, 1), color, trackColor, stroke),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(label, style: BiladaText.displayXl(color: color, size: size * 0.4)),
              if (sublabel != null)
                Text(sublabel!.toUpperCase(), style: BiladaText.label(color: color, size: 11)),
            ],
          ),
        ),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter(this.progress, this.color, this.trackColor, this.stroke);
  final double progress;
  final Color color;
  final Color trackColor;
  final double stroke;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = (size.width - stroke) / 2;
    final track = Paint()
      ..color = trackColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke;
    final arc = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(center, radius, track);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      2 * math.pi * progress,
      false,
      arc,
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.progress != progress || old.color != color;
}

/// Bölüm başlığı etiketi.
class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key, this.trailing});
  final String text;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(text, style: BiladaText.headline(size: 24)),
        if (trailing != null) trailing!,
      ],
    );
  }
}

/// Küçük rozet/etiket hapı.
class PillBadge extends StatelessWidget {
  const PillBadge(this.text, {super.key, this.color = AppTheme.cTertiary, this.fg = AppTheme.cOnTertiary});
  final String text;
  final Color color;
  final Color fg;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(999)),
      child: Text(text.toUpperCase(), style: BiladaText.label(color: fg, size: 11)),
    );
  }
}
