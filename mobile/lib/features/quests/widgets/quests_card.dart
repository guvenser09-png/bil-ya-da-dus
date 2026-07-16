import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:quizroyale/core/services/haptic_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/features/auth/providers/auth_provider.dart';
import 'package:quizroyale/features/quests/providers/quests_provider.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';
import 'package:quizroyale/shared/widgets/gold_coin.dart';

/// Ana ekrandaki kompakt "GÜNLÜK GÖREVLER" kartı.
///
/// Üç görev tek bakışta: emoji + başlık + ince ilerleme çubuğu. Tamamlanan
/// görevde "AL" butonu belirir (dokun → altın). Karta dokununca detay sheet
/// açılır. Kart HIZLI MAÇ'ı gölgelemesin diye satırlar sıkı ve sessizdir.
class QuestsCard extends ConsumerWidget {
  const QuestsCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(questsProvider);
    if (!state.loaded || state.quests.isEmpty) return const SizedBox.shrink();

    return GlassCard(
      onTap: () => showQuestsSheet(context),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Column(
        children: [
          Row(
            children: [
              const Text('📋', style: TextStyle(fontSize: 18)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'GÜNLÜK GÖREVLER',
                  style: BiladaText.label(color: AppTheme.cSecondary, size: 12),
                ),
              ),
              if (state.claimableCount > 0)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    gradient: AppTheme.goldGradient,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    '${state.claimableCount} ÖDÜL HAZIR',
                    style: BiladaText.label(color: const Color(0xFF58002F), size: 10),
                  ),
                )
              else
                Text(
                  '${state.completedCount}/${state.quests.length}',
                  style: BiladaText.label(size: 11),
                ),
            ],
          ),
          const SizedBox(height: 8),
          for (final quest in state.quests)
            QuestRow(
              quest: quest,
              dense: true,
              claiming: state.claimingId == quest.id,
              onClaim: () => claimQuest(context, ref, quest),
            ),
        ],
      ),
    );
  }
}

/// Görev satırı — kartta (dense) ve detay sheet'inde (geniş) aynı widget.
class QuestRow extends StatelessWidget {
  const QuestRow({
    super.key,
    required this.quest,
    required this.onClaim,
    this.claiming = false,
    this.dense = false,
  });

  final Quest quest;
  final VoidCallback onClaim;
  final bool claiming;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final done = quest.completed;
    return Padding(
      padding: EdgeInsets.symmetric(vertical: dense ? 5 : 9),
      child: Row(
        children: [
          Opacity(
            opacity: quest.claimed ? 0.45 : 1,
            child: Text(quest.emoji, style: TextStyle(fontSize: dense ? 16 : 20)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        quest.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: BiladaText.body(
                          size: dense ? 13 : 15,
                          color: quest.claimed
                              ? AppTheme.cOnSurfaceVariant
                              : AppTheme.cOnSurface,
                        ),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      quest.target > 1 ? '${quest.progress}/${quest.target}' : '',
                      style: BiladaText.label(size: 10),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(999),
                  child: LinearProgressIndicator(
                    value: quest.ratio,
                    minHeight: dense ? 4 : 6,
                    backgroundColor: AppTheme.cSurfaceContainerHighest,
                    valueColor: AlwaysStoppedAnimation(
                      done ? AppTheme.cTertiary : AppTheme.cSecondaryContainer,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(width: dense ? 72 : 84, child: _trailing()),
        ],
      ),
    );
  }

  Widget _trailing() {
    if (quest.claimed) {
      return Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          const Icon(Icons.check_circle_rounded, size: 16, color: AppTheme.cTertiary),
          const SizedBox(width: 4),
          Text('ALINDI', style: BiladaText.label(size: 10)),
        ],
      );
    }
    if (quest.claimable) {
      return GestureDetector(
        onTap: claiming ? null : onClaim,
        child: Container(
          height: dense ? 26 : 32,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            gradient: AppTheme.goldGradient,
            borderRadius: BorderRadius.circular(999),
            boxShadow: [
              BoxShadow(
                color: AppTheme.gold.withValues(alpha: 0.35),
                blurRadius: 10,
                offset: const Offset(0, 3),
              ),
            ],
          ),
          child: claiming
              ? const SizedBox(
                  width: 12,
                  height: 12,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF58002F)),
                )
              : Text(
                  'AL +${quest.reward}',
                  style: BiladaText.label(color: const Color(0xFF58002F), size: 10),
                ),
        ),
      );
    }
    // Henüz tamamlanmadı → ödülü hatırlat (motivasyon).
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Text('+${quest.reward}', style: BiladaText.label(size: 11)),
        const SizedBox(width: 3),
        const GoldCoin(size: 12),
      ],
    );
  }
}

/// Görev ödülünü alır ve kullanıcıyı bilgilendirir (altın bakiyesini tazeler).
Future<void> claimQuest(BuildContext context, WidgetRef ref, Quest quest) async {
  HapticService().buttonTap();
  final reward = await ref.read(questsProvider.notifier).claim(quest.id);
  if (!context.mounted) return;
  if (reward > 0) {
    // Bakiye tek gerçek kaynaktan tazelensin (üst bardaki CoinPill).
    await ref.read(authProvider.notifier).refreshUser();
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('${quest.title} tamam! +$reward altın')),
    );
  }
}

/// Görev detayları — ana ekrandaki karta dokununca açılır.
Future<void> showQuestsSheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: true,
    builder: (_) => const _QuestsSheet(),
  );
}

class _QuestsSheet extends ConsumerWidget {
  const _QuestsSheet();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(questsProvider);
    return Container(
      padding: EdgeInsets.fromLTRB(20, 12, 20, 24 + MediaQuery.of(context).padding.bottom),
      decoration: const BoxDecoration(
        color: AppTheme.cSurfaceContainerHigh,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 44,
            height: 4,
            decoration: BoxDecoration(
              color: AppTheme.cOutlineVariant,
              borderRadius: BorderRadius.circular(999),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              const Text('📋', style: TextStyle(fontSize: 22)),
              const SizedBox(width: 10),
              Expanded(child: Text('Günlük Görevler', style: BiladaText.headline(size: 22))),
            ],
          ),
          const SizedBox(height: 4),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Her gün gece yarısı yenilenir. Tamamla, altını al.',
              style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 13),
            ),
          ),
          const SizedBox(height: 8),
          for (final quest in state.quests)
            QuestRow(
              quest: quest,
              claiming: state.claimingId == quest.id,
              onClaim: () => claimQuest(context, ref, quest),
            ),
          const SizedBox(height: 12),
        ],
      ),
    );
  }
}
