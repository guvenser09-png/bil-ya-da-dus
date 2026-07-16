import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/network/api_client.dart';
import 'package:quizroyale/core/services/ad_service.dart';
import 'package:quizroyale/core/services/haptic_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/gold_coin.dart';

/// Maç-öncesi kalkan seçim sonucu — lobi bunu okuyup üst rozeti (kalkan
/// hazır mı?) ve oturum-içi "bir daha sorma" tercihini günceller.
class ShieldPromptResult {
  const ShieldPromptResult({
    this.prepared = false,
    this.dontAskAgain = false,
  });

  /// Kalkan hazırlandı mı (altın veya reklam ile)?
  final bool prepared;

  /// Kullanıcı bu oturumda bir daha sorulmasını istemiyor mu?
  final bool dontAskAgain;
}

/// Maç-öncesi kalkan seçim sayfasını açar. Kullanıcı dışarı tıklarsa (null)
/// "kalkansız devam" kabul edilir.
Future<ShieldPromptResult> showShieldPrompt(BuildContext context) async {
  final res = await showModalBottomSheet<ShieldPromptResult>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => const _ShieldPromptSheet(),
  );
  return res ?? const ShieldPromptResult();
}

class _ShieldPromptSheet extends ConsumerStatefulWidget {
  const _ShieldPromptSheet();

  @override
  ConsumerState<_ShieldPromptSheet> createState() => _ShieldPromptSheetState();
}

class _ShieldPromptSheetState extends ConsumerState<_ShieldPromptSheet> {
  bool _busyGold = false;
  bool _busyAd = false;

  /// Altın yetersiz çıktı → reklam seçeneğini vurgula + ipucu göster.
  bool _insufficientGold = false;

  /// Bu oturumda bir daha sorma tercihi.
  bool _dontAskAgain = false;

  bool get _busy => _busyGold || _busyAd;

  int get _coins =>
      (ref.watch(authProvider).user?['coins'] as num?)?.toInt() ?? 0;

  void _close(ShieldPromptResult result) {
    if (!mounted) return;
    Navigator.of(context).pop(result);
  }

  /// "100 Altın" — prepare-shield source=gold. Yetersizse reklam öner.
  Future<void> _payWithGold() async {
    if (_busy) return;
    HapticService().buttonTap();
    setState(() {
      _busyGold = true;
      _insufficientGold = false;
    });
    try {
      final res = await ApiClient.instance.post(
        '/api/users/me/prepare-shield',
        body: {'source': 'gold'},
      );
      if (res['ok'] == true) {
        // Bakiye düştü → üst barlar güncel kalsın.
        await ref.read(authProvider.notifier).refreshUser();
        _close(const ShieldPromptResult(prepared: true));
        return;
      }
      // ok:false → büyük ihtimalle yetersiz altın.
      if (mounted) setState(() => _insufficientGold = true);
    } catch (_) {
      if (mounted) setState(() => _insufficientGold = true);
    } finally {
      if (mounted) setState(() => _busyGold = false);
    }
  }

  /// "📺 Reklam İzle" — ödüllü reklam → prepare-shield source=ad.
  Future<void> _watchAd() async {
    if (_busy) return;
    HapticService().buttonTap();
    setState(() => _busyAd = true);
    try {
      final status = await AdService.instance.showRewarded(placement: 'shield');
      if (status == AdRewardStatus.earned) {
        // Reklam kredisi verildi → kalkanı bu kredi ile hazırla.
        try {
          final res = await ApiClient.instance.post(
            '/api/users/me/prepare-shield',
            body: {'source': 'ad'},
          );
          if (res['ok'] == true) {
            await ref.read(authProvider.notifier).refreshUser();
            _close(const ShieldPromptResult(prepared: true));
            return;
          }
        } catch (_) {}
        _showSnack('Kalkan hazırlanamadı, tekrar dene.');
      } else if (status == AdRewardStatus.unavailable) {
        _showSnack('Reklam şu an yok, birazdan tekrar dene.');
      }
      // dismissed → kullanıcı erken kapattı; sessizce sheet'te kal.
    } finally {
      if (mounted) setState(() => _busyAd = false);
    }
  }

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final coins = _coins;
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: AppTheme.cSurfaceContainerLow,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      padding: EdgeInsets.fromLTRB(
          24, 16, 24, 20 + MediaQuery.of(context).padding.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: AppTheme.cOutlineVariant,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 20),
          const Text('🛡️', style: TextStyle(fontSize: 40)),
          const SizedBox(height: 10),
          Text('Kalkan ister misin?', style: BiladaText.headline(size: 24)),
          const SizedBox(height: 6),
          Text(
            'Kalkan, ilk yanlış cevabında elenmekten kurtarır.',
            style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 22),

          // ── 100 Altın ──
          ChunkyButton(
            height: 54,
            color: AppTheme.gold,
            foreground: AppTheme.cOnPrimaryContainer,
            shadowColor: const Color(0xFF8A6A00),
            onPressed: _busy ? null : _payWithGold,
            child: _busyGold
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                        strokeWidth: 2.5, color: Color(0xFF58002F)),
                  )
                : const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      GoldCoin(size: 18),
                      SizedBox(width: 8),
                      Text('100 Altın', style: TextStyle(fontSize: 17)),
                    ],
                  ),
          ),
          const SizedBox(height: 4),
          Text(
            _insufficientGold
                ? 'Altın yok (bakiye: $coins) — reklam izleyerek bedava al 👇'
                : 'Bakiyen: $coins altın',
            style: BiladaText.label(
              color: _insufficientGold ? AppTheme.cError : AppTheme.cOnSurfaceVariant,
              size: 12,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),

          // ── 📺 Reklam İzle ──
          ChunkyButton(
            height: 54,
            color: AppTheme.cTertiary,
            foreground: AppTheme.cOnTertiary,
            shadowColor: AppTheme.cSurfaceContainerLowest,
            onPressed: _busy ? null : _watchAd,
            child: _busyAd
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                        strokeWidth: 2.5, color: Colors.white),
                  )
                : const Text('📺 Reklam İzle → Bedava Kalkan',
                    style: TextStyle(fontSize: 16)),
          ),
          const SizedBox(height: 14),

          // ── Kalkansız Oyna ──
          TextButton(
            onPressed: _busy
                ? null
                : () {
                    HapticService().buttonTap();
                    _close(ShieldPromptResult(dontAskAgain: _dontAskAgain));
                  },
            child: Text('Kalkansız Oyna',
                style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 14)),
          ),

          // ── Bu oturumda bir daha sorma (küçük konfor) ──
          InkWell(
            onTap: _busy
                ? null
                : () => setState(() => _dontAskAgain = !_dontAskAgain),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    _dontAskAgain
                        ? Icons.check_box_rounded
                        : Icons.check_box_outline_blank_rounded,
                    size: 18,
                    color: AppTheme.cOnSurfaceVariant,
                  ),
                  const SizedBox(width: 6),
                  Text('Bu oturumda bir daha sorma',
                      style: BiladaText.label(
                          color: AppTheme.cOnSurfaceVariant, size: 12)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
