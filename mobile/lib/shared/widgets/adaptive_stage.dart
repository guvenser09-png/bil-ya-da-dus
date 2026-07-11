import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:quizroyale/shared/widgets/bilada_ui.dart';

/// 📱→📲 iPad / geniş ekran uyarlanabilir düzen katmanı.
///
/// Uygulama ~414pt telefon genişliği için tasarlandı; geniş ekranlarda
/// ([breakpoint] üstü) içerik olduğu gibi GERİLMEK yerine ortalanmış
/// [stageWidth] genişliğinde bir "sahne" kuşağına alınır:
///
///  - Kuşağın arkasını TAM EKRAN [BiladaBackground] doldurur → yanlarda
///    siyah/boş bant görünmez.
///  - Kuşağın içine daraltılmış bir [MediaQuery] verilir → ekran ölçüsüne
///    bakan kodlar (emoji overlay konumu, reveal düşüş yüksekliği vb.)
///    kuşağı "ekran" olarak görür; telefon oranları korunur.
///  - Navigator/Overlay da kuşağın İÇİNDE kaldığı için dialog ve
///    bottom-sheet'ler kendiliğinden kuşak genişliğiyle sınırlanır.
///  - Tam ekran kalması gereken efektler (havai fişek, vinyet, FİNAL
///    duyurusu) [StageFx] ile kuşağın DIŞINDAKİ efekt katmanına taşınır.
///
/// Telefonda (dar ekran) hiçbir şey değişmez — child aynen döner.
class AdaptiveStage extends StatefulWidget {
  const AdaptiveStage({super.key, required this.child});

  final Widget child;

  /// Bu genişliğin üstünde kuşak düzenine geçilir (iPad portre ≥768pt).
  static const double breakpoint = 600;

  /// İçerik kuşağının genişliği — büyükçe bir telefon gibi davranır.
  static const double stageWidth = 500;

  // Aktif sahne durumu — StageFx'in efektleri sahneye asabilmesi için.
  static _AdaptiveStageState? _state;

  /// Şu an geniş ekran (kuşak) düzeni etkin mi?
  static bool get isWide => _state?._wide ?? false;

  @override
  State<AdaptiveStage> createState() => _AdaptiveStageState();
}

class _AdaptiveStageState extends State<AdaptiveStage> {
  bool _wide = false;

  /// Kuşak dışına taşınan tam ekran efektler (StageFx başına bir giriş;
  /// LinkedHashMap olduğu için ekleme sırası = çizim sırası korunur).
  final Map<Object, Widget> _fx = <Object, Widget>{};

  @override
  void initState() {
    super.initState();
    AdaptiveStage._state = this;
  }

  @override
  void dispose() {
    if (AdaptiveStage._state == this) AdaptiveStage._state = null;
    super.dispose();
  }

  /// Efekt katmanına widget as/güncelle/kaldır (w == null → kaldır).
  /// StageFx build/dispose sırasında çağırdığı için çerçeve sonuna ertelenir.
  void _setFx(Object key, Widget? w) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      setState(() {
        if (w == null) {
          _fx.remove(key);
        } else {
          _fx[key] = w;
        }
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        _wide = constraints.maxWidth > AdaptiveStage.breakpoint;

        // Telefon: sarmalayıcı tamamen şeffaf — davranış birebir aynı.
        if (!_wide) return widget.child;

        final media = MediaQuery.of(context);
        final stageW = math.min(AdaptiveStage.stageWidth, constraints.maxWidth);

        return Stack(
          // expand: efekt katmanı girişleri tam ekran ölçü alsın.
          fit: StackFit.expand,
          children: [
            // Tam ekran tema arka planı — kuşağın dışı boş/siyah KALMAZ.
            const BiladaBackground(),

            // Ortalanmış içerik kuşağı — hafif kenar çizgisi + yumuşak
            // gölgeyle zarif "sahne" hissi.
            Center(
              child: Container(
                width: stageW,
                clipBehavior: Clip.antiAlias, // içerik kuşak dışına taşmasın
                decoration: BoxDecoration(
                  border: Border.symmetric(
                    vertical: BorderSide(
                      color: Colors.white.withValues(alpha: 0.08),
                    ),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.45),
                      blurRadius: 48,
                      spreadRadius: 4,
                    ),
                  ],
                ),
                // Kuşak içindeki kod "ekran"ı kuşak genişliğinde görsün
                // (MediaQuery.size'a bağlı konum/ölçü hesapları için).
                child: MediaQuery(
                  data: media.copyWith(size: Size(stageW, media.size.height)),
                  child: widget.child,
                ),
              ),
            ),

            // Kuşağa hapsolmaması gereken TAM EKRAN efektler (StageFx besler).
            for (final entry in _fx.entries)
              KeyedSubtree(key: ObjectKey(entry.key), child: entry.value),
          ],
        );
      },
    );
  }
}

/// Tam ekran efekt taşıyıcısı.
///
/// Telefonda çocuğunu OLDUĞU YERDE bırakır (davranış değişmez); geniş
/// ekranda ise çocuğu içerik kuşağının dışındaki, tüm ekranı kaplayan
/// efekt katmanına taşır. Havai fişek, kırmızı vinyet/sarsıntı, FİNAL
/// duyurusu gibi "ekranı kaplasın" istenen overlay'leri bununla sar.
class StageFx extends StatefulWidget {
  const StageFx({super.key, required this.child});

  final Widget child;

  @override
  State<StageFx> createState() => _StageFxState();
}

class _StageFxState extends State<StageFx> {
  bool _hoisted = false; // efekt şu an sahne katmanında mı?

  @override
  void didUpdateWidget(StageFx oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Efekt içeriği güncellendiyse sahnedeki kopyayı tazele.
    if (_hoisted) AdaptiveStage._state?._setFx(this, widget.child);
  }

  @override
  void dispose() {
    if (_hoisted) AdaptiveStage._state?._setFx(this, null);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final wide = AdaptiveStage.isWide;
    if (wide != _hoisted) {
      _hoisted = wide;
      AdaptiveStage._state?._setFx(this, wide ? widget.child : null);
    }
    // Geniş ekranda efekt sahne katmanında çizilir; yerinde iz bırakma.
    return wide ? const SizedBox.shrink() : widget.child;
  }
}
