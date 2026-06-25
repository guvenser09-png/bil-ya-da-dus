import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

Future<void> showQrShareSheet(BuildContext context, {required String lobbyCode, required String lobbyUrl}) {
  return showModalBottomSheet(
    context: context,
    backgroundColor: Colors.transparent,
    builder: (_) => _QrShareSheet(lobbyCode: lobbyCode, lobbyUrl: lobbyUrl),
  );
}

class _QrShareSheet extends StatelessWidget {
  const _QrShareSheet({required this.lobbyCode, required this.lobbyUrl});
  final String lobbyCode;
  final String lobbyUrl;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppTheme.cSurfaceContainerLow,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      padding: EdgeInsets.fromLTRB(24, 12, 24, 24 + MediaQuery.of(context).padding.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 40,
            height: 4,
            margin: const EdgeInsets.only(bottom: 20),
            decoration: BoxDecoration(color: AppTheme.cOutlineVariant, borderRadius: BorderRadius.circular(2)),
          ),
          Text('LOBİYE DAVET ET', style: BiladaText.label(color: AppTheme.cPrimary)),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(20)),
            child: QrImageView(data: lobbyUrl, version: QrVersions.auto, size: 200),
          ),
          const SizedBox(height: 20),
          Text('Lobi Kodu', style: BiladaText.label(color: AppTheme.cOutline, size: 12)),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: () {
              Clipboard.setData(ClipboardData(text: lobbyCode));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Kod kopyalandı!'), duration: Duration(seconds: 2)),
              );
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              decoration: BoxDecoration(
                color: AppTheme.cSurfaceContainerHigh,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.cPrimaryContainer.withValues(alpha: 0.5)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(lobbyCode, style: BiladaText.displayXl(color: AppTheme.cPrimary, size: 28).copyWith(letterSpacing: 6)),
                  const SizedBox(width: 12),
                  const Icon(Icons.copy_outlined, size: 18, color: AppTheme.cPrimary),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          ChunkyButton(
            height: 56,
            onPressed: () {
              Clipboard.setData(ClipboardData(text: lobbyUrl));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("Link kopyalandı! WhatsApp'a yapıştır."), duration: Duration(seconds: 2)),
              );
            },
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [Icon(Icons.share_rounded, size: 18), SizedBox(width: 8), Text('LİNKİ KOPYALA')],
            ),
          ),
        ],
      ),
    );
  }
}
