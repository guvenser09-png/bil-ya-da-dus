import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/daily/providers/daily_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/gold_coin.dart';

/// Günlük ödül diyaloğunu açar. home_screen rozeti dokununca çağırır.
Future<void> showDailyRewardDialog(BuildContext context) {
  return showDialog<void>(
    context: context,
    barrierColor: Colors.black.withValues(alpha: 0.7),
    builder: (_) => const _DailyRewardDialog(),
  );
}

class _DailyRewardDialog extends ConsumerStatefulWidget {
  const _DailyRewardDialog();

  @override
  ConsumerState<_DailyRewardDialog> createState() => _DailyRewardDialogState();
}

class _DailyRewardDialogState extends ConsumerState<_DailyRewardDialog>
    with SingleTickerProviderStateMixin {
  late final AnimationController _coinCtrl =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 700));
  bool _claimed = false;
  int _claimedReward = 0;
  int _claimedStreak = 0;

  @override
  void dispose() {
    _coinCtrl.dispose();
    super.dispose();
  }

  Future<void> _claim() async {
    final result = await ref.read(dailyProvider.notifier).claim();
    if (!mounted || result == null) return;
    if (result.claimed) {
      setState(() {
        _claimed = true;
        _claimedReward = result.reward;
        _claimedStreak = result.streak;
      });
      _coinCtrl.forward(from: 0);
      // Bakiye tek gerçek kaynaktan tazelensin: üst bardaki CoinPill
      // (authProvider.user.coins) günlük ödül sonrası hemen güncellenir.
      // ignore: unawaited_futures
      ref.read(authProvider.notifier).refreshUser();
    } else if (result.alreadyClaimed) {
      // Bugün zaten alınmış — bilgilendir ve kapat.
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Bugünkü ödülü zaten aldın. Yarın görüşürüz! 👋')),
      );
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dailyProvider);
    final streak = _claimed ? _claimedStreak : state.streak;
    final reward = _claimed ? _claimedReward : state.todayReward;

    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: const EdgeInsets.symmetric(horizontal: 32),
      child: GlassCard(
        padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
        color: AppTheme.cSurfaceContainerHigh.withValues(alpha: 0.96),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('GÜNLÜK ÖDÜL', style: BiladaText.label(color: AppTheme.cTertiary, size: 13)),
            const SizedBox(height: 8),
            // Streak göstergesi (örn 🔥x3).
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              decoration: BoxDecoration(
                color: AppTheme.cSecondaryContainer.withValues(alpha: 0.25),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('🔥', style: TextStyle(fontSize: 18)),
                  const SizedBox(width: 6),
                  Text(
                    '$streak gün üst üste',
                    style: BiladaText.title(color: AppTheme.cSecondary, size: 16),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            _coin(reward),
            const SizedBox(height: 20),
            if (_claimed) ...[
              Text('Teşekkürler! 🎉', style: BiladaText.headline(size: 22)),
              const SizedBox(height: 6),
              Text(
                'Yarın daha büyük ödül için tekrar gel.',
                style: BiladaText.body(color: AppTheme.cOnSurfaceVariant),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              ChunkyButton(
                height: 54,
                color: AppTheme.cTertiaryContainer,
                foreground: Colors.white,
                shadowColor: AppTheme.cTertiaryShadow,
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('SÜPER!'),
              ),
            ] else ...[
              Text('Bugünkü ödülün hazır!', style: BiladaText.headline(size: 20)),
              if (state.nextReward > 0) ...[
                const SizedBox(height: 6),
                Text(
                  'Yarın: ${state.nextReward} altın',
                  style: BiladaText.label(color: AppTheme.cOutline, size: 12),
                ),
              ],
              const SizedBox(height: 20),
              ChunkyButton(
                height: 56,
                onPressed: state.claiming ? null : _claim,
                child: state.claiming
                    ? const SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white),
                      )
                    : const Text('AL'),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: Text('Sonra', style: BiladaText.label(color: AppTheme.cOutline, size: 12)),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Coin görseli — claim sonrası hafif "pop" animasyonu.
  Widget _coin(int reward) {
    final scale = _claimed
        ? Tween<double>(begin: 0.4, end: 1.0)
            .animate(CurvedAnimation(parent: _coinCtrl, curve: Curves.elasticOut))
        : const AlwaysStoppedAnimation<double>(1.0);
    return ScaleTransition(
      scale: scale,
      child: Container(
        width: 110,
        height: 110,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: AppTheme.goldGradient,
          boxShadow: [
            BoxShadow(color: AppTheme.gold.withValues(alpha: 0.5), blurRadius: 28, spreadRadius: 2),
          ],
        ),
        alignment: Alignment.center,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const GoldCoin(size: 38),
            const SizedBox(height: 2),
            Text('+$reward', style: BiladaText.displayXl(color: const Color(0xFF58002F), size: 26)),
          ],
        ),
      ),
    );
  }
}
