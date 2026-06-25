import 'package:quizroyale/core/network/api_client.dart';

/// Backend mağaza uçlarına ince HTTP sarmalayıcı.
///
/// Sadece [ApiClient] (Dio) kullanır; token interceptor tarafından otomatik
/// eklenir. Mağaza tek para birimi (ALTIN) üzerine kuruludur:
/// karakterler bireysel olarak altınla alınır; gerçek para yalnızca ALTIN
/// paketi ve PREMIUM üyelik içindir.
///
/// Sözleşme:
/// - GET   /api/store/characters     -> {coins, equipped, characters:[...]}  (auth)
/// - POST  /api/store/characters/buy -> {bought, already_owned, coins, ...}  (auth)
/// - PATCH /api/users/me             -> kullanıcı (avatar_id güncelle/kuşan)  (auth)
/// - GET   /api/store/catalog        -> {products:[gold_* + premium_*]}  (auth opsiyonel)
/// - GET   /api/store/inventory      -> {coins, is_premium...}              (auth)
/// - POST  /api/store/purchase       -> {status, product_id, inventory}     (auth)
/// - POST  /api/store/restore        -> {restored, inventory}              (auth)
class StoreApi {
  StoreApi._();
  static final StoreApi instance = StoreApi._();

  /// Karakter kataloğu: her karakterin ALTIN fiyatı + sahiplik + kuşanılı
  /// durumu + güncel altın bakiyesi. Karakterler ucuzdan pahalıya sıralı gelir.
  /// `{coins:int, equipped:String, characters:[{id, name, price_coins, rarity,
  ///   free, owned, equipped}]}` (auth gerekir).
  Future<Map<String, dynamic>> getCharacters() async {
    return ApiClient.instance.get('/api/store/characters');
  }

  /// Bir karakteri ALTIN ile satın alır.
  /// Başarıda `{bought, already_owned, character_id, coins}` döner.
  /// Yetersiz altın / geçersiz karakterde backend HTTP 400 fırlatır.
  Future<Map<String, dynamic>> buyCharacter(String characterId) async {
    return ApiClient.instance
        .post('/api/store/characters/buy', body: {'character_id': characterId});
  }

  /// Bir karakteri kuşanır (avatar_id günceller). Sunucu sahiplik kapısı uygular;
  /// sahip değilse HTTP 400 fırlatır. Başarıda güncel kullanıcı döner.
  Future<Map<String, dynamic>> equipCharacter(String characterId) async {
    return ApiClient.instance
        .patch('/api/users/me', body: {'avatar_id': characterId});
  }

  /// Gerçek-para ürün kataloğu (yalnızca ALTIN paketleri + PREMIUM abonelikler).
  /// Token varsa abonelik ürünlerinde `owned` bayrağı işaretli gelir.
  Future<List<Map<String, dynamic>>> getCatalog() async {
    final res = await ApiClient.instance.get('/api/store/catalog');
    return _asMapList(res['products']);
  }

  /// Kullanıcının envanteri (coins/premium). Auth gerekir.
  Future<Map<String, dynamic>> getInventory() async {
    return ApiClient.instance.get('/api/store/inventory');
  }

  /// Satın alma makbuzunu backend'e gönderir (gerçek-para ürünler).
  ///
  /// Başarıda `{status, product_id, transaction_id, inventory{...}}` döner.
  /// Geçersiz makbuzda backend HTTP 400 fırlatır (DioException olarak yükselir).
  Future<Map<String, dynamic>> purchase({
    required String platform,
    required String productId,
    required String receipt,
    String? transactionId,
  }) async {
    return ApiClient.instance.post(
      '/api/store/purchase',
      body: {
        'platform': platform,
        'product_id': productId,
        'receipt': receipt,
        'transaction_id': transactionId,
      },
    );
  }

  /// Doğrulanmış non-consumable satın almaları yeniden uygular.
  /// `{restored: [...], inventory{...}}` döner.
  Future<Map<String, dynamic>> restore() async {
    return ApiClient.instance.post('/api/store/restore');
  }

  /// `dynamic` bir liste alanını güvenli şekilde `List<Map<String,dynamic>>`
  /// yapar. Null/yanlış tipte boş liste döner.
  static List<Map<String, dynamic>> _asMapList(dynamic raw) {
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((e) => e.map((k, v) => MapEntry(k.toString(), v)))
        .toList();
  }
}
