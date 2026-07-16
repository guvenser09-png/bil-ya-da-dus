import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/services/ad_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/store/providers/store_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/gold_coin.dart';

/// Mağaza ekranı — tek para birimi ALTIN üzerine kurulu.
///
/// İlk lansman TAMAMEN ÜCRETSİZ: gerçek-para bölümleri (ALTIN PAKETLERİ ve
/// PREMIUM ÜYELİK) rafa kaldırıldı — Aşama 3'te geri açılacak (git geçmişine
/// bakınız). Ekranda yalnızca altınla açılan KARAKTERLER listelenir.
class StoreScreen extends ConsumerWidget {
  const StoreScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(storeProvider);
    return Stack(
      children: [
        const Positioned.fill(child: BiladaBackground(showFloaters: false)),
        Column(
          children: [
            BiladaTopBar(coins: state.coins, username: '', avatarSeed: 7),
            Expanded(child: _body(context, ref, state)),
          ],
        ),
      ],
    );
  }

  Widget _body(BuildContext context, WidgetRef ref, StoreState state) {
    if (state.loading && state.characters.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.characters.isEmpty && state.error != null) {
      return _errorView(context, ref, state.error!);
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(storeProvider.notifier).load(),
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── ÖDÜLLÜ REKLAM → ALTIN (ekonominin valfi) ──
            // Web'de google_mobile_ads no-op → kartı hiç gösterme.
            if (!kIsWeb) ...[
              const _WatchAdForGoldButton(),
              const SizedBox(height: 20),
            ],
            // ── KARAKTERLER (mağazanın yıldızı — altınla açılır) ──
            if (state.characters.isNotEmpty) ...[
              _sectionHeader('Karakterler', 'Altınla aç, lobide gösteriş yap'),
              const SizedBox(height: 14),
              _CharacterGrid(characters: state.characters),
            ],
          ],
        ),
      ),
    );
  }

  Widget _sectionHeader(String title, String subtitle) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: BiladaText.headline(size: 24)),
        const SizedBox(height: 2),
        Text(subtitle,
            style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13)),
      ],
    );
  }

  Widget _errorView(BuildContext context, WidgetRef ref, String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_rounded,
                size: 48, color: AppTheme.cOnSurfaceVariant),
            const SizedBox(height: 16),
            Text(message,
                style: BiladaText.body(color: AppTheme.cOnSurfaceVariant),
                textAlign: TextAlign.center),
            const SizedBox(height: 24),
            SizedBox(
              width: 180,
              child: ChunkyButton(
                onPressed: () => ref.read(storeProvider.notifier).load(),
                child: const Text('TEKRAR DENE'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
//  ÖDÜLLÜ REKLAM → ALTIN
// ─────────────────────────────────────────────────────────────────────────

/// "Altının mı az? 📺 Reklam izle → +200 altın" kartı. Ödüllü reklam izlenip
/// ödül hak edilince backend +200 altın ekler; bakiye tazelenir. Web'de hiç
/// gösterilmez (bkz. StoreScreen._body → kIsWeb guard).
///
/// ⚠️ TUTARLILIK SÖZLEŞMESİ: buradaki "+200" metinleri backend
/// PLACEMENTS['gold'] miktarıyla (ads_service.py) BİREBİR aynı olmak zorunda.
class _WatchAdForGoldButton extends ConsumerStatefulWidget {
  const _WatchAdForGoldButton();

  @override
  ConsumerState<_WatchAdForGoldButton> createState() =>
      _WatchAdForGoldButtonState();
}

class _WatchAdForGoldButtonState extends ConsumerState<_WatchAdForGoldButton> {
  bool _busy = false;

  Future<void> _watch() async {
    if (_busy) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final status = await AdService.instance.showRewarded(placement: 'gold');
      if (!mounted) return;
      if (status == AdRewardStatus.earned) {
        // Bakiye tazele (grant başarılıysa backend +200 ekledi): hem global
        // kullanıcıyı hem mağaza bakiyesini (üst bar) yenile.
        await ref.read(authProvider.notifier).refreshUser();
        await ref.read(storeProvider.notifier).load();
        if (!mounted) return;
        // GERÇEĞİ göster: earned, reklamın izlendiğini söyler ama backend
        // grant'i reddetmiş olabilir (ör. günlük cap). lastGrantError doluysa
        // "+eklendi" DEME — kullanıcıya backend'in mesajını göster (eski bug:
        // hata yutulup her izlemede "+altın eklendi!" yazıyordu ama bakiye
        // değişmiyordu).
        final grantError = AdService.instance.lastGrantError;
        if (grantError != null) {
          messenger.showSnackBar(SnackBar(
            content: Text(grantError),
            backgroundColor: AppTheme.cError,
          ));
        } else {
          final coins = AdService.instance.lastGrantedCoins ?? 200;
          messenger.showSnackBar(SnackBar(
              content: Text('+$coins altın hesabına eklendi!')));
        }
      } else if (status == AdRewardStatus.unavailable) {
        messenger.showSnackBar(const SnackBar(
            content: Text('Reklam şu an yok, birazdan tekrar dene.')));
      }
      // dismissed → kullanıcı erken kapattı; sessizce geç.
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
      borderRadius: 20,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const GoldCoin(size: 26),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Altının mı az?', style: BiladaText.title(size: 16)),
                    const SizedBox(height: 2),
                    Text(
                      'Kısa bir reklam izle, anında +200 altın kazan.',
                      style: BiladaText.body(
                          color: AppTheme.cOnSurfaceVariant, size: 12),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: ChunkyButton(
              height: 48,
              color: AppTheme.cTertiary,
              foreground: AppTheme.cOnTertiary,
              shadowColor: AppTheme.cSurfaceContainerLowest,
              onPressed: _busy ? null : _watch,
              child: _busy
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2.5, color: Colors.white),
                    )
                  : const Text('📺 Reklam izle → +200 altın',
                      style: TextStyle(fontSize: 15)),
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
//  NADİRLİK STİLİ
// ─────────────────────────────────────────────────────────────────────────

/// Bir nadirlik seviyesinin görsel kimliği (renk + etiket + prestij).
class _RarityStyle {
  const _RarityStyle(this.color, this.label, {this.glow = false});
  final Color color;
  final String label;

  /// Legendary/epic için ekstra parıltı/altın çerçeve uygulanır mı?
  final bool glow;
}

_RarityStyle _styleFor(CharacterRarity r) {
  switch (r) {
    case CharacterRarity.free:
      return const _RarityStyle(AppTheme.cOnSurfaceVariant, 'Ücretsiz');
    case CharacterRarity.common:
      return const _RarityStyle(AppTheme.cTertiary, 'Sıradan');
    case CharacterRarity.rare:
      return const _RarityStyle(Color(0xFF4FA3FF), 'Nadir');
    case CharacterRarity.epic:
      return const _RarityStyle(AppTheme.cSecondary, 'Epik', glow: true);
    case CharacterRarity.legendary:
      return const _RarityStyle(AppTheme.gold, 'Efsanevi', glow: true);
  }
}

// ─────────────────────────────────────────────────────────────────────────
//  KARAKTER IZGARASI
// ─────────────────────────────────────────────────────────────────────────

class _CharacterGrid extends StatelessWidget {
  const _CharacterGrid({required this.characters});
  final List<StoreCharacter> characters;

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: characters.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 14,
        crossAxisSpacing: 14,
        childAspectRatio: 0.74,
      ),
      itemBuilder: (_, i) => _CharacterCard(character: characters[i]),
    );
  }
}

class _CharacterCard extends ConsumerWidget {
  const _CharacterCard({required this.character});
  final StoreCharacter character;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = character;
    final style = _styleFor(c.rarity);
    final state = ref.watch(storeProvider);
    final buying = state.buyingCharacterId == c.id;
    final equipping = state.equipBusyId == c.id;

    // Çerçeve: kuşanılı → nadirlik rengi (kalın), prestijli (glow) →
    // altın/mor ince çerçeve + parıltı, aksi halde hafif kenar.
    final borderColor = c.equipped
        ? style.color
        : (style.glow
            ? style.color.withValues(alpha: 0.7)
            : Colors.white.withValues(alpha: 0.10));

    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
            color: borderColor, width: c.equipped ? 2.5 : (style.glow ? 1.5 : 1)),
        boxShadow: style.glow
            ? [
                BoxShadow(
                  color: style.color.withValues(alpha: c.equipped ? 0.45 : 0.28),
                  blurRadius: 26,
                  spreadRadius: 1,
                ),
              ]
            : null,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(22),
        child: GlassCard(
          padding: const EdgeInsets.fromLTRB(10, 12, 10, 10),
          borderRadius: 22,
          border: false,
          child: Column(
            children: [
              // Nadirlik rozeti + kuşanılı işareti
              Row(
                children: [
                  _rarityChip(style),
                  const Spacer(),
                  if (c.equipped)
                    Icon(Icons.check_circle_rounded,
                        color: style.color, size: 18),
                ],
              ),
              // 3D karakter görseli (prestijli karakterlerde halkalı sahne)
              Expanded(
                child: Center(
                  child: _CharacterArt(character: c, style: style),
                ),
              ),
              Text(
                c.name,
                style: BiladaText.title(size: 15),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 8),
              _actionButton(context, ref, buying, equipping, style),
            ],
          ),
        ),
      ),
    );
  }

  Widget _rarityChip(_RarityStyle style) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: style.color.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: style.color.withValues(alpha: 0.5)),
      ),
      child: Text(style.label.toUpperCase(),
          style: BiladaText.label(color: style.color, size: 9)),
    );
  }

  /// Durum bazlı buton: sahip değil → fiyat; sahip & kuşanılı değil → "Kuşan";
  /// kuşanılı → "Seçili" rozeti.
  Widget _actionButton(BuildContext context, WidgetRef ref, bool buying,
      bool equipping, _RarityStyle style) {
    final c = character;

    if (c.equipped) {
      return Container(
        height: 38,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: style.color.withValues(alpha: 0.16),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: style.color),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.check_rounded, color: style.color, size: 16),
            const SizedBox(width: 6),
            Text('SEÇİLİ', style: BiladaText.label(color: style.color, size: 12)),
          ],
        ),
      );
    }

    if (c.owned) {
      return ChunkyButton(
        height: 38,
        depth: 3,
        borderRadius: 14,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        color: AppTheme.cSecondaryContainer,
        foreground: Colors.white,
        shadowColor: AppTheme.cSecondaryShadow,
        onPressed: equipping ? null : () => _equip(context, ref),
        child: equipping
            ? const SizedBox(
                width: 16,
                height: 16,
                child:
                    CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
            : const Text('KUŞAN', style: TextStyle(fontSize: 13)),
      );
    }

    // Sahip değil → altın fiyatı.
    return ChunkyButton(
      height: 38,
      depth: 3,
      borderRadius: 14,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      color: AppTheme.gold,
      foreground: AppTheme.cOnPrimaryContainer,
      shadowColor: const Color(0xFF8A6A00),
      onPressed: buying ? null : () => _confirmBuy(context, ref),
      child: buying
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                  strokeWidth: 2, color: Color(0xFF58002F)))
          : Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const GoldCoin(size: 14),
                const SizedBox(width: 5),
                Text('${c.priceCoins}', style: const TextStyle(fontSize: 14)),
              ],
            ),
    );
  }

  Future<void> _equip(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final ok = await ref.read(storeProvider.notifier).equipCharacter(character.id);
    if (!context.mounted) return;
    if (!ok) {
      messenger.showSnackBar(SnackBar(
          content: Text(ref.read(storeProvider).error ?? 'Kuşanma başarısız.')));
    }
  }

  void _confirmBuy(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _BuyCharacterSheet(character: character),
    );
  }
}

/// Karakterin 3D görseli — prestijli (glow) karakterlerde renkli sahne dairesi.
class _CharacterArt extends StatelessWidget {
  const _CharacterArt({required this.character, required this.style});
  final StoreCharacter character;
  final _RarityStyle style;

  @override
  Widget build(BuildContext context) {
    final img = _charImage(character, 78);
    if (!style.glow) return img;
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [
            style.color.withValues(alpha: 0.30),
            style.color.withValues(alpha: 0.0),
          ],
        ),
      ),
      child: img,
    );
  }
}

/// Karakter 3D görselini gösterir (yüklenirken/ hata durumunda nazik yer tutucu).
Widget _charImage(StoreCharacter c, double size) {
  final url = c.imageUrl;
  if (url == null) {
    return Icon(Icons.emoji_emotions_rounded,
        size: size * 0.7, color: Colors.white.withValues(alpha: 0.5));
  }
  return SizedBox(
    width: size,
    height: size,
    child: CachedNetworkImage(
      imageUrl: url,
      fit: BoxFit.contain,
      placeholder: (_, __) => Icon(Icons.image_rounded,
          size: size * 0.55, color: Colors.white.withValues(alpha: 0.3)),
      errorWidget: (_, __, ___) => Icon(Icons.broken_image_rounded,
          size: size * 0.55, color: Colors.white54),
    ),
  );
}

/// Altınla karakter satın alma onay sayfası (yetersizse buton kilitli + uyarı).
class _BuyCharacterSheet extends ConsumerWidget {
  const _BuyCharacterSheet({required this.character});
  final StoreCharacter character;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(storeProvider);
    final c = character;
    final style = _styleFor(c.rarity);
    final coins = state.coins;
    final canAfford = coins >= c.priceCoins;
    final buying = state.buyingCharacterId == c.id;

    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: AppTheme.cSurfaceContainerLow,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      padding: EdgeInsets.fromLTRB(
          24, 16, 24, 24 + MediaQuery.of(context).padding.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                  color: AppTheme.cOutlineVariant,
                  borderRadius: BorderRadius.circular(2))),
          const SizedBox(height: 22),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: style.color.withValues(alpha: 0.14),
              border: Border.all(color: style.color.withValues(alpha: 0.6)),
            ),
            child: _charImage(c, 92),
          ),
          const SizedBox(height: 16),
          Text(c.name, style: BiladaText.headline(size: 24)),
          const SizedBox(height: 6),
          PillBadge(style.label,
              color: style.color, fg: AppTheme.cOnPrimaryContainer),
          const SizedBox(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const GoldCoin(size: 30),
              const SizedBox(width: 8),
              Text('${c.priceCoins}',
                  style: BiladaText.displayXl(color: AppTheme.gold, size: 34)),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            canAfford
                ? 'Bakiyen: $coins altın'
                : 'Yetersiz altın (bakiye: $coins) — Maç kazanarak altın topla!',
            style: BiladaText.body(
                color: canAfford ? AppTheme.cOnSurfaceVariant : AppTheme.cError,
                size: 13),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: ChunkyButton(
              color: AppTheme.gold,
              foreground: AppTheme.cOnPrimaryContainer,
              shadowColor: const Color(0xFF8A6A00),
              onPressed: (!canAfford || buying)
                  ? null
                  : () => _buy(context, ref),
              child: buying
                  ? const SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(
                          strokeWidth: 2.5, color: Color(0xFF58002F)))
                  : Text(canAfford ? 'SATIN AL' : 'YETERSİZ ALTIN'),
            ),
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text('VAZGEÇ',
                style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
          ),
        ],
      ),
    );
  }

  Future<void> _buy(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final ok = await ref.read(storeProvider.notifier).buyCharacter(character.id);
    if (!context.mounted) return;
    navigator.pop();
    messenger.showSnackBar(SnackBar(
      content: Text(ok
          ? '${character.name} alındı! 🎉 Profilinden kuşanabilirsin.'
          : (ref.read(storeProvider).error ?? 'Satın alma başarısız.')),
    ));
  }
}
