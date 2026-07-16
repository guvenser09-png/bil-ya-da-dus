import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/cosmetics/providers/cosmetics_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/gold_coin.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

/// Kozmetik mağazası: çerçeveler / isim rengi / efektler. Coin ile alınır.
class CosmeticsScreen extends ConsumerStatefulWidget {
  const CosmeticsScreen({super.key});

  @override
  ConsumerState<CosmeticsScreen> createState() => _CosmeticsScreenState();
}

class _CosmeticsScreenState extends ConsumerState<CosmeticsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tab = TabController(length: 3, vsync: this);

  static const _slots = ['frame', 'name_color', 'effect'];

  @override
  void initState() {
    super.initState();
    _tab.addListener(() => setState(() {})); // canlı önizleme sekme rengini takip etsin
  }

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(cosmeticsProvider);
    final user = ref.watch(authProvider).user;
    final avatarId = user?['avatar_id'] as String? ?? 'default_01';
    final username = (user?['username'] ?? 'Oyuncu').toString();

    // Hata varsa snackbar göster (yetersiz coin vb.).
    ref.listen(cosmeticsProvider, (prev, next) {
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
                _header(state.coins),
                _preview(state, avatarId, username),
                const SizedBox(height: 12),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: TabBar(
                    controller: _tab,
                    tabs: const [
                      Tab(text: 'ÇERÇEVE'),
                      Tab(text: 'İSİM RENGİ'),
                      Tab(text: 'EFEKT'),
                    ],
                  ),
                ),
                const SizedBox(height: 8),
                Expanded(
                  child: state.loading && !state.loaded
                      ? const Center(child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer))
                      : TabBarView(
                          controller: _tab,
                          children: [
                            for (final slot in _slots) _slotContent(state, slot),
                          ],
                        ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _header(int coins) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 4, 20, 8),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_rounded, color: AppTheme.cOnSurface),
            onPressed: () => context.pop(),
          ),
          Text('Kozmetikler', style: BiladaText.headline(size: 22)),
          const Spacer(),
          CoinPill(coins: coins),
        ],
      ),
    );
  }

  /// Canlı önizleme: kullanıcı avatarını kuşanılmış çerçeve/isim rengi/efektle
  /// gösterir (Görünümüm).
  Widget _preview(CosmeticsState state, String avatarId, String username) {
    final frameId = state.equippedFrame;
    final nameColor = parseHexColor(state.byId(state.equippedNameColor)?.colorHex);
    final effect = state.byId(state.equippedEffect);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: GlassCard(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            PlayerAvatar(
              avatarId: avatarId,
              username: username,
              size: 88,
              frame: frameKeyFromId(frameId),
            ),
            const SizedBox(height: 10),
            Text(
              username,
              style: BiladaText.title(color: nameColor ?? AppTheme.cOnSurface, size: 20),
            ),
            if (effect != null) ...[
              const SizedBox(height: 8),
              PillBadge('✨ ${effect.name}',
                  color: AppTheme.cTertiaryContainer, fg: Colors.white),
            ],
            const SizedBox(height: 6),
            Text('Görünümüm', style: BiladaText.label(color: AppTheme.cOutline, size: 10)),
          ],
        ),
      ),
    );
  }

  /// Bir slotun içeriği: önce "Sahip olduklarım" (dolap), sonra "Mağaza".
  Widget _slotContent(CosmeticsState state, String slot) {
    final owned = state.ownedOfSlot(slot);
    final shop = state.shopOfSlot(slot);
    final emptyOwnedText = switch (slot) {
      'frame' => 'Henüz çerçeven yok, mağazadan al.',
      'name_color' => 'Henüz isim rengin yok, mağazadan al.',
      _ => 'Henüz efektin yok, mağazadan al.',
    };

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 40),
      children: [
        _sectionLabel('SAHİP OLDUKLARIM'),
        const SizedBox(height: 10),
        if (owned.isEmpty)
          _emptyState(emptyOwnedText)
        else
          _grid(owned),
        const SizedBox(height: 24),
        _sectionLabel('MAĞAZA'),
        const SizedBox(height: 10),
        if (shop.isEmpty)
          _emptyState('Bu kategoride satılık başka bir şey kalmadı. 🎉')
        else
          _grid(shop),
      ],
    );
  }

  Widget _sectionLabel(String text) =>
      Text(text, style: BiladaText.label(color: AppTheme.cOnSurfaceVariant, size: 12));

  Widget _emptyState(String text) => GlassCard(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
        child: Row(
          children: [
            const Text('🛍️', style: TextStyle(fontSize: 20)),
            const SizedBox(width: 12),
            Expanded(
              child: Text(text, style: BiladaText.body(color: AppTheme.cOutline, size: 13)),
            ),
          ],
        ),
      );

  Widget _grid(List<Cosmetic> items) => GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 14,
          crossAxisSpacing: 14,
          childAspectRatio: 0.78,
        ),
        itemCount: items.length,
        itemBuilder: (_, i) => _CosmeticCard(cosmetic: items[i]),
      );
}

class _CosmeticCard extends ConsumerWidget {
  const _CosmeticCard({required this.cosmetic});
  final Cosmetic cosmetic;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(cosmeticsProvider);
    final notifier = ref.read(cosmeticsProvider.notifier);
    final equipped = state.equippedIdForSlot(cosmetic.slot) == cosmetic.id;
    final busy = state.busyId == cosmetic.id;
    final canAfford = state.coins >= cosmetic.priceCoins;

    return GlassCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          Expanded(child: Center(child: _previewFor(cosmetic))),
          const SizedBox(height: 8),
          Text(
            cosmetic.name,
            style: BiladaText.title(size: 14),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 8),
          _actionButton(context, ref, notifier, equipped, busy, canAfford),
        ],
      ),
    );
  }

  /// Slot tipine göre önizleme: çerçeve halkası / renkli daire / efekt rozeti.
  Widget _previewFor(Cosmetic c) {
    switch (c.slot) {
      case 'frame':
        return PlayerAvatar(
          avatarId: 'default_01',
          username: 'Aa',
          size: 64,
          frame: frameKeyFromId(c.id),
        );
      case 'name_color':
        final color = c.color ?? AppTheme.cPrimary;
        return Text('Aa', style: BiladaText.displayXl(color: color, size: 40));
      case 'effect':
      default:
        return Container(
          width: 64,
          height: 64,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            gradient: AppTheme.primaryGradient,
          ),
          alignment: Alignment.center,
          child: const Text('✨', style: TextStyle(fontSize: 30)),
        );
    }
  }

  Widget _actionButton(
    BuildContext context,
    WidgetRef ref,
    CosmeticsNotifier notifier,
    bool equipped,
    bool busy,
    bool canAfford,
  ) {
    if (busy) {
      return const ChunkyButton(
        height: 40,
        depth: 4,
        onPressed: null,
        child: SizedBox(
          width: 18,
          height: 18,
          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
        ),
      );
    }

    // Sahip değil → SATIN AL.
    if (!cosmetic.owned) {
      return ChunkyButton(
        height: 40,
        depth: 4,
        color: canAfford ? AppTheme.cPrimaryContainer : AppTheme.cSurfaceContainerHighest,
        onPressed: () async {
          if (!canAfford) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Yeterli altın yok.')),
            );
            return;
          }
          await notifier.buy(cosmetic.id);
        },
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('${cosmetic.priceCoins}', style: const TextStyle(fontSize: 14)),
            const SizedBox(width: 4),
            const GoldCoin(size: 13),
          ],
        ),
      );
    }

    // Sahip + kuşanılmış → tek dokunuşla ÇIKAR (unequip).
    if (equipped) {
      return ChunkyButton(
        height: 40,
        depth: 4,
        color: AppTheme.cTertiaryContainer,
        foreground: Colors.white,
        shadowColor: AppTheme.cTertiaryShadow,
        onPressed: () => notifier.equip(cosmetic.slot, null),
        child: const Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.check_circle_rounded, size: 14),
            SizedBox(width: 4),
            Text('ÇIKAR', style: TextStyle(fontSize: 13)),
          ],
        ),
      );
    }

    // Sahip + kuşanılmamış → KUŞAN.
    return ChunkyButton(
      height: 40,
      depth: 4,
      color: AppTheme.cSecondaryContainer,
      foreground: Colors.white,
      shadowColor: AppTheme.cSecondaryShadow,
      onPressed: () => notifier.equip(cosmetic.slot, cosmetic.id),
      child: const Text('KUŞAN', style: TextStyle(fontSize: 14)),
    );
  }
}
