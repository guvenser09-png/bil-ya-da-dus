import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/cosmetics/providers/cosmetics_provider.dart';
import 'package:quizroyale/features/inventory/providers/inventory_provider.dart';
import 'package:quizroyale/shared/characters.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/player_avatar.dart';

/// "Envanterim" — sahip olunan HER ŞEY tek ekranda:
/// bakiye (altın/premium), karakterler ve kozmetikler.
class InventoryScreen extends ConsumerWidget {
  const InventoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(inventoryProvider);

    // Kuşanma vb. hataları snackbar ile bildir.
    ref.listen(inventoryProvider, (prev, next) {
      if (next.error != null && next.error != prev?.error && next.loaded) {
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
                Expanded(
                  child: !state.loaded
                      ? const Center(
                          child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer),
                        )
                      : RefreshIndicator(
                          color: AppTheme.cPrimaryContainer,
                          backgroundColor: AppTheme.cSurfaceContainer,
                          onRefresh: () => ref.read(inventoryProvider.notifier).load(),
                          child: _body(context, ref, state),
                        ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _header(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 8, 20, 8),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_rounded, color: AppTheme.cOnSurface),
            onPressed: () => context.pop(),
          ),
          Text('Envanterim', style: BiladaText.headline(size: 24)),
        ],
      ),
    );
  }

  Widget _body(BuildContext context, WidgetRef ref, InventoryState state) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
      children: [
        if (state.error != null) ...[
          GlassCard(
            color: AppTheme.cErrorContainer.withValues(alpha: 0.4),
            child: Row(
              children: [
                const Icon(Icons.error_outline_rounded, color: AppTheme.cError, size: 20),
                const SizedBox(width: 10),
                Expanded(child: Text(state.error!, style: BiladaText.body(size: 14))),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
        _balanceSection(state),
        const SizedBox(height: 28),
        _charactersSection(context, ref, state),
        const SizedBox(height: 28),
        _cosmeticsSection(context, state),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // BAKİYE
  // ---------------------------------------------------------------------------
  Widget _balanceSection(InventoryState state) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('BAKİYE', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
        const SizedBox(height: 12),
        _balanceTile('🪙', _fmt(state.coins), 'Altın', AppTheme.gold),
        // İLK LANSMAN: premium üyelik kutusu gizlendi (satış yok) — Aşama 3'te
        // git geçmişindeki _premiumTile ile geri açılacak.
      ],
    );
  }

  Widget _balanceTile(String emoji, String value, String label, Color accent) {
    return GlassCard(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Text(emoji, style: const TextStyle(fontSize: 26)),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(value, style: BiladaText.title(color: accent, size: 18)),
              Text(label, style: BiladaText.label(color: AppTheme.cOutline, size: 11)),
            ],
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // KARAKTERLER
  // ---------------------------------------------------------------------------
  Widget _charactersSection(BuildContext context, WidgetRef ref, InventoryState state) {
    final chars = state.ownedCharacters;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('KARAKTERLERİM', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
            Text('${chars.length} karakter',
                style: BiladaText.label(color: AppTheme.cOutline, size: 11)),
          ],
        ),
        const SizedBox(height: 12),
        if (chars.isEmpty)
          _emptyState('Henüz karakterin yok', 'Mağaza\'dan yeni karakterler al.')
        else ...[
          Text('Kuşanmak için dokun',
              style: BiladaText.label(color: AppTheme.cOutline, size: 11)),
          const SizedBox(height: 10),
          GlassCard(
            padding: const EdgeInsets.all(16),
            child: Wrap(
              spacing: 16,
              runSpacing: 16,
              children: chars
                  .map((c) => _characterTile(
                        context,
                        ref,
                        c,
                        equipped: c.id == state.equippedCharacterId,
                        busy: c.id == state.busyCharacterId,
                      ))
                  .toList(),
            ),
          ),
        ],
      ],
    );
  }

  Widget _characterTile(
    BuildContext context,
    WidgetRef ref,
    BiladaCharacter c, {
    required bool equipped,
    required bool busy,
  }) {
    return GestureDetector(
      onTap: equipped || busy
          ? null
          : () => ref.read(inventoryProvider.notifier).equipCharacter(c.id),
      child: SizedBox(
        width: 72,
        child: Column(
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                Container(
                  padding: const EdgeInsets.all(2),
                  decoration: equipped
                      ? BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(color: AppTheme.cTertiary, width: 2.5),
                        )
                      : null,
                  child: PlayerAvatar(avatarId: c.id, username: c.name, size: 56),
                ),
                if (busy)
                  Positioned.fill(
                    child: Container(
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.black.withValues(alpha: 0.45),
                      ),
                      child: const Center(
                        child: SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        ),
                      ),
                    ),
                  ),
                if (equipped && !busy)
                  Positioned(
                    bottom: -2,
                    right: -2,
                    child: Container(
                      width: 18,
                      height: 18,
                      decoration: BoxDecoration(
                        color: AppTheme.cTertiary,
                        shape: BoxShape.circle,
                        border: Border.all(color: AppTheme.cSurfaceContainerHigh, width: 2),
                      ),
                      child: const Icon(Icons.check, size: 10, color: AppTheme.cOnTertiary),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              c.name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: BiladaText.label(
                color: equipped ? AppTheme.cTertiary : AppTheme.cOnSurfaceVariant,
                size: 10,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // KOZMETİKLER
  // ---------------------------------------------------------------------------
  Widget _cosmeticsSection(BuildContext context, InventoryState state) {
    const slots = [
      ('frame', 'Çerçeveler'),
      ('name_color', 'İsim Renkleri'),
      ('effect', 'Efektler'),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('KOZMETİKLERİM', style: BiladaText.label(color: AppTheme.cOnSurfaceVariant)),
            GestureDetector(
              onTap: () => context.push('/cosmetics'),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('Değiştir',
                      style: BiladaText.label(color: AppTheme.cTertiary, size: 12)),
                  const Icon(Icons.chevron_right_rounded, color: AppTheme.cTertiary, size: 18),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (state.hasNoCosmetics)
          _emptyState('Henüz kozmetiğin yok', 'Mağaza\'dan çerçeve, renk ve efekt al.')
        else
          ...slots.map((s) {
            final items = state.ownedOfSlot(s.$1);
            if (items.isEmpty) return const SizedBox.shrink();
            return Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: _cosmeticSlotCard(s.$2, s.$1, items, state),
            );
          }),
      ],
    );
  }

  Widget _cosmeticSlotCard(
      String title, String slot, List<Cosmetic> items, InventoryState state) {
    final equippedId = state.equippedIdForSlot(slot);
    return GlassCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: BiladaText.title(size: 15)),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: items
                .map((c) => _cosmeticChip(c, equipped: c.id == equippedId))
                .toList(),
          ),
        ],
      ),
    );
  }

  Widget _cosmeticChip(Cosmetic c, {required bool equipped}) {
    final color = c.color;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: equipped
            ? AppTheme.cTertiaryContainer.withValues(alpha: 0.35)
            : AppTheme.cSurfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: equipped ? AppTheme.cTertiary : AppTheme.cOutlineVariant,
          width: equipped ? 1.5 : 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (color != null) ...[
            Container(
              width: 14,
              height: 14,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
            const SizedBox(width: 8),
          ],
          Text(c.name, style: BiladaText.body(size: 13)),
          if (equipped) ...[
            const SizedBox(width: 6),
            const Icon(Icons.check_circle_rounded, color: AppTheme.cTertiary, size: 16),
          ],
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // YARDIMCILAR
  // ---------------------------------------------------------------------------
  Widget _emptyState(String title, String subtitle) {
    return GlassCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          const Icon(Icons.inventory_2_outlined, color: AppTheme.cOutline, size: 32),
          const SizedBox(height: 10),
          Text(title, style: BiladaText.title(size: 15), textAlign: TextAlign.center),
          const SizedBox(height: 4),
          Text(subtitle,
              style: BiladaText.label(color: AppTheme.cOutline, size: 11),
              textAlign: TextAlign.center),
        ],
      ),
    );
  }

  static String _fmt(int n) {
    final s = n.toString();
    final buf = StringBuffer();
    for (int i = 0; i < s.length; i++) {
      if (i > 0 && (s.length - i) % 3 == 0) buf.write(',');
      buf.write(s[i]);
    }
    return buf.toString();
  }

}
