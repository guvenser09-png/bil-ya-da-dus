import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/season/providers/season_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// Sezon Ödülleri ekranı — TEK ücretsiz ödül hattı.
///
/// Oynayarak kazanılan sezon puanıyla kademeler açılır; her kademenin ödülü
/// (altın / kozmetik) açıldığında claim edilebilir. Battle Pass / premium hat
/// tamamen kaldırıldı.
class SeasonScreen extends ConsumerWidget {
  const SeasonScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(seasonProvider);

    // Hata olunca snackbar (uygun olmayan claim vb.).
    ref.listen(seasonProvider, (prev, next) {
      if (next.error != null && next.error != prev?.error) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(next.error!)));
      }
    });

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground(showFloaters: false)),
          SafeArea(
            bottom: false,
            child: Column(
              children: [
                _header(context),
                Expanded(child: _body(context, ref, state)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _header(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 4, 20, 8),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_rounded, color: AppTheme.cOnSurface),
            onPressed: () => context.pop(),
          ),
          Text('Sezon Ödülleri', style: BiladaText.headline(size: 22)),
          const Spacer(),
          const Text('🏆', style: TextStyle(fontSize: 22)),
        ],
      ),
    );
  }

  Widget _body(BuildContext context, WidgetRef ref, SeasonState state) {
    if (state.loading && !state.loaded) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer));
    }
    if (state.loaded && state.tiers.isEmpty) {
      return _emptyOrError(context, ref, state);
    }

    final sorted = [...state.tiers]..sort((a, b) => a.tier.compareTo(b.tier));

    return RefreshIndicator(
      color: AppTheme.cPrimaryContainer,
      backgroundColor: AppTheme.cSurfaceContainer,
      onRefresh: () => ref.read(seasonProvider.notifier).load(),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 40),
        children: [
          _seasonCard(state),
          const SizedBox(height: 18),
          Row(
            children: [
              Container(
                width: 4,
                height: 18,
                decoration: BoxDecoration(
                  color: AppTheme.gold,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 8),
              Text('KADEME ÖDÜLLERİ', style: BiladaText.label(color: AppTheme.gold, size: 13)),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Oyna, sezon puanı kazan ve kademeleri aç.',
            style: BiladaText.label(color: AppTheme.cOutline, size: 11),
          ),
          const SizedBox(height: 12),
          ...sorted.map((t) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _TierRow(tier: t),
              )),
        ],
      ),
    );
  }

  Widget _emptyOrError(BuildContext context, WidgetRef ref, SeasonState state) {
    final isError = state.error != null;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(isError ? '😕' : '🏆', style: const TextStyle(fontSize: 48)),
            const SizedBox(height: 12),
            Text(
              isError ? 'Sezon yüklenemedi' : 'Şu an aktif sezon yok',
              style: BiladaText.title(size: 18),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 6),
            Text(
              isError
                  ? 'Bağlantını kontrol edip tekrar dene.'
                  : 'Yeni sezon başlayınca ödüller burada olacak.',
              style: BiladaText.label(color: AppTheme.cOutline, size: 12),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            ChunkyButton(
              expand: false,
              height: 48,
              onPressed: () => ref.read(seasonProvider.notifier).load(),
              child: const Text('YENİLE', style: TextStyle(fontSize: 16)),
            ),
          ],
        ),
      ),
    );
  }

  /// Sezon başlığı + kalan gün + ilerleme çubuğu (my_points → bir sonraki tier).
  Widget _seasonCard(SeasonState state) {
    final info = state.progressInfo;
    final atMax = info.next == null;
    return GlassCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  state.seasonId == null ? 'Sezon' : 'Sezon ${state.seasonId}',
                  style: BiladaText.title(size: 18),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              PillBadge('${state.endsInDays} GÜN', color: AppTheme.gold, fg: AppTheme.cOnPrimaryContainer),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Kademe ${state.myTier} • ${state.myPoints} puan',
            style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 12),
          ),
          const SizedBox(height: 14),
          _progressBar(info.progress),
          const SizedBox(height: 6),
          Text(
            atMax
                ? 'Tüm kademeler tamamlandı 🎉'
                : 'Sonraki kademe (${info.next!.tier}) için ${info.nextPoints - state.myPoints} puan',
            style: BiladaText.label(color: AppTheme.cOutline, size: 11),
          ),
        ],
      ),
    );
  }

  Widget _progressBar(double progress) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: Stack(
        children: [
          Container(height: 14, color: AppTheme.cSurfaceContainerHighest),
          FractionallySizedBox(
            widthFactor: progress.clamp(0.0, 1.0),
            child: Container(
              height: 14,
              decoration: const BoxDecoration(gradient: AppTheme.goldGradient),
            ),
          ),
        ],
      ),
    );
  }
}

/// Tek bir kademenin ödül satırı: kademe rozeti + ödül + durum butonu.
class _TierRow extends ConsumerWidget {
  const _TierRow({required this.tier});

  final SeasonTier tier;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(seasonProvider);
    final reward = tier.reward;
    final claimed = tier.claimed;
    final claimable = tier.claimable;
    final busy = state.busyKey == 'claim_${tier.tier}';

    return GlassCard(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          // Kademe rozeti.
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: AppTheme.gold.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppTheme.gold.withValues(alpha: 0.5)),
            ),
            alignment: Alignment.center,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text('${tier.tier}',
                    style: BiladaText.title(color: AppTheme.gold, size: 18)),
                Text('KADEME',
                    style: BiladaText.label(color: AppTheme.gold, size: 7)),
              ],
            ),
          ),
          const SizedBox(width: 14),
          // Ödül ikonu + etiketi.
          if (reward == null)
            Expanded(
              child: Text('—', style: BiladaText.title(color: AppTheme.cOutline, size: 18)),
            )
          else
            Expanded(
              child: Row(
                children: [
                  Text(reward.icon, style: const TextStyle(fontSize: 28)),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          reward.type == 'coins' ? '${reward.label} Altın' : reward.label,
                          style: BiladaText.title(size: 15),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        Text(
                          '${tier.pointsRequired} puanda açılır',
                          style: BiladaText.label(color: AppTheme.cOutline, size: 10),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(width: 10),
          _statusWidget(ref, reward, claimed, claimable, busy),
        ],
      ),
    );
  }

  Widget _statusWidget(
      WidgetRef ref, SeasonReward? reward, bool claimed, bool claimable, bool busy) {
    if (reward == null) {
      return const SizedBox(width: 84, height: 36);
    }
    if (claimed) {
      return SizedBox(
        width: 84,
        height: 36,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.check_circle_rounded, color: AppTheme.gold, size: 18),
            const SizedBox(width: 4),
            Text('ALINDI', style: BiladaText.label(color: AppTheme.gold, size: 11)),
          ],
        ),
      );
    }
    if (busy) {
      return const SizedBox(
        width: 84,
        height: 36,
        child: ChunkyButton(
          height: 36,
          depth: 3,
          onPressed: null,
          child: SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
          ),
        ),
      );
    }
    if (claimable) {
      return SizedBox(
        width: 84,
        height: 36,
        child: ChunkyButton(
          height: 36,
          depth: 3,
          color: AppTheme.gold,
          foreground: AppTheme.cOnPrimaryContainer,
          shadowColor: const Color(0xFF8A6A00),
          onPressed: () => ref.read(seasonProvider.notifier).claim(tier.tier),
          child: const Text('AL', style: TextStyle(fontSize: 14)),
        ),
      );
    }
    // Henüz ulaşılmadı → kilitli.
    return const SizedBox(
      width: 84,
      height: 36,
      child: Center(child: Icon(Icons.lock_rounded, color: AppTheme.cOutline, size: 18)),
    );
  }
}
