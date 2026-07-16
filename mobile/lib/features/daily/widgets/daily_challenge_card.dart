import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/daily/providers/daily_challenge_provider.dart';
import 'package:quizroyale/features/daily/widgets/daily_share_sheet.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/gold_coin.dart';

/// Ana ekrandaki "🗓️ GÜNÜN 5 SORUSU" kartı — günlük dönüşün omurgası.
///
/// İki hâli var:
/// - BUGÜN OYNANMADI  → vurgulu (mint gradyan + parlak kenar), seri sayısı,
///   "OYNA" çağrısı. HIZLI MAÇ'ı gölgelemesin diye yüksekliği ölçülü tutuldu.
/// - BUGÜN OYNANDI    → sakin cam kart: 🟩🟥 ızgarası, kaç doğru, kazanılan
///   altın, "PAYLAŞ" ve "yarın tekrar gel".
class DailyChallengeCard extends ConsumerWidget {
  const DailyChallengeCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(dailyChallengeProvider);

    // Henüz yüklenmediyse ya da hata varsa yer kaplama (ana ekran zıplamasın).
    if (!state.loaded || state.error != null) return const SizedBox.shrink();

    return state.playedToday ? _played(context, state) : _pending(context, state);
  }

  /// Oynanmadı: dikkat çeken çağrı.
  Widget _pending(BuildContext context, DailyChallengeState state) {
    return GestureDetector(
      onTap: () => context.push('/daily'),
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
        decoration: BoxDecoration(
          gradient: AppTheme.mintGradient,
          borderRadius: BorderRadius.circular(20),
          boxShadow: const [
            BoxShadow(color: AppTheme.cTertiaryShadow, offset: Offset(0, 5), blurRadius: 0),
          ],
        ),
        child: Row(
          children: [
            const Text('🗓️', style: TextStyle(fontSize: 26)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'GÜNÜN 5 SORUSU',
                    style: BiladaText.label(color: const Color(0xFF00332B), size: 13),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    state.streak > 0
                        ? '🔥 ${state.streak} günlük seri — bugünü kaçırma!'
                        : 'Herkese aynı 5 soru • +${state.maxReward} altına kadar',
                    style: BiladaText.body(color: const Color(0xFF00332B), size: 12),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFF00332B),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text('OYNA', style: BiladaText.label(color: Colors.white, size: 12)),
            ),
          ],
        ),
      ),
    );
  }

  /// Oynandı: sonucu göster, paylaşıma davet et, yarına çapa at.
  Widget _played(BuildContext context, DailyChallengeState state) {
    final result = state.result;
    return GlassCard(
      onTap: () => context.push('/daily'),
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      child: Column(
        children: [
          Row(
            children: [
              const Text('🗓️', style: TextStyle(fontSize: 22)),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'GÜNÜN 5 SORUSU',
                  style: BiladaText.label(color: AppTheme.cTertiary, size: 12),
                ),
              ),
              if (state.streak > 0)
                Text(
                  '🔥${state.streak}',
                  style: BiladaText.label(color: AppTheme.gold, size: 12),
                ),
            ],
          ),
          const SizedBox(height: 10),
          if (result != null) ...[
            Row(
              children: [
                Text(result.grid, style: const TextStyle(fontSize: 20, letterSpacing: 2)),
                const SizedBox(width: 10),
                Text(
                  '${result.correctCount}/${result.questionCount}',
                  style: BiladaText.title(size: 18),
                ),
                const Spacer(),
                Text(
                  '+${result.coinsEarned}',
                  style: BiladaText.label(color: AppTheme.gold, size: 13),
                ),
                const SizedBox(width: 3),
                const GoldCoin(size: 14),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Yarın yeni 5 soru 👋',
                    style: BiladaText.label(size: 11),
                  ),
                ),
                // Viral kanal: sonucu paylaşmak ana ekrandan da bir dokunuş.
                Builder(
                  builder: (btnContext) => GestureDetector(
                    onTap: () => shareDailyResult(btnContext, result),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppTheme.cTertiaryContainer,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.ios_share_rounded, size: 13, color: Colors.white),
                          const SizedBox(width: 5),
                          Text('PAYLAŞ',
                              style: BiladaText.label(color: Colors.white, size: 11)),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ] else
            Text(
              'Bugünkü soruları tamamladın. Yarın yeni 5 soru! 👋',
              style: BiladaText.body(size: 13),
            ),
        ],
      ),
    );
  }
}
