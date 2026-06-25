import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/characters.dart';

class PlayerAvatar extends StatelessWidget {
  const PlayerAvatar({
    super.key,
    required this.avatarId,
    required this.username,
    this.size = 48,
    this.isEliminated = false,
    this.isWinner = false,
    this.onTap,
    this.frame,
  });

  final String avatarId;
  final String username;
  final double size;
  final bool isEliminated;
  final bool isWinner;
  final VoidCallback? onTap;

  /// Kuşanılmış kozmetik çerçeve anahtarı (`gold` | `neon` | `fire` | `ice` |
  /// `royal`). null ise çerçeve çizilmez (geriye dönük uyumlu).
  final String? frame;

  Color _colorForId(String id) {
    final digits = id.replaceAll(RegExp(r'\D'), '');
    if (digits.isNotEmpty) {
      final index = int.parse(digits);
      return AppTheme.avatarColors[index % AppTheme.avatarColors.length];
    }
    int hash = 0;
    for (final c in username.codeUnits) {
      hash = (hash * 31 + c) & 0x7FFFFFFF;
    }
    return AppTheme.avatarColors[hash % AppTheme.avatarColors.length];
  }

  String _initials(String name) {
    final parts = name.trim().split(RegExp(r'[._\s]'));
    if (parts.length >= 2 && parts[0].isNotEmpty && parts[1].isNotEmpty) {
      return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    }
    if (name.isEmpty) return '?';
    return name.substring(0, name.length >= 2 ? 2 : 1).toUpperCase();
  }

  /// Gradient + baş harf fallback (görsel yüklenemez ya da katalog dışı id).
  Widget _buildFallback() {
    final color = _colorForId(avatarId);
    final initials = _initials(username);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: isEliminated
            ? null
            : LinearGradient(
                colors: [color, Color.lerp(color, Colors.black, 0.35)!],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
        color: isEliminated ? Colors.grey.shade700 : null,
        shape: BoxShape.circle,
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Text(
            initials,
            style: GoogleFonts.quicksand(
              fontSize: size * 0.38,
              fontWeight: FontWeight.w700,
              color: isEliminated ? Colors.grey.shade500 : Colors.white,
            ),
          ),
          if (isEliminated) Text('💀', style: TextStyle(fontSize: size * 0.35)),
        ],
      ),
    );
  }

  /// Katalog karakteri için 3D PNG (dairesel, candy arka plan + placeholder).
  Widget _buildCharacter(String url) {
    final color = _colorForId(avatarId);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        // Hafif candy parıltısı arka plan; görsel şeffaf PNG olduğu için
        // arkadan nazik bir gradyan görünür.
        gradient: LinearGradient(
          colors: [
            color.withValues(alpha: 0.30),
            Color.lerp(color, Colors.black, 0.35)!.withValues(alpha: 0.30),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: ClipOval(
        child: CachedNetworkImage(
          imageUrl: url,
          fit: BoxFit.cover,
          width: size,
          height: size,
          placeholder: (_, __) => Center(
            child: SizedBox(
              width: size * 0.3,
              height: size * 0.3,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: Colors.white.withValues(alpha: 0.8),
              ),
            ),
          ),
          errorWidget: (_, __, ___) => _buildFallback(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final url = imageUrlFor(avatarId);
    Widget inner = url != null ? _buildCharacter(url) : _buildFallback();

    // Elenmiş oyuncuyu grileştir.
    if (isEliminated && url != null) {
      inner = ColorFiltered(
        colorFilter: const ColorFilter.matrix(<double>[
          0.2126, 0.7152, 0.0722, 0, 0,
          0.2126, 0.7152, 0.0722, 0, 0,
          0.2126, 0.7152, 0.0722, 0, 0,
          0, 0, 0, 1, 0,
        ]),
        child: Opacity(opacity: 0.6, child: inner),
      );
    }

    // Kazanan için altın çerçeve + parıltı.
    Widget avatar = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: isWinner ? Border.all(color: AppTheme.gold, width: size * 0.06) : null,
        boxShadow: isWinner
            ? [BoxShadow(color: AppTheme.gold.withValues(alpha: 0.5), blurRadius: 12, spreadRadius: 2)]
            : null,
      ),
      child: ClipOval(child: inner),
    );

    if (isWinner) avatar = _WinnerGlow(child: avatar);

    // Kuşanılmış kozmetik çerçeve (kazanan altın çerçevesinden bağımsız;
    // elenmişse gösterme). frame null ise hiçbir şey çizilmez.
    final spec = _frameSpec(frame);
    if (spec != null && !isEliminated && !isWinner) {
      avatar = _FrameRing(size: size, spec: spec, child: avatar);
    }

    if (onTap != null) return GestureDetector(onTap: onTap, child: avatar);
    return avatar;
  }
}

/// Çerçeve görsel tanımı (renkler + parıltı). [PlayerAvatar.frame] anahtarına
/// göre seçilir. Bilinmeyen anahtar → null (çerçeve çizilmez).
class _FrameSpec {
  const _FrameSpec(this.colors, {this.glow = true});

  /// Halka gradyanını oluşturan renkler.
  final List<Color> colors;

  /// Dışa doğru hafif parıltı.
  final bool glow;
}

_FrameSpec? _frameSpec(String? key) {
  switch (key) {
    case 'gold':
      return const _FrameSpec([Color(0xFFFFE082), AppTheme.gold, Color(0xFFFFA500)]);
    case 'neon':
      return const _FrameSpec([Color(0xFF1DDFBE), Color(0xFF00E5FF), Color(0xFF6800E4)]);
    case 'fire':
      return const _FrameSpec([Color(0xFFFFD23F), Color(0xFFFF6B35), Color(0xFFDC2626)]);
    case 'ice':
      return const _FrameSpec([Color(0xFFE0F7FF), Color(0xFF7DD3FC), Color(0xFF3B82F6)], glow: false);
    case 'royal':
      return const _FrameSpec([Color(0xFFD2BBFF), Color(0xFF8B5CF6), Color(0xFF6800E4)]);
    // Eksklüzif turnuva ödülleri (sadece sezon şampiyonlarında / finalistlerinde).
    case 'champion':
      return const _FrameSpec([Color(0xFFFFFBEA), Color(0xFFFFD23F), Color(0xFFE0A000)]);
    case 'legend':
      return const _FrameSpec([Color(0xFFFFE082), Color(0xFFFF6B35), Color(0xFF8B5CF6)]);
    default:
      return null;
  }
}

/// Avatarın etrafına gradyanlı bir halka (+ opsiyonel parıltı) çizer.
/// Halka kalınlığı avatar boyutuna orantılı; içte avatar olduğu gibi durur.
class _FrameRing extends StatelessWidget {
  const _FrameRing({required this.size, required this.spec, required this.child});

  final double size;
  final _FrameSpec spec;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final ringWidth = (size * 0.07).clamp(2.0, 6.0);
    return Container(
      width: size,
      height: size,
      padding: EdgeInsets.all(ringWidth),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: SweepGradient(colors: [...spec.colors, spec.colors.first]),
        boxShadow: spec.glow
            ? [BoxShadow(color: spec.colors[1].withValues(alpha: 0.5), blurRadius: size * 0.18, spreadRadius: 1)]
            : null,
      ),
      child: ClipOval(child: child),
    );
  }
}

class _WinnerGlow extends StatefulWidget {
  const _WinnerGlow({required this.child});
  final Widget child;

  @override
  State<_WinnerGlow> createState() => _WinnerGlowState();
}

class _WinnerGlowState extends State<_WinnerGlow> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat(reverse: true);
  late final Animation<double> _glow =
      Tween<double>(begin: 4, end: 14).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _glow,
      builder: (_, child) => Container(
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          boxShadow: [BoxShadow(color: AppTheme.gold.withValues(alpha: 0.6), blurRadius: _glow.value, spreadRadius: 2)],
        ),
        child: child,
      ),
      child: widget.child,
    );
  }
}
