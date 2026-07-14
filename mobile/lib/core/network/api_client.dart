import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:quizroyale/core/constants/app_constants.dart';
import 'package:quizroyale/core/storage/secure_storage.dart';

class ApiClient {
  ApiClient._();
  static final ApiClient instance = ApiClient._();

  late final Dio _dio;
  bool _initialized = false;

  void init() {
    if (_initialized) return;
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConstants.baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 30),
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
      ),
    );
    _dio.interceptors.add(_AuthInterceptor());
    _initialized = true;
  }

  Future<Map<String, dynamic>> get(String path, {Map<String, dynamic>? query}) async {
    final res = await _dio.get(path, queryParameters: query);
    return res.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> post(String path, {dynamic body}) async {
    final res = await _dio.post(path, data: body);
    return res.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> patch(String path, {dynamic body}) async {
    final res = await _dio.patch(path, data: body);
    return res.data as Map<String, dynamic>;
  }

  /// [body]: DELETE isteği gövdesi (ör. silinecek push token'ı). Dio gövdeli
  /// DELETE'i destekler; mevcut çağrılar gövde vermediği için geriye dönük uyumlu.
  Future<Map<String, dynamic>> delete(String path, {dynamic body}) async {
    final res = await _dio.delete(path, data: body);
    return res.data as Map<String, dynamic>;
  }

  /// WebSocket bağlantıları (lobi/oyun) Dio interceptor'ından geçmediği için
  /// token'larını OTOMATİK yenilemez. Bu yüzden WS açmadan ÖNCE bu metodu çağır:
  /// mevcut access token süresi dolmuşsa (veya ~dolmak üzereyse) refresh token
  /// ile yeniler ve TAZE access token döndürür. Yenilenemezse null döner
  /// (çağıran tarafı kullanıcıyı tekrar girişe yönlendirebilir).
  ///
  /// Bu olmadan: 30 dk'lık access token süresi dolunca WS "4001 / not upgraded"
  /// hatası verir ve lobi/oyun bağlanamaz.
  Future<String?> ensureValidAccessToken() async {
    final access = await SecureStorage.instance.getAccessToken();
    if (access != null && !_isJwtExpired(access)) {
      return access; // hâlâ geçerli
    }
    // Süresi dolmuş/eksik → refresh token ile yenile
    final refresh = await SecureStorage.instance.getRefreshToken();
    if (refresh == null) return null;
    try {
      final dio = Dio(BaseOptions(baseUrl: AppConstants.baseUrl));
      final res = await dio.post(
        '/api/auth/refresh',
        data: {'refresh_token': refresh},
      );
      final newAccess = res.data['access_token'] as String;
      final newRefresh = res.data['refresh_token'] as String;
      await SecureStorage.instance.saveTokens(
        accessToken: newAccess,
        refreshToken: newRefresh,
      );
      return newAccess;
    } catch (_) {
      return null; // refresh de geçersiz → tekrar giriş gerekli
    }
  }

  /// JWT'nin `exp` alanını çözüp süresinin dolup dolmadığını döndürür
  /// (30 sn güvenlik payıyla). Çözülemezse "dolmuş" kabul edilir.
  static bool _isJwtExpired(String jwt) {
    try {
      final parts = jwt.split('.');
      if (parts.length != 3) return true;
      final payload = jsonDecode(
        utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))),
      ) as Map<String, dynamic>;
      final exp = payload['exp'];
      if (exp is! int) return true;
      final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
      return now >= (exp - 30);
    } catch (_) {
      return true;
    }
  }

  static String friendlyError(DioException e) {
    if (e.response != null) {
      final data = e.response!.data;
      if (data is Map && data['detail'] != null) return data['detail'].toString();
      switch (e.response!.statusCode) {
        case 400: return 'Geçersiz istek.';
        case 401: return 'Oturum süresi doldu, tekrar giriş yapın.';
        case 403: return 'Bu işlem için yetkiniz yok.';
        case 404: return 'Bulunamadı.';
        case 429: return 'Çok fazla istek. Lütfen bekleyin.';
        case 500: return 'Sunucu hatası. Lütfen tekrar deneyin.';
      }
    }
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return 'Bağlantı zaman aşımı. İnternetinizi kontrol edin.';
    }
    return 'Bir hata oluştu. Lütfen tekrar deneyin.';
  }
}

class _AuthInterceptor extends Interceptor {
  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await SecureStorage.instance.getAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    if (err.response?.statusCode == 401) {
      // Try to refresh token
      final refreshToken = await SecureStorage.instance.getRefreshToken();
      if (refreshToken != null) {
        try {
          final dio = Dio(BaseOptions(baseUrl: AppConstants.baseUrl));
          final res = await dio.post(
            '/api/auth/refresh',
            data: {'refresh_token': refreshToken},
          );
          final newAccess = res.data['access_token'] as String;
          final newRefresh = res.data['refresh_token'] as String;
          await SecureStorage.instance.saveTokens(
            accessToken: newAccess,
            refreshToken: newRefresh,
          );
          // Retry original request
          err.requestOptions.headers['Authorization'] = 'Bearer $newAccess';
          final retryRes = await dio.fetch(err.requestOptions);
          handler.resolve(retryRes);
          return;
        } catch (_) {
          await SecureStorage.instance.clearAll();
        }
      }
    }
    handler.next(err);
  }
}
