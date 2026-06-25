import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/store/providers/store_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// Mağaza ekranı — tek para birimi ALTIN üzerine kurulu.
///
/// Akış (yukarıdan aşağıya):
/// 1. KARAKTERLER  — bireysel, altın fiyatlı, ucuzdan pahalıya, nadirlik kodlu.
/// 2. ALTIN PAKETLERİ — gerçek parayla (gold_*), bonus rozetleri.
/// 3. PREMIUM ÜYELİK  — gerçek parayla (premium_monthly/yearly) + yasal not.
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
    if (state.loading &&
        state.characters.isEmpty &&
        state.products.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.characters.isEmpty &&
        state.products.isEmpty &&
        state.error != null) {
      return _errorView(context, ref, state.error!);
    }

    final goldProducts = state.productsOfType('coins');
    final premiumProducts = state.productsOfType('premium');

    return RefreshIndicator(
      onRefresh: () => ref.read(storeProvider.notifier).load(),
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── 1) KARAKTERLER (mağazanın yıldızı) ──
            if (state.characters.isNotEmpty) ...[
              _sectionHeader('Karakterler', 'Altınla aç, lobide gösteriş yap'),
              const SizedBox(height: 14),
              _CharacterGrid(characters: state.characters),
              const SizedBox(height: 28),
            ],

            // ── 2) ALTIN PAKETLERİ ──
            if (goldProducts.isNotEmpty) ...[
              _sectionHeader('Altın Paketleri', 'Daha fazla karakter aç'),
              const SizedBox(height: 14),
              _GoldGrid(products: goldProducts),
              const SizedBox(height: 28),
            ],

            // ── 3) PREMIUM ÜYELİK ──
            if (premiumProducts.isNotEmpty) ...[
              _sectionHeader('Premium Üyelik', 'Her gün altın + ekstra avantaj'),
              const SizedBox(height: 14),
              _PremiumSection(products: premiumProducts),
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
                const Text('🪙', style: TextStyle(fontSize: 14)),
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
              const Text('🪙', style: TextStyle(fontSize: 28)),
              const SizedBox(width: 8),
              Text('${c.priceCoins}',
                  style: BiladaText.displayXl(color: AppTheme.gold, size: 34)),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            canAfford
                ? 'Bakiyen: $coins altın'
                : 'Yetersiz altın (bakiye: $coins)',
            style: BiladaText.body(
                color: canAfford ? AppTheme.cOnSurfaceVariant : AppTheme.cError,
                size: 13),
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

// ─────────────────────────────────────────────────────────────────────────
//  ALTIN PAKETLERİ
// ─────────────────────────────────────────────────────────────────────────

class _GoldGrid extends StatelessWidget {
  const _GoldGrid({required this.products});
  final List<Map<String, dynamic>> products;

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: products.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 14,
        crossAxisSpacing: 14,
        childAspectRatio: 0.92,
      ),
      itemBuilder: (_, i) => _GoldCard(product: products[i]),
    );
  }
}

class _GoldCard extends ConsumerWidget {
  const _GoldCard({required this.product});
  final Map<String, dynamic> product;

  static String _title(Map<String, dynamic> p) => p['title']?.toString() ?? '';
  static int? _grantCoins(Map<String, dynamic> p) {
    final g = p['grants'];
    if (g is Map && g['coins'] is num) return (g['coins'] as num).toInt();
    return null;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = product;
    final coins = _grantCoins(p);
    final bonus = p['bonus_label']?.toString();
    final store = ref.watch(storeProvider);
    final loading = store.loading;
    final priceStr = store.priceFor(p);

    return GlassCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Text('🪙', style: TextStyle(fontSize: 30)),
              const Spacer(),
              if (bonus != null && bonus.isNotEmpty)
                PillBadge(bonus,
                    color: AppTheme.gold, fg: AppTheme.cOnPrimaryContainer),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            coins != null ? '$coins' : _title(p),
            style: BiladaText.displayXl(color: AppTheme.gold, size: 26),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          Text('altın',
              style:
                  BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13)),
          const Spacer(),
          ChunkyButton(
            height: 42,
            depth: 4,
            borderRadius: 14,
            padding: const EdgeInsets.symmetric(horizontal: 8),
            onPressed:
                loading ? null : () => _confirm(context, ref),
            child: Text(priceStr, style: const TextStyle(fontSize: 14)),
          ),
        ],
      ),
    );
  }

  void _confirm(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ConfirmProductSheet(product: product),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
//  PREMIUM ÜYELİK
// ─────────────────────────────────────────────────────────────────────────

class _PremiumSection extends ConsumerWidget {
  const _PremiumSection({required this.products});
  final List<Map<String, dynamic>> products;

  /// Apple Guideline 3.1.2 — abonelik satın alma noktasında zorunlu açıklama.
  static const String subscriptionDisclosureText =
      'Premium aylık (premium_monthly) ve yıllık (premium_yearly) otomatik '
      'yenilenen aboneliklerdir. Ödeme, satın alma onaylandığında Apple ID '
      'hesabınızdan tahsil edilir. Abonelik, mevcut dönemin bitiminden en az '
      '24 saat önce iptal edilmediği sürece otomatik olarak yenilenir. '
      'Aboneliğinizi App Store hesap ayarlarınızdan yönetebilirsiniz.';

  static const _benefits = [
    'Her gün +100 altın',
    '2x sezon puanı',
    'Özel kozmetikler',
    'Reklamsız deneyim',
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(storeProvider);
    final monthly = products.firstWhere(
        (p) => p['product_id'] == 'premium_monthly',
        orElse: () => const <String, dynamic>{});
    final yearly = products.firstWhere(
        (p) => p['product_id'] == 'premium_yearly',
        orElse: () => const <String, dynamic>{});

    return GlassCard(
      padding: EdgeInsets.zero,
      child: Stack(
        children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    AppTheme.gold.withValues(alpha: 0.40),
                    AppTheme.cSecondaryContainer.withValues(alpha: 0.35),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.workspace_premium_rounded,
                        color: AppTheme.gold, size: 26),
                    const SizedBox(width: 8),
                    Text('Premium', style: BiladaText.title(color: Colors.white)),
                    const Spacer(),
                    if (state.isPremium)
                      const PillBadge('AKTİF',
                          color: AppTheme.cTertiary, fg: AppTheme.cOnTertiary),
                  ],
                ),
                const SizedBox(height: 12),
                for (final t in _benefits)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      children: [
                        const Icon(Icons.check_circle_rounded,
                            color: AppTheme.gold, size: 16),
                        const SizedBox(width: 8),
                        Text(t,
                            style: BiladaText.body(
                                color: AppTheme.cOnSurface, size: 13)),
                      ],
                    ),
                  ),
                const SizedBox(height: 16),
                if (monthly.isNotEmpty && yearly.isNotEmpty)
                  IntrinsicHeight(
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Expanded(child: _planCard(context, ref, monthly, state)),
                        const SizedBox(width: 12),
                        Expanded(
                            child: _planCard(context, ref, yearly, state,
                                badge: 'EN AVANTAJLI')),
                      ],
                    ),
                  )
                else
                  for (final p in products)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: _planCard(context, ref, p, state),
                    ),
                const SizedBox(height: 14),
                Text(subscriptionDisclosureText,
                    style: BiladaText.body(
                        color: AppTheme.cOnSurfaceVariant, size: 11)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 16,
                  runSpacing: 4,
                  children: [
                    _legalLink(context, 'Kullanım Şartları', '/legal/terms'),
                    _legalLink(context, 'Gizlilik Politikası', '/legal/privacy'),
                  ],
                ),
                const SizedBox(height: 12),
                // Aboneliği geri yükle.
                SizedBox(
                  width: double.infinity,
                  child: ChunkyButton(
                    height: 46,
                    depth: 4,
                    color: AppTheme.cSurfaceVariant,
                    foreground: AppTheme.cOnSurface,
                    shadowColor: AppTheme.cOutlineVariant,
                    onPressed:
                        state.loading ? null : () => _restore(context, ref),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.restore_rounded, size: 18),
                        SizedBox(width: 8),
                        Text('SATIN ALIMLARI GERİ YÜKLE',
                            style: TextStyle(fontSize: 13)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _planCard(BuildContext context, WidgetRef ref,
      Map<String, dynamic> p, StoreState state,
      {String? badge}) {
    final owned = state.isPremium || (p['owned'] == true);
    final title = p['title']?.toString() ?? '';
    final price = state.priceFor(p);
    return GlassCard(
      padding: const EdgeInsets.all(14),
      color: AppTheme.cSurfaceContainerHigh.withValues(alpha: 0.55),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (badge != null) ...[
                PillBadge(badge,
                    color: AppTheme.gold, fg: AppTheme.cOnPrimaryContainer),
                const SizedBox(height: 8),
              ],
              Text(title, style: BiladaText.title(size: 15)),
              const SizedBox(height: 4),
              Text(price,
                  style: BiladaText.displayXl(color: AppTheme.gold, size: 20)),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ChunkyButton(
              height: 42,
              depth: 4,
              borderRadius: 14,
              padding: const EdgeInsets.symmetric(horizontal: 8),
              onPressed: owned || state.loading
                  ? null
                  : () => _confirm(context, ref, p),
              child: Text(owned ? 'AKTİF' : 'ABONE OL',
                  style: const TextStyle(fontSize: 14)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _legalLink(BuildContext context, String label, String route) {
    return GestureDetector(
      onTap: () => context.push(route),
      child: Text(
        label,
        style: BiladaText.label(color: AppTheme.cPrimary, size: 11).copyWith(
          decoration: TextDecoration.underline,
          decorationColor: AppTheme.cPrimary,
        ),
      ),
    );
  }

  void _confirm(BuildContext context, WidgetRef ref, Map<String, dynamic> p) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ConfirmProductSheet(product: p),
    );
  }

  Future<void> _restore(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final ok = await ref.read(storeProvider.notifier).restore();
    if (!context.mounted) return;
    messenger.showSnackBar(SnackBar(
      content: Text(ok
          ? 'Satın alımların geri yüklendi.'
          : 'Geri yüklenecek satın alım bulunamadı.'),
    ));
  }
}

// ─────────────────────────────────────────────────────────────────────────
//  GERÇEK-PARA ÜRÜN ONAY SAYFASI (altın paketi / premium)
// ─────────────────────────────────────────────────────────────────────────

class _ConfirmProductSheet extends ConsumerStatefulWidget {
  const _ConfirmProductSheet({required this.product});
  final Map<String, dynamic> product;

  @override
  ConsumerState<_ConfirmProductSheet> createState() =>
      _ConfirmProductSheetState();
}

class _ConfirmProductSheetState extends ConsumerState<_ConfirmProductSheet> {
  bool _busy = false;

  Future<void> _run() async {
    setState(() => _busy = true);
    final notifier = ref.read(storeProvider.notifier);
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final ok = await notifier.buyProduct(widget.product);
    if (!mounted) return;
    setState(() => _busy = false);
    navigator.pop();
    messenger.showSnackBar(SnackBar(
      content: Text(ok
          ? 'Satın alma tamamlandı! 🎉'
          : (ref.read(storeProvider).error ?? 'Satın alma başarısız.')),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.product;
    final title = p['title']?.toString() ?? '';
    final desc = p['description']?.toString() ?? '';
    final price = ref.watch(storeProvider).priceFor(p);
    final productId = p['product_id']?.toString() ?? '';
    final isSubscription = productId.startsWith('premium_');

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
          Text(title,
              style: BiladaText.headline(size: 22), textAlign: TextAlign.center),
          if (desc.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(desc,
                style: BiladaText.body(color: AppTheme.cOnSurfaceVariant),
                textAlign: TextAlign.center),
          ],
          const SizedBox(height: 18),
          Text(price,
              style: BiladaText.displayXl(color: AppTheme.gold, size: 34)),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: ChunkyButton(
              onPressed: _busy ? null : _run,
              child: _busy
                  ? const SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(strokeWidth: 2.5))
                  : const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.shopping_cart_rounded),
                        SizedBox(width: 8),
                        Text('SATIN AL'),
                      ],
                    ),
            ),
          ),
          if (isSubscription) ...[
            const SizedBox(height: 16),
            Text(
              _PremiumSection.subscriptionDisclosureText,
              style:
                  BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 11),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _legal(context, 'Kullanım Şartları', '/legal/terms'),
                const SizedBox(width: 16),
                _legal(context, 'Gizlilik Politikası', '/legal/privacy'),
              ],
            ),
          ],
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

  Widget _legal(BuildContext context, String label, String route) {
    return GestureDetector(
      onTap: () => context.push(route),
      child: Text(label,
          style: BiladaText.label(color: AppTheme.cPrimary, size: 11).copyWith(
            decoration: TextDecoration.underline,
            decorationColor: AppTheme.cPrimary,
          )),
    );
  }
}
