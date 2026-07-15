import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/daily/providers/daily_provider.dart';
import 'package:quizroyale/features/daily/widgets/daily_reward_dialog.dart';
import 'package:quizroyale/features/home/widgets/gift_character_sheet.dart';
import 'package:quizroyale/features/quests/providers/quests_provider.dart';
import 'package:quizroyale/features/quests/widgets/quests_card.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';
// GÜNÜN 5 SORUSU (v1.2): ana ekrandan GİZLENDİ (dormant). Kart/provider/route
// kodu silinmedi; yalnızca buradaki giriş noktası kaldırıldı. Bu yüzden
// daily_challenge_provider ve daily_challenge_card import'ları kaldırıldı.

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  /// Hediye karakter ekranının yalnızca bir kez gösterilmesi için prefs bayrağı.
  static const String _kGiftShownKey = 'gift_character_shown_v1';

  @override
  void initState() {
    super.initState();
    // Açılışta günlük ödül durumunu ve günlük görevleri çek (otomatik dialog
    // AÇMA — sadece rozet). GÜNÜN 5 SORUSU çağrısı KALDIRILDI (mod gizlendi).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(dailyProvider.notifier).load();
      ref.read(questsProvider.notifier).load();
      _maybeShowGiftCharacter();
    });
  }

  /// HEDİYE KARAKTER (v1.2): Başlangıç altını 1000→300'e indi; telafi olarak
  /// yeni oyuncuya ilk ana ekranda BİR KEZ bedava karakter seçtiriyoruz.
  /// Yalnız avatar hâlâ varsayılansa (yeni oyuncu) hediye ekranı açılır;
  /// yerleşik oyuncuda sadece bayrak işaretlenir, ekran gösterilmez.
  Future<void> _maybeShowGiftCharacter() async {
    SharedPreferences prefs;
    try {
      prefs = await SharedPreferences.getInstance();
    } catch (_) {
      return;
    }
    if (prefs.getBool(_kGiftShownKey) ?? false) return;

    // Kullanıcı verisi (avatar_id) yüklenene kadar kısa süre bekle: cold-start'ta
    // authProvider kullanıcıyı async çeker. Erken karar verirsek yerleşik
    // oyuncunun avatar'ını yanlışlıkla varsayılana çevirebiliriz. Yüklenemezse
    // bayrağı SET ETMEDEN çık — sonraki ana ekran ziyaretinde tekrar denenir.
    Map<String, dynamic>? user;
    for (var i = 0; i < 20; i++) {
      user = ref.read(authProvider).user;
      if (user != null) break;
      await Future.delayed(const Duration(milliseconds: 150));
      if (!mounted) return;
    }
    if (user == null) return;

    await prefs.setBool(_kGiftShownKey, true);

    final avatarId = user['avatar_id'] as String?;
    final isDefault =
        avatarId == null || avatarId == 'robot' || avatarId == 'default_01';
    if (!isDefault) return; // yerleşik oyuncu — hediyeyi tekrar sunma
    if (!mounted) return;
    await showGiftCharacterSheet(context, ref);
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final username = (user?['username'] ?? 'Oyuncu').toString();
    final coins = (user?['coins'] as num?)?.toInt() ?? 0;
    final gamesPlayed = (user?['games_played'] as num?)?.toInt() ?? 0;
    final winRate = (user?['win_rate'] as num?)?.toInt() ?? 0;

    return Stack(
      children: [
        const Positioned.fill(child: BiladaBackground()),
        Column(
          children: [
            // Üst barda logo GİZLİ: hemen altında büyük hero "Bil ya da Düş"
            // başlığı var; ikisi birden çıkınca isim alt alta iki kez görünüp
            // göz tırmalıyordu. Hero başlık kalsın, üst bar sade olsun.
            BiladaTopBar(
              username: username,
              coins: coins,
              avatarSeed: username.hashCode,
              showLogo: false,
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 4, 20, 100),
                child: Column(
                  children: [
                    const SizedBox(height: 4),
                    const BiladaLogo(fontSize: 38),
                    const SizedBox(height: 10),
                    _onlineBadge(),
                    _dailyBadge(context, ref),
                    const SizedBox(height: 10),
                    _seasonStrip(context),
                    const SizedBox(height: 16),
                    _hero(user),
                    const SizedBox(height: 18),
                    // BİRİNCİL AKSİYON — en büyük, en parlak buton. Aşağıdaki
                    // günlük kartlar bunu GÖLGELEMEZ: biri mint gradyanlı ince
                    // bir şerit, diğeri sessiz cam kart.
                    ChunkyButton(
                      height: 64,
                      onPressed: () => context.go('/lobby'),
                      child: const Text('HIZLI MAÇ'),
                    ),
                    const SizedBox(height: 12),
                    // ZOR MOD (v1.2): Rafta duran turnuva "ZOR MOD" olarak geri
                    // açıldı. HIZLI MAÇ birincil kalır; bu kart belirgin ama onu
                    // gölgelemez (ateş/kor teması, "gaza getiren").
                    // NOT: Günün 5 Sorusu kartı (DailyChallengeCard) buradan
                    // KALDIRILDI — mod gizlendi (dormant).
                    _hardModeCard(context),
                    const SizedBox(height: 12),
                    ChunkyButton(
                      height: 56,
                      color: AppTheme.cSecondaryContainer,
                      foreground: Colors.white,
                      shadowColor: AppTheme.cSecondaryShadow,
                      onPressed: () => context.go('/room'),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.group_rounded),
                          SizedBox(width: 8),
                          Text('ARKADAŞLARLA OYNA', style: TextStyle(fontSize: 18)),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    // İkinci geri dönüş kancası: 3 küçük görev, ödül hazırsa
                    // altın rozet çeker. Dokununca detay sheet açılır.
                    const QuestsCard(),
                    const SizedBox(height: 18),
                    Row(
                      children: [
                        Expanded(
                          child: _statCard(
                            icon: Icons.workspace_premium_rounded,
                            iconColor: AppTheme.cTertiary,
                            label: 'Galibiyet Oranı',
                            value: '%$winRate',
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: _statCard(
                            icon: Icons.local_fire_department_rounded,
                            iconColor: AppTheme.cSecondary,
                            label: 'Oynanan Maç',
                            value: '$gamesPlayed',
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  /// Günlük ödül rozeti — yalnızca alınabilirken görünür, dokununca dialog açar.
  /// Otomatik açılmaz (kullanıcıyı rahatsız etmez).
  Widget _dailyBadge(BuildContext context, WidgetRef ref) {
    final daily = ref.watch(dailyProvider);
    if (!daily.canClaim) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: GestureDetector(
        onTap: () => showDailyRewardDialog(context),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            gradient: AppTheme.goldGradient,
            borderRadius: BorderRadius.circular(999),
            boxShadow: [
              BoxShadow(color: AppTheme.gold.withValues(alpha: 0.4), blurRadius: 14, offset: const Offset(0, 4)),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('🎁', style: TextStyle(fontSize: 16)),
              const SizedBox(width: 8),
              Text(
                'Günlük Ödülünü Al',
                style: BiladaText.label(color: const Color(0xFF58002F), size: 12),
              ),
              if (daily.streak > 0) ...[
                const SizedBox(width: 8),
                Text('🔥${daily.streak}', style: BiladaText.label(color: const Color(0xFF58002F), size: 12)),
              ],
            ],
          ),
        ),
      ),
    );
  }

  /// ZOR MOD giriş kartı — rafta duran turnuva "ZOR MOD" olarak dirildi.
  /// Ateş/kor temalı, gaza getiren ama HIZLI MAÇ'ı gölgelemeyen ikincil aksiyon.
  /// Dokununca /tournament (yeniden markalı ZOR MOD) ekranına gider.
  Widget _hardModeCard(BuildContext context) {
    return GestureDetector(
      onTap: () => context.push('/tournament'),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [AppTheme.accentOrange, Color(0xFFC01048)], // kor → ateş
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: AppTheme.accentOrange.withValues(alpha: 0.42),
              blurRadius: 18,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Row(
          children: [
            const Text('🔥', style: TextStyle(fontSize: 26)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text('ZOR MOD',
                          style: BiladaText.headline(color: Colors.white, size: 18)),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.22),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text('3x PUAN',
                            style: BiladaText.label(color: Colors.white, size: 10)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(
                    'Zor sorular · Ödül havuzu · 3x puan',
                    style: BiladaText.label(
                        color: Colors.white.withValues(alpha: 0.9), size: 12),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right_rounded, color: Colors.white),
          ],
        ),
      ),
    );
  }

  /// Sezon girişi — gold şerit, dokununca sezon ödülleri ekranını açar.
  Widget _seasonStrip(BuildContext context) {
    return GestureDetector(
      onTap: () => context.push('/season'),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          gradient: AppTheme.goldGradient,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(color: AppTheme.gold.withValues(alpha: 0.35), blurRadius: 14, offset: const Offset(0, 4)),
          ],
        ),
        child: Row(
          children: [
            const Text('🏆', style: TextStyle(fontSize: 18)),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Sezon Ödülleri',
                style: BiladaText.label(color: const Color(0xFF58002F), size: 13),
              ),
            ),
            const Icon(Icons.chevron_right_rounded, color: Color(0xFF58002F)),
          ],
        ),
      ),
    );
  }

  Widget _onlineBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.cSurfaceVariant.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(width: 8, height: 8, decoration: const BoxDecoration(color: AppTheme.cTertiary, shape: BoxShape.circle)),
          const SizedBox(width: 8),
          Text('Çevrimiçi', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
        ],
      ),
    );
  }

  /// Kuşanılı karakteri (avatar) sahnede gösterir — oyuncunun seçimi ana
  /// ekrana yansısın. Avatar yoksa varsayılan başlangıç karakterine düşer.
  Widget _hero(Map<String, dynamic>? user) {
    final avatarId = (user?['avatar_id'] as String?) ?? 'robot';
    final username = (user?['username'] ?? 'Oyuncu').toString();
    return Container(
      width: 152,
      height: 152,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [AppTheme.cPrimaryContainer.withValues(alpha: 0.35), Colors.transparent],
        ),
      ),
      alignment: Alignment.center,
      child: Container(
        width: 116,
        height: 116,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: const LinearGradient(
            colors: [AppTheme.cPrimaryContainer, AppTheme.cSecondaryContainer],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          boxShadow: [BoxShadow(color: AppTheme.cPrimaryContainer.withValues(alpha: 0.4), blurRadius: 32, offset: const Offset(0, 16))],
        ),
        alignment: Alignment.center,
        child: PlayerAvatar(avatarId: avatarId, username: username, size: 104),
      ),
    );
  }

  Widget _statCard({required IconData icon, required Color iconColor, required String label, required String value}) {
    return GlassCard(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 12),
      child: Column(
        children: [
          Icon(icon, color: iconColor),
          const SizedBox(height: 4),
          Text(label, style: BiladaText.label(), textAlign: TextAlign.center),
          const SizedBox(height: 2),
          Text(value, style: BiladaText.title(size: 20)),
        ],
      ),
    );
  }
}
