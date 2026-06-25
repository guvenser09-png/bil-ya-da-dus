import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// "Bil ya da Düş" tasarım sistemi.
/// Google Stitch tasarımından üretilen candy-glass / chunky tema.
/// Renk isimleri Material 3 "Bil ya da Düş" paletini takip eder.
/// (Eski [primary], [background] gibi adlar geriye dönük uyumluluk için korunur.)
class AppTheme {
  AppTheme._();

  // ── Stitch paleti (kaynak renkler) ──────────────────────────────
  static const Color cPrimary = Color(0xFFFFB0CB); // açık pembe (logo/metin)
  static const Color cPrimaryContainer = Color(0xFFFF479C); // hot pink (buton)
  static const Color cOnPrimary = Color(0xFF640036);
  static const Color cOnPrimaryContainer = Color(0xFF58002F);
  static const Color cPrimaryShadow = Color(0xFF58002F); // 3D buton gölgesi

  static const Color cSecondary = Color(0xFFD2BBFF); // lavanta metin
  static const Color cSecondaryContainer = Color(0xFF6800E4); // mor
  static const Color cOnSecondaryContainer = Color(0xFFD2BBFF);
  static const Color cSecondaryShadow = Color(0xFF25005A);

  static const Color cTertiary = Color(0xFF1DDFBE); // mint
  static const Color cTertiaryContainer = Color(0xFF00A38A);
  static const Color cOnTertiary = Color(0xFF00382E);
  static const Color cOnTertiaryContainer = Color(0xFF003027);
  static const Color cTertiaryShadow = Color(0xFF005143);

  static const Color cError = Color(0xFFFFB4AB);
  static const Color cErrorContainer = Color(0xFF93000A);
  static const Color cOnErrorContainer = Color(0xFFFFDAD6);
  static const Color cErrorShadow = Color(0xFF64000A);

  static const Color gold = Color(0xFFFFD23F);

  // Surface katmanları
  static const Color cSurface = Color(0xFF1D0F14);
  static const Color cSurfaceContainerLowest = Color(0xFF180A0F);
  static const Color cSurfaceContainerLow = Color(0xFF26171C);
  static const Color cSurfaceContainer = Color(0xFF2B1B20);
  static const Color cSurfaceContainerHigh = Color(0xFF36252B);
  static const Color cSurfaceContainerHighest = Color(0xFF413035);
  static const Color cSurfaceVariant = Color(0xFF413035);

  static const Color cOnSurface = Color(0xFFF7DCE3);
  static const Color cOnSurfaceVariant = Color(0xFFE1BDC7);
  static const Color cOutline = Color(0xFFA88892);
  static const Color cOutlineVariant = Color(0xFF594048);

  // ── Geriye dönük uyumlu adlar (eski ekranlar bunları kullanıyor) ──
  static const Color primary = cPrimaryContainer; // ana aksiyon (hot pink)
  static const Color primaryDark = cPrimaryShadow;
  static const Color secondary = cSecondary;
  static const Color accent = gold;
  static const Color accentOrange = Color(0xFFFF6B35);
  static const Color success = cTertiary;
  static const Color danger = cError;

  static const Color background = cSurface;
  static const Color surface = cSurfaceContainer;
  static const Color card = cSurfaceContainer;
  static const Color cardLight = cSurfaceContainerHighest;

  static const Color textPrimary = cOnSurface;
  static const Color textSecondary = cOnSurfaceVariant;
  static const Color textHint = cOutline;

  // ── Gradyanlar ──────────────────────────────────────────────────
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [cPrimaryContainer, cSecondaryContainer],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient goldGradient = LinearGradient(
    colors: [gold, Color(0xFFFFA500)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient mintGradient = LinearGradient(
    colors: [cTertiary, cTertiaryContainer],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient backgroundGradient = LinearGradient(
    colors: [cSurface, cSurfaceContainerLow, Color(0xFF2A0A2E)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  /// Çekirdek "epik" arka plan (final / kazanan ekranları).
  static const RadialGradient epicGradient = RadialGradient(
    colors: [Color(0xFF640036), cSurface],
    center: Alignment.topCenter,
    radius: 1.2,
  );

  // ── Avatar renkleri ─────────────────────────────────────────────
  static const List<Color> avatarColors = [
    cPrimaryContainer, cTertiary, cSecondaryContainer, cError,
    gold, Color(0xFFFF6B35), Color(0xFF8B5CF6), Color(0xFF06B6D4),
    Color(0xFFF59E0B), Color(0xFFEC4899), Color(0xFF10B981), Color(0xFF3B82F6),
    Color(0xFF6366F1), Color(0xFF14B8A6), Color(0xFFD97706), Color(0xFF9333EA),
    Color(0xFF0EA5E9), Color(0xFF16A34A), Color(0xFFDC2626), Color(0xFFCA8A04),
    Color(0xFF7C3AED), Color(0xFF0284C7), Color(0xFF059669), Color(0xFFB91C1C),
    Color(0xFF92400E), Color(0xFF5B21B6), Color(0xFF0369A1), Color(0xFF047857),
    Color(0xFF991B1B), Color(0xFF78350F),
  ];

  // ── Tema ────────────────────────────────────────────────────────
  static ThemeData get dark {
    final base = ThemeData(brightness: Brightness.dark, useMaterial3: true);
    final textTheme = GoogleFonts.quicksandTextTheme(base.textTheme)
        .apply(bodyColor: cOnSurface, displayColor: cOnSurface);

    return base.copyWith(
      scaffoldBackgroundColor: cSurface,
      textTheme: textTheme,
      colorScheme: const ColorScheme.dark(
        primary: cPrimaryContainer,
        onPrimary: cOnPrimaryContainer,
        primaryContainer: cPrimaryContainer,
        onPrimaryContainer: cOnPrimaryContainer,
        secondary: cSecondaryContainer,
        onSecondary: Colors.white,
        secondaryContainer: cSecondaryContainer,
        onSecondaryContainer: cOnSecondaryContainer,
        tertiary: cTertiary,
        onTertiary: cOnTertiary,
        tertiaryContainer: cTertiaryContainer,
        onTertiaryContainer: cOnTertiaryContainer,
        error: cError,
        onError: Color(0xFF690005),
        errorContainer: cErrorContainer,
        onErrorContainer: cOnErrorContainer,
        surface: cSurfaceContainer,
        onSurface: cOnSurface,
        onSurfaceVariant: cOnSurfaceVariant,
        outline: cOutline,
        outlineVariant: cOutlineVariant,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: cSurface,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: GoogleFonts.quicksand(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: cPrimary,
        ),
        iconTheme: const IconThemeData(color: cOnSurface),
      ),
      cardTheme: CardThemeData(
        color: cSurfaceContainer,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        margin: EdgeInsets.zero,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: cPrimaryContainer,
          foregroundColor: cOnPrimaryContainer,
          minimumSize: const Size(double.infinity, 56),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          textStyle: GoogleFonts.quicksand(fontSize: 18, fontWeight: FontWeight.w700),
          elevation: 0,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: cSecondary,
          side: const BorderSide(color: cSecondary, width: 2),
          minimumSize: const Size(double.infinity, 56),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          textStyle: GoogleFonts.quicksand(fontSize: 16, fontWeight: FontWeight.w700),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: cSecondary,
          textStyle: GoogleFonts.quicksand(fontSize: 14, fontWeight: FontWeight.w600),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: cSurfaceContainerHigh,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: cPrimaryContainer, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: cError, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
        hintStyle: const TextStyle(color: cOutline),
        labelStyle: const TextStyle(color: cOnSurfaceVariant),
      ),
      tabBarTheme: TabBarThemeData(
        labelColor: cOnPrimary,
        unselectedLabelColor: cOnSurfaceVariant,
        indicator: BoxDecoration(
          color: cPrimary,
          borderRadius: BorderRadius.circular(12),
        ),
        labelStyle: GoogleFonts.quicksand(fontWeight: FontWeight.w700, fontSize: 12),
        unselectedLabelStyle: GoogleFonts.quicksand(fontWeight: FontWeight.w700, fontSize: 12),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: cSurfaceContainerHigh,
        contentTextStyle: GoogleFonts.quicksand(color: cOnSurface, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        behavior: SnackBarBehavior.floating,
      ),
      dividerTheme: const DividerThemeData(color: cOutlineVariant, thickness: 1),
    );
  }
}

/// Gradyan metin yardımcısı (eski ekranlar kullanıyor).
class GradientText extends StatelessWidget {
  const GradientText(this.text, {super.key, required this.gradient, this.style});

  final String text;
  final Gradient gradient;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    return ShaderMask(
      blendMode: BlendMode.srcIn,
      shaderCallback: (bounds) =>
          gradient.createShader(Rect.fromLTWH(0, 0, bounds.width, bounds.height)),
      child: Text(text, style: style),
    );
  }
}

/// Eski gradyan buton (geriye dönük uyumluluk). Yeni kod [ChunkyButton] kullanmalı.
class GradientButton extends StatelessWidget {
  const GradientButton({
    super.key,
    required this.onPressed,
    required this.child,
    this.gradient = AppTheme.primaryGradient,
    this.height = 56,
    this.borderRadius = 20,
    this.isLoading = false,
  });

  final VoidCallback? onPressed;
  final Widget child;
  final Gradient gradient;
  final double height;
  final double borderRadius;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: isLoading ? null : onPressed,
      child: Container(
        height: height,
        decoration: BoxDecoration(
          gradient: onPressed == null ? null : gradient,
          color: onPressed == null ? AppTheme.cardLight : null,
          borderRadius: BorderRadius.circular(borderRadius),
          boxShadow: onPressed == null
              ? null
              : [BoxShadow(color: AppTheme.primary.withValues(alpha: 0.4), blurRadius: 12, offset: const Offset(0, 4))],
        ),
        child: Center(
          child: isLoading
              ? const SizedBox(
                  width: 22, height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white),
                )
              : child,
        ),
      ),
    );
  }
}
