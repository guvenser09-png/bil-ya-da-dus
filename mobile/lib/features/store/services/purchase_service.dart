import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:quizroyale/features/store/services/store_api.dart';

/// Bir satın alma denemesinin sonucu.
class PurchaseResult {
  const PurchaseResult({
    required this.success,
    this.status,
    this.productId,
    this.transactionId,
    this.inventory,
    this.error,
  });

  /// Backend doğruladı mı? (status 'verified' veya 'already_processed').
  final bool success;

  /// Backend status: 'verified' | 'already_processed' | null (hata).
  final String? status;

  final String? productId;
  final String? transactionId;

  /// Başarıda güncel envanter (coins/is_premium/character_packs...).
  final Map<String, dynamic>? inventory;

  /// Başarısızlık mesajı (kullanıcıya gösterilebilir).
  final String? error;

  factory PurchaseResult.failure(String message) =>
      PurchaseResult(success: false, error: message);
}

/// IAP (uygulama içi satın alma) soyutlama katmanı.
///
/// İKİ ÇALIŞMA MODU:
/// -----------------------------------------------------------------------
/// 1. GERÇEK CİHAZ (App Store / Play Store):
///    `in_app_purchase` paketi ile ürün sorgulanır, platform satın alma akışı
///    tetiklenir, `purchaseStream` dinlenir; başarıda mağazanın verdiği gerçek
///    `serverVerificationData` (receipt) + `purchaseID` (transaction_id)
///    backend `POST /api/store/purchase`'e gönderilir, doğrulanırsa
///    `completePurchase(...)` çağrılır.
/// 2. WEB / DEV (Chrome'da test):
///    `kIsWeb` ise veya `InAppPurchase.instance.isAvailable()` false ise
///    StoreKit/Play HİÇ ÇAĞRILMAZ. Eski sandbox akışı korunur: sahte
///    ('sandbox_') makbuz + benzersiz transaction_id üretilip doğrudan
///    backend'e gönderilir (backend `IAP_SANDBOX=True` iken kabul eder).
///
/// [buy] / [restore] gövdeleri guard'a göre dallanır; [PurchaseResult]
/// arayüzü AYNEN kalır, provider/UI değişmez.
/// -----------------------------------------------------------------------
class PurchaseService {
  PurchaseService._();
  static final PurchaseService instance = PurchaseService._();

  final StoreApi _api = StoreApi.instance;
  final InAppPurchase _iap = InAppPurchase.instance;

  /// StoreKit/Play ürün kimliği (ör. `com.bilyadadus.gold_small`) → backend
  /// katalog `product_id` (ör. `gold_small`) eşlemesi. `registerCatalog` doldurur;
  /// makbuz doğrulamasında mağaza id'sini katalog id'sine çevirmek için kullanılır
  /// (KRİTİK: yoksa gerçek satın almada backend eşleşmesi başarısız olur).
  final Map<String, String> _storeIdToCatalog = {};

  /// Katalog ürünlerini mağaza-id ↔ katalog-id eşlemesi için kaydet.
  /// store_provider katalog yüklendiğinde çağırır.
  void registerCatalog(List<Map<String, dynamic>> products) {
    for (final p in products) {
      final cid = p['product_id']?.toString();
      if (cid == null || cid.isEmpty) continue;
      _storeIdToCatalog[cid] = cid;
      final ios = p['ios_product_id']?.toString();
      final and = p['android_product_id']?.toString();
      if (ios != null && ios.isNotEmpty) _storeIdToCatalog[ios] = cid;
      if (and != null && and.isNotEmpty) _storeIdToCatalog[and] = cid;
    }
  }

  /// Bir katalog ürününün PLATFORM mağaza kimliği (iOS: ios_product_id,
  /// Android: android_product_id). Yoksa katalog product_id'ye düşer.
  String _storeId(Map<String, dynamic> product) {
    final pid = product['product_id']?.toString() ?? '';
    if (!kIsWeb && Platform.isAndroid) {
      return product['android_product_id']?.toString() ?? pid;
    }
    return product['ios_product_id']?.toString() ?? pid;
  }

  /// Mağazadan (StoreKit/Play) YERELLEŞTİRİLMİŞ fiyatları çeker.
  /// Dönüş: {katalog product_id → "₺29,99" gibi yerel fiyat}. Web/dev'de veya
  /// mağaza erişilemezse boş map (UI katalog price_display'e düşer).
  Future<Map<String, String>> fetchLocalizedPrices(
      List<Map<String, dynamic>> products) async {
    if (!await _useStoreKit()) return {};
    final ids = <String>{};
    final storeToCatalog = <String, String>{};
    for (final p in products) {
      final cid = p['product_id']?.toString();
      if (cid == null || cid.isEmpty) continue;
      final sid = _storeId(p);
      ids.add(sid);
      storeToCatalog[sid] = cid;
    }
    if (ids.isEmpty) return {};
    try {
      final resp = await _iap.queryProductDetails(ids);
      final out = <String, String>{};
      for (final d in resp.productDetails) {
        final cid = storeToCatalog[d.id];
        if (cid != null) out[cid] = d.price;
      }
      return out;
    } catch (_) {
      return {};
    }
  }

  /// Çalıştığımız platform: 'ios' | 'android'. Web'de test için 'ios' varsayılır
  /// (yalnızca sandbox akışında anlamlı).
  String get _platform {
    if (kIsWeb) return 'ios';
    return Platform.isAndroid ? 'android' : 'ios';
  }

  /// Gerçek StoreKit/Play akışı kullanılmalı mı? Web değilse ve mağaza
  /// erişilebilirse true. Web/dev'de false → eski sandbox akışı.
  Future<bool> _useStoreKit() async {
    if (kIsWeb) return false;
    try {
      return await _iap.isAvailable();
    } catch (_) {
      return false;
    }
  }

  /// Verilen ürünü satın alır.
  ///
  /// [product] katalog girdisidir (product_id zorunlu).
  Future<PurchaseResult> buy(Map<String, dynamic> product) async {
    final productId = product['product_id']?.toString();
    if (productId == null || productId.isEmpty) {
      return PurchaseResult.failure('Geçersiz ürün.');
    }

    if (await _useStoreKit()) {
      return _buyViaStoreKit(productId, product);
    }
    return _buyViaSandbox(productId);
  }

  /// GERÇEK akış: StoreKit / Play Billing üzerinden satın al, makbuzu backend'e
  /// doğrulat, başarıda `completePurchase` çağır.
  Future<PurchaseResult> _buyViaStoreKit(
      String productId, Map<String, dynamic> product) async {
    // StoreKit/Play ürün kimliği (ör. com.bilyadadus.gold_small) — backend
    // katalog product_id'sinden (gold_small) FARKLI olabilir; satın alma
    // bununla yapılır, doğrulamaya katalog id'si gönderilir.
    final storeId = _storeId(product);
    // 1) Ürünü mağazadan sorgula.
    final ProductDetailsResponse response;
    try {
      response = await _iap.queryProductDetails({storeId});
    } catch (_) {
      return PurchaseResult.failure(
          'Mağazaya bağlanılamadı. Lütfen tekrar deneyin.');
    }
    if (response.error != null) {
      return PurchaseResult.failure(
          'Ürün bilgisi alınamadı. Lütfen tekrar deneyin.');
    }
    if (response.productDetails.isEmpty) {
      return PurchaseResult.failure('Bu ürün şu anda mağazada bulunamadı.');
    }
    final details = response.productDetails.first;

    // 2) Satın alma akışını dinle. Bu mağaza id'si için bir sonucu bekle.
    final completer = Completer<PurchaseResult>();
    late final StreamSubscription<List<PurchaseDetails>> sub;
    sub = _iap.purchaseStream.listen(
      (purchases) async {
        for (final purchase in purchases) {
          if (purchase.productID != storeId) continue;
          switch (purchase.status) {
            case PurchaseStatus.pending:
              // Beklemede; sonucu beklemeye devam et.
              break;
            case PurchaseStatus.canceled:
              if (!completer.isCompleted) {
                completer.complete(
                    PurchaseResult.failure('Satın alma iptal edildi.'));
              }
              if (purchase.pendingCompletePurchase) {
                await _iap.completePurchase(purchase);
              }
              break;
            case PurchaseStatus.error:
              if (!completer.isCompleted) {
                completer.complete(PurchaseResult.failure(
                    'Satın alma başarısız. Lütfen tekrar deneyin.'));
              }
              if (purchase.pendingCompletePurchase) {
                await _iap.completePurchase(purchase);
              }
              break;
            case PurchaseStatus.purchased:
            case PurchaseStatus.restored:
              // 3) Makbuzu backend'e gönder, doğrulat (katalog id'siyle).
              final result =
                  await _verifyWithBackend(purchase, catalogProductId: productId);
              // 4) Mağazaya işlemi tamamladığımızı bildir.
              if (purchase.pendingCompletePurchase) {
                await _iap.completePurchase(purchase);
              }
              if (!completer.isCompleted) completer.complete(result);
              break;
          }
        }
      },
      onError: (_) {
        if (!completer.isCompleted) {
          completer.complete(
              PurchaseResult.failure('Bir hata oluştu. Lütfen tekrar deneyin.'));
        }
      },
    );

    // 5) Satın almayı başlat: tüketilebilir (altın paketleri) → buyConsumable;
    //    aksi halde (premium abonelikler) → buyNonConsumable.
    try {
      final purchaseParam = PurchaseParam(productDetails: details);
      final consumable = _isConsumable(product, productId);
      final started = consumable
          ? await _iap.buyConsumable(purchaseParam: purchaseParam)
          : await _iap.buyNonConsumable(purchaseParam: purchaseParam);
      if (!started && !completer.isCompleted) {
        completer.complete(
            PurchaseResult.failure('Satın alma başlatılamadı.'));
      }
    } catch (_) {
      if (!completer.isCompleted) {
        completer.complete(
            PurchaseResult.failure('Satın alma başlatılamadı.'));
      }
    }

    // Akış asılı kalmasın diye güvenlik zaman aşımı.
    final result = await completer.future.timeout(
      const Duration(minutes: 5),
      onTimeout: () =>
          PurchaseResult.failure('Satın alma zaman aşımına uğradı.'),
    );
    await sub.cancel();
    return result;
  }

  /// Mağaza makbuzunu backend'e gönderip doğrulatır.
  Future<PurchaseResult> _verifyWithBackend(PurchaseDetails purchase,
      {String? catalogProductId}) async {
    final receipt = purchase.verificationData.serverVerificationData;
    final source = purchase.verificationData.source; // 'app_store' | 'google_play'
    final txnId = purchase.purchaseID;
    // Backend katalog product_id'si ile doğrular; StoreKit'in döndürdüğü mağaza
    // id'sini (com.bilyadadus.*) katalog id'sine çevir (restore'da da çalışır).
    final catalogId = catalogProductId ??
        _storeIdToCatalog[purchase.productID] ??
        purchase.productID;
    try {
      final res = await _api.purchase(
        platform: _platformForSource(source),
        productId: catalogId,
        receipt: receipt,
        transactionId: txnId,
      );
      final status = res['status']?.toString();
      return PurchaseResult(
        success: status == 'verified' || status == 'already_processed',
        status: status,
        productId: res['product_id']?.toString(),
        transactionId: res['transaction_id']?.toString(),
        inventory: _asMap(res['inventory']),
      );
    } catch (e) {
      return PurchaseResult.failure(_errorMessage(e));
    }
  }

  /// SANDBOX akışı (web/dev): sahte makbuz üretip doğrudan backend'e gönderir.
  Future<PurchaseResult> _buyViaSandbox(String productId) async {
    final txnId = '${productId}_${DateTime.now().microsecondsSinceEpoch}';
    try {
      final res = await _api.purchase(
        platform: _platform,
        productId: productId,
        receipt: 'sandbox_$txnId',
        transactionId: txnId,
      );
      final status = res['status']?.toString();
      return PurchaseResult(
        success: status == 'verified' || status == 'already_processed',
        status: status,
        productId: res['product_id']?.toString(),
        transactionId: res['transaction_id']?.toString(),
        inventory: _asMap(res['inventory']),
      );
    } catch (e) {
      return PurchaseResult.failure(_errorMessage(e));
    }
  }

  /// Daha önce satın alınmış non-consumable hakları geri yükler.
  /// Gerçek cihazda önce `restorePurchases()` ile platform geri yükleme akışı
  /// tetiklenir (gelen makbuzlar purchaseStream üzerinden doğrulanır), ardından
  /// backend /restore ile envanter senkronlanır. Web/dev'de yalnızca backend.
  Future<PurchaseResult> restore() async {
    if (await _useStoreKit()) {
      try {
        // Platform geri yükleme akışını tetikle. Gelen non-consumable makbuzlar
        // purchaseStream'de (restored) işlenip backend'e doğrulatılır; ardından
        // /restore ile envanteri kesinleştiririz.
        final sub = _iap.purchaseStream.listen((purchases) async {
          for (final purchase in purchases) {
            if (purchase.status == PurchaseStatus.restored) {
              await _verifyWithBackend(purchase);
              if (purchase.pendingCompletePurchase) {
                await _iap.completePurchase(purchase);
              }
            }
          }
        });
        await _iap.restorePurchases();
        // Mağazanın stream'e makbuzları akıtması için kısa bekleme.
        await Future<void>.delayed(const Duration(seconds: 2));
        await sub.cancel();
      } catch (_) {
        // Platform geri yükleme başarısız olsa bile backend /restore deneriz.
      }
    }
    try {
      final res = await _api.restore();
      return PurchaseResult(
        success: true,
        status: 'restored',
        inventory: _asMap(res['inventory']),
      );
    } catch (e) {
      return PurchaseResult.failure(_errorMessage(e));
    }
  }

  /// Ürün tüketilebilir mi? Altın paketleri (coins/gold_*) → evet.
  /// Premium abonelikler (premium_*) → hayır (non-consumable API).
  static bool _isConsumable(Map<String, dynamic> product, String productId) {
    final type = product['type']?.toString();
    if (type == 'coins') return true;
    // type yoksa (offer kısayolları) id önekine bak.
    if (type == null) {
      return productId.startsWith('coins_') || productId.startsWith('gold_');
    }
    return false;
  }

  /// in_app_purchase'in verdiği `source` değerini backend platform'una çevirir.
  static String _platformForSource(String source) {
    if (source == 'google_play') return 'android';
    if (source == 'app_store') return 'ios';
    // Bilinmeyen kaynaklarda derleme platformuna güven.
    if (!kIsWeb && Platform.isAndroid) return 'android';
    return 'ios';
  }

  static Map<String, dynamic>? _asMap(dynamic raw) {
    if (raw is Map) {
      return raw.map((k, v) => MapEntry(k.toString(), v));
    }
    return null;
  }

  /// DioException dahil hataları kullanıcı dostu mesaja çevirir.
  static String _errorMessage(Object e) {
    final s = e.toString();
    if (s.contains('400')) return 'Satın alma doğrulanamadı.';
    return 'Bir hata oluştu. Lütfen tekrar deneyin.';
  }
}
