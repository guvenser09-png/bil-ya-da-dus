import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:go_router/go_router.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// Bir markdown asset dosyasını (gizlilik politikası / kullanım şartları gibi)
/// uygulamanın teması ile uyumlu biçimde gösteren ekran.
///
/// Yeni paket bağımlılığı eklememek için markdown, rootBundle ile okunup
/// sade bir biçimde (başlık, paragraf, madde, alıntı, kalın metin) render edilir.
class LegalViewerScreen extends StatelessWidget {
  const LegalViewerScreen({
    super.key,
    required this.assetPath,
    required this.title,
  });

  /// Gösterilecek markdown dosyasının asset yolu.
  /// Örn: 'assets/legal/privacy_policy.md'
  final String assetPath;

  /// Üst başlıkta gösterilecek metin. Örn: 'Gizlilik Politikası'
  final String title;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: BiladaBackground(showFloaters: false)),
          SafeArea(
            child: Column(
              children: [
                // Üst başlık çubuğu
                Padding(
                  padding: const EdgeInsets.fromLTRB(8, 8, 20, 8),
                  child: Row(
                    children: [
                      IconButton(
                        icon: const Icon(Icons.arrow_back_rounded, color: AppTheme.cOnSurface),
                        onPressed: () => context.pop(),
                      ),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          title,
                          style: BiladaText.headline(size: 22),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: FutureBuilder<String>(
                    future: rootBundle.loadString(assetPath),
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) {
                        return const Center(
                          child: CircularProgressIndicator(color: AppTheme.cPrimaryContainer),
                        );
                      }
                      if (snapshot.hasError || !snapshot.hasData) {
                        return Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24),
                            child: Text(
                              'Belge yüklenemedi. Lütfen daha sonra tekrar deneyin.',
                              style: BiladaText.body(color: AppTheme.cOnSurfaceVariant),
                              textAlign: TextAlign.center,
                            ),
                          ),
                        );
                      }
                      return SingleChildScrollView(
                        padding: const EdgeInsets.fromLTRB(20, 4, 20, 40),
                        child: GlassCard(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: _MarkdownRenderer.render(snapshot.data!),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Çok sade bir markdown -> widget dönüştürücü.
/// Desteklenenler: # / ## / ### başlıklar, > alıntı/not, - veya * madde,
/// **kalın** metin (satır içi), boş satır = paragraf ayracı.
class _MarkdownRenderer {
  const _MarkdownRenderer._();

  static List<Widget> render(String source) {
    final widgets = <Widget>[];
    // CRLF normalize et.
    final lines = source.replaceAll('\r\n', '\n').split('\n');

    // Çok satırlı alıntı (>) bloklarını tek karta toplamak için tampon.
    final quoteBuffer = <String>[];

    void flushQuote() {
      if (quoteBuffer.isEmpty) return;
      widgets.add(_quoteBlock(quoteBuffer.join(' ')));
      widgets.add(const SizedBox(height: 14));
      quoteBuffer.clear();
    }

    for (final raw in lines) {
      final line = raw.trimRight();
      final trimmed = line.trim();

      if (trimmed.startsWith('>')) {
        quoteBuffer.add(trimmed.replaceFirst(RegExp(r'^>\s?'), ''));
        continue;
      }
      flushQuote();

      if (trimmed.isEmpty) {
        widgets.add(const SizedBox(height: 10));
        continue;
      }

      if (trimmed.startsWith('### ')) {
        widgets.add(_heading(trimmed.substring(4), 16));
      } else if (trimmed.startsWith('## ')) {
        widgets.add(_heading(trimmed.substring(3), 20));
      } else if (trimmed.startsWith('# ')) {
        widgets.add(_heading(trimmed.substring(2), 26));
      } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        widgets.add(_bullet(trimmed.substring(2)));
      } else {
        widgets.add(_paragraph(trimmed));
      }
    }
    flushQuote();
    return widgets;
  }

  static Widget _heading(String text, double size) {
    return Padding(
      padding: const EdgeInsets.only(top: 14, bottom: 6),
      child: Text(text, style: BiladaText.title(size: size, color: AppTheme.cPrimary)),
    );
  }

  static Widget _paragraph(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Text.rich(
        _inline(text, AppTheme.cOnSurfaceVariant),
        style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14),
      ),
    );
  }

  static Widget _bullet(String text) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 6, right: 8),
            child: Container(
              width: 6,
              height: 6,
              decoration: const BoxDecoration(
                color: AppTheme.cPrimary,
                shape: BoxShape.circle,
              ),
            ),
          ),
          Expanded(
            child: Text.rich(
              _inline(text, AppTheme.cOnSurfaceVariant),
              style: BiladaText.body(color: AppTheme.cOnSurfaceVariant, size: 14),
            ),
          ),
        ],
      ),
    );
  }

  static Widget _quoteBlock(String text) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cSurfaceContainerHighest.withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(12),
        border: const Border(
          left: BorderSide(color: AppTheme.gold, width: 4),
        ),
      ),
      child: Text.rich(
        _inline(text, AppTheme.cOnSurface),
        style: BiladaText.body(color: AppTheme.cOnSurface, size: 13),
      ),
    );
  }

  /// **kalın** metni ayrıştıran sade satır içi çözümleyici.
  static InlineSpan _inline(String text, Color color) {
    final spans = <TextSpan>[];
    final regex = RegExp(r'\*\*(.+?)\*\*');
    int last = 0;
    for (final m in regex.allMatches(text)) {
      if (m.start > last) {
        spans.add(TextSpan(text: text.substring(last, m.start)));
      }
      spans.add(TextSpan(
        text: m.group(1),
        style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.cOnSurface),
      ));
      last = m.end;
    }
    if (last < text.length) {
      spans.add(TextSpan(text: text.substring(last)));
    }
    return TextSpan(style: TextStyle(color: color), children: spans);
  }
}
