import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/cosmetics/providers/cosmetics_provider.dart';
import 'package:quizroyale/features/leaderboard/providers/leaderboard_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';
import 'package:quizroyale/shared/widgets/profile_bottom_sheet.dart';

class LeaderboardScreen extends ConsumerStatefulWidget {
  const LeaderboardScreen({super.key});

  static const _tabs = [
    (LeaderboardTab.daily, 'GÜNLÜK'),
    (LeaderboardTab.weekly, 'HAFTALIK'),
    (LeaderboardTab.season, 'SEZON'),
    (LeaderboardTab.allTime, 'TÜM ZAMANLAR'),
    (LeaderboardTab.friends, 'ARKADAŞLAR'),
  ];

  @override
  ConsumerState<LeaderboardScreen> createState() => _LeaderboardScreenState();
}

class _LeaderboardScreenState extends ConsumerState<LeaderboardScreen> {
  @override
  void initState() {
    super.initState();
    // Ekran her açıldığında aktif sekmeyi tazele (maç sonrası bayat veriyi önler).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final tab = ref.read(leaderboardProvider).tab;
      ref.read(leaderboardProvider.notifier).load(tab);
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(leaderboardProvider);
    final user = ref.watch(authProvider).user;
    final username = (user?['username'] ?? '').toString();
    final coins = (user?['coins'] as num?)?.toInt() ?? 0;

    return Stack(
      children: [
        const Positioned.fill(child: BiladaBackground(showFloaters: false)),
        Column(
          children: [
            BiladaTopBar(coins: coins, username: username, avatarSeed: username.hashCode),
            // Segment sekmeler
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
              child: GlassCard(
                padding: const EdgeInsets.all(6),
                borderRadius: 18,
                child: SizedBox(
                  height: 36,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    children: [
                      for (final t in LeaderboardScreen._tabs)
                        GestureDetector(
                          onTap: () => ref.read(leaderboardProvider.notifier).load(t.$1),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 180),
                            alignment: Alignment.center,
                            margin: const EdgeInsets.symmetric(horizontal: 2),
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            decoration: BoxDecoration(
                              color: t.$1 == state.tab ? AppTheme.cPrimary : Colors.transparent,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(t.$2,
                                style: BiladaText.label(
                                    color: t.$1 == state.tab ? AppTheme.cOnPrimary : AppTheme.cOnSurfaceVariant)),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
            if (state.tab == LeaderboardTab.season)
              _SeasonStrip(secondsLeft: state.seasonSecondsLeft),
            Expanded(
              child: state.isLoading
                  ? const Center(child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer))
                  : state.error != null
                      ? _ErrorView(onRetry: () => ref.read(leaderboardProvider.notifier).load(state.tab))
                      : _list(context, state.entries, state.tab),
            ),
            if (state.myEntry != null) _MyRankBar(entry: state.myEntry!),
          ],
        ),
      ],
    );
  }

  Widget _list(BuildContext context, List<Map<String, dynamic>> entries, LeaderboardTab tab) {
    if (entries.isEmpty) return const _EmptyView();
    final me = (ref.read(authProvider).user?['username'] ?? '').toString().toLowerCase();
    // İsim rengini katalog color_hex'i ile çözmek için kozmetik state'i izle.
    final cos = ref.watch(cosmeticsProvider);
    final isSeason = tab == LeaderboardTab.season;
    // Tek akışlı liste: ilk 3 ince madalya vurgusu alır, 4+ sade satır.
    // İlk 10 üstte görünür; kaydırınca 50'ye kadar gider.
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 120),
      itemCount: entries.length,
      itemBuilder: (context, i) {
        final e = entries[i];
        return _RegularEntry(
          entry: e,
          rank: (e['rank'] as int?) ?? i + 1,
          isSeason: isSeason,
          isMe: (e['username'] as String? ?? '').toLowerCase() == me,
          cos: cos,
        );
      },
    );
  }
}

// ── Sıra madalyonu: metalik (top-3) veya sade tonlu (4+) ────────────────────
({List<Color> colors, Color fg, bool metallic}) _rankMetal(int rank) {
  switch (rank) {
    case 1:
      return (colors: const [Color(0xFFFFEFB0), Color(0xFFFFD23F), Color(0xFFE08A00)], fg: const Color(0xFF5A3B00), metallic: true);
    case 2:
      return (colors: const [Color(0xFFF6F8FB), Color(0xFFC8CFD7), Color(0xFF98A2AD)], fg: const Color(0xFF373D45), metallic: true);
    case 3:
      return (colors: const [Color(0xFFF3CBA0), Color(0xFFCD7F32), Color(0xFF8A4E20)], fg: const Color(0xFF44260C), metallic: true);
    default:
      return (colors: const [AppTheme.cSurfaceContainerHigh, AppTheme.cSurfaceContainerHigh], fg: AppTheme.cOnSurfaceVariant, metallic: false);
  }
}

// ── Kuşanılmış kozmetikler (frame + name_color + effect) ────────────────────
// Backend leaderboard girişleri ws/game oyuncu objesiyle birebir aynı anahtarları
// taşır: `frame` (örn frame_gold), `name_color` (örn name_rainbow), `effect`
// (örn fx_confetti). Çerçeve PlayerAvatar.frame ile (game/lobby ile aynı yol),
// isim rengi katalog color_hex üzerinden (profile_screen ile aynı yol) çözülür.
class _Cosmetics {
  const _Cosmetics({this.frameKey, this.nameColor, this.rainbow = false, this.effectGlyph});

  /// PlayerAvatar'a verilecek çerçeve anahtarı (gold/neon/...). null → çerçeve yok.
  final String? frameKey;

  /// Düz isim rengi (rainbow değilse). null → varsayılan renk.
  final Color? nameColor;

  /// Gökkuşağı isim (color_hex == "rainbow"): düz renk yerine gradyan çizilir.
  final bool rainbow;

  /// Efekt ipucu için küçük simge (örn 🎉). null → efekt yok.
  final String? effectGlyph;

  bool get hasNameStyle => rainbow || nameColor != null;
}

/// Bir leaderboard girişinden kuşanılmış kozmetikleri çözer. Katalog,
/// name_color id'sini renge çevirmek için kullanılır (profile_screen mantığı).
_Cosmetics _cosmeticsOf(Map<String, dynamic> e, CosmeticsState cos) {
  final frameKey = frameKeyFromId(e['frame'] as String?);

  final nameColorId = e['name_color'] as String?;
  final hex = cos.byId(nameColorId)?.colorHex;
  final rainbow = hex == 'rainbow';
  final nameColor = rainbow ? null : parseHexColor(hex);

  return _Cosmetics(
    frameKey: frameKey,
    nameColor: nameColor,
    rainbow: rainbow,
    effectGlyph: _effectGlyph(e['effect'] as String?),
  );
}

/// Efekt id'sini küçük bir simgeye eşler (isim yanında zarif ipucu). Bilinmeyen
/// veya null → simge yok.
String? _effectGlyph(String? effectId) {
  switch (effectId) {
    case 'fx_confetti':
      return '🎉';
    case 'fx_fireworks':
      return '🎆';
    case 'fx_hearts':
      return '💖';
    case 'fx_crown':
      return '👑';
    default:
      return null;
  }
}

/// Kullanıcı adını kuşanılmış isim rengiyle (düz renk veya gökkuşağı gradyanı)
/// + opsiyonel efekt simgesiyle çizer. Kozmetik yoksa sade görünür.
class _StyledName extends StatelessWidget {
  const _StyledName({
    required this.username,
    required this.cosmetics,
    required this.style,
    this.defaultColor,
  });

  final String username;
  final _Cosmetics cosmetics;
  final TextStyle style;
  final Color? defaultColor;

  static const _rainbow = [
    Color(0xFFFF3B6B),
    Color(0xFFFFA500),
    Color(0xFFFFD23F),
    Color(0xFF1DDFBE),
    Color(0xFF00B3FF),
    Color(0xFF8B5CF6),
  ];

  @override
  Widget build(BuildContext context) {
    final base = style.copyWith(color: cosmetics.nameColor ?? defaultColor);
    final text = Text(username, maxLines: 1, overflow: TextOverflow.ellipsis, style: base);

    if (!cosmetics.rainbow) return text;

    // Gökkuşağı: metni gradyanla boya (ShaderMask). Sade fallback rengi koru.
    return ShaderMask(
      shaderCallback: (rect) => const LinearGradient(
        colors: _rainbow,
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
      ).createShader(rect),
      blendMode: BlendMode.srcIn,
      child: Text(username,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: style.copyWith(color: Colors.white)),
    );
  }
}

/// Yuvarlak sıra rozeti. Top-3 metalik gradyan + parıltı; diğerleri sade tonlu disk.
class _RankMedal extends StatelessWidget {
  const _RankMedal(this.rank, {this.size = 34});
  final int rank;
  final double size;

  @override
  Widget build(BuildContext context) {
    final m = _rankMetal(rank);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(colors: m.colors, begin: Alignment.topLeft, end: Alignment.bottomRight),
        border: Border.all(color: Colors.white.withValues(alpha: m.metallic ? 0.45 : 0.08), width: 1),
        boxShadow: m.metallic
            ? [BoxShadow(color: m.colors.last.withValues(alpha: 0.5), blurRadius: 10, offset: const Offset(0, 3))]
            : null,
      ),
      alignment: Alignment.center,
      child: Text('$rank', style: BiladaText.headline(color: m.fg, size: size * 0.44)),
    );
  }
}

/// Sezon sekmesinde gösterilen geri sayım şeridi.
class _SeasonStrip extends StatelessWidget {
  const _SeasonStrip({required this.secondsLeft});
  final int secondsLeft;

  @override
  Widget build(BuildContext context) {
    final s = secondsLeft < 0 ? 0 : secondsLeft;
    final d = s ~/ 86400;
    final h = (s % 86400) ~/ 3600;
    final m = (s % 3600) ~/ 60;
    final label = d > 0 ? '$d gün $h saat' : '$h saat $m dk';
    return Container(
      margin: const EdgeInsets.fromLTRB(20, 0, 20, 12),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        gradient: AppTheme.goldGradient,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          const Text('⏳', style: TextStyle(fontSize: 16)),
          const SizedBox(width: 8),
          Expanded(
            child: Text('Yeni sezona kalan süre',
                style: BiladaText.label(color: const Color(0xFF58002F), size: 12)),
          ),
          Text(label,
              style: BiladaText.title(color: const Color(0xFF58002F), size: 14)),
        ],
      ),
    );
  }
}

/// "SEN" rozeti — kullanıcının kendi satırını işaretler.
class _MeChip extends StatelessWidget {
  const _MeChip();
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppTheme.cPrimaryContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text('SEN', style: BiladaText.label(color: Colors.white, size: 8)),
    );
  }
}

class _RegularEntry extends StatelessWidget {
  const _RegularEntry(
      {required this.entry, required this.rank, this.isSeason = false, this.isMe = false, required this.cos});
  final Map<String, dynamic> entry;
  final int rank;
  final bool isSeason;
  final bool isMe;
  final CosmeticsState cos;

  @override
  Widget build(BuildContext context) {
    final username = entry['username'] as String? ?? '';
    final wins = entry['games_won'] ?? 0;
    final score =
        (isSeason ? (entry['season_points'] ?? entry['score']) : entry['score']) as int? ?? 0;
    final cosmetics = _cosmeticsOf(entry, cos);
    // İlk 3'e ince madalya rengi vurgusu (sol şerit hissi: renkli kenarlık).
    final isTop3 = rank <= 3;
    final accent = _rankMetal(rank).colors.last;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassCard(
        onTap: () => showProfileSheet(context, username: username),
        color: isMe
            ? AppTheme.cPrimaryContainer.withValues(alpha: 0.16)
            : isTop3
                ? accent.withValues(alpha: 0.08)
                : null,
        padding: const EdgeInsets.fromLTRB(10, 10, 16, 10),
        child: Row(
          children: [
            _RankMedal(rank, size: 34),
            const SizedBox(width: 12),
            PlayerAvatar(
              avatarId: entry['avatar_id'] as String? ?? 'default_01',
              username: username,
              size: 42,
              frame: cosmetics.frameKey,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: _StyledName(
                          username: username,
                          cosmetics: cosmetics,
                          defaultColor: AppTheme.cOnSurface,
                          style: BiladaText.title(size: 15),
                        ),
                      ),
                      if (cosmetics.effectGlyph != null) ...[
                        const SizedBox(width: 4),
                        Text(cosmetics.effectGlyph!, style: const TextStyle(fontSize: 13)),
                      ],
                      if (isMe) ...[const SizedBox(width: 6), const _MeChip()],
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text('$wins galibiyet', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 11)),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text('$score', style: BiladaText.headline(color: AppTheme.cPrimary, size: 18)),
                Text(isSeason ? 'puan' : 'skor', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 9)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MyRankBar extends StatelessWidget {
  const _MyRankBar({required this.entry});
  final Map<String, dynamic> entry;

  @override
  Widget build(BuildContext context) {
    final rank = entry['rank'] as int? ?? 0;
    final score = entry['score'] as int? ?? 0;
    final pointsToNext = entry['points_to_next'] as int?;
    final atTop = pointsToNext == null;
    return Container(
      margin: EdgeInsets.fromLTRB(20, 0, 20, 92 + MediaQuery.of(context).padding.bottom),
      padding: const EdgeInsets.fromLTRB(12, 12, 18, 12),
      decoration: BoxDecoration(
        gradient: AppTheme.primaryGradient,
        borderRadius: BorderRadius.circular(22),
        boxShadow: [BoxShadow(color: AppTheme.cPrimaryContainer.withValues(alpha: 0.45), blurRadius: 24, offset: const Offset(0, 6))],
      ),
      child: Row(
        children: [
          // Beyaz çerçeveli sıra rozeti — koyu pembe zemine kontrast
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.18),
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white.withValues(alpha: 0.5), width: 1.5),
            ),
            alignment: Alignment.center,
            child: Text('$rank', style: BiladaText.headline(color: Colors.white, size: 17)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Senin Sıran', style: BiladaText.label(color: Colors.white.withValues(alpha: 0.85), size: 11)),
                const SizedBox(height: 1),
                Row(
                  children: [
                    Icon(atTop ? Icons.local_fire_department_rounded : Icons.trending_up_rounded,
                        color: Colors.white, size: 15),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(
                        atTop ? 'Zirvedesin, kimse yetişemiyor!' : 'Üst sıraya $pointsToNext puan',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: BiladaText.title(color: Colors.white, size: 13),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text('$score', style: BiladaText.headline(color: Colors.white, size: 24)),
        ],
      ),
    );
  }
}

/// Boş sıralama durumu — sade, davetkâr.
class _EmptyView extends StatelessWidget {
  const _EmptyView();
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text('🏅', style: TextStyle(fontSize: 46)),
          const SizedBox(height: 12),
          Text('Henüz sıralama yok', style: BiladaText.title(color: AppTheme.cOnSurfaceVariant, size: 16)),
          const SizedBox(height: 4),
          Text('İlk maçını oyna, tabloya adını yazdır!',
              textAlign: TextAlign.center,
              style: BiladaText.label(color: AppTheme.cOutline, size: 12)),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.wifi_off_rounded, color: AppTheme.cOutline, size: 40),
          const SizedBox(height: 12),
          Text('Yüklenemedi', style: BiladaText.body(color: AppTheme.cOnSurfaceVariant)),
          const SizedBox(height: 12),
          TextButton(onPressed: onRetry, child: const Text('Tekrar Dene')),
        ],
      ),
    );
  }
}
