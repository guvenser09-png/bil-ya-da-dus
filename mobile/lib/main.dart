import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:quizroyale/core/network/api_client.dart';
import 'package:quizroyale/core/router/app_router.dart';
import 'package:quizroyale/core/services/ad_service.dart';
import 'package:quizroyale/core/services/push_service.dart';
import 'package:quizroyale/core/theme/app_theme.dart';
import 'package:quizroyale/shared/widgets/adaptive_stage.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Portrait only
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));

  // Hive local storage
  try {
    await Hive.initFlutter();
  } catch (_) {}

  // API client
  try {
    ApiClient.instance.init();
  } catch (_) {}

  // Push bildirimleri (FCM). AWAIT EDİLMEZ → açılışı yavaşlatmaz.
  // Firebase yapılandırması (GoogleService-Info.plist) yoksa servis sessizce
  // devre dışı kalır; hata yutulur. İZİN BURADA İSTENMEZ — ilk maç bitince
  // istenir (bkz. core/services/push_service.dart).
  unawaited(PushService.instance.init());

  // AdMob (ödüllü reklam). SADECE mobilde — web'de google_mobile_ads no-op.
  // AWAIT EDİLMEZ → açılışı yavaşlatmaz; hata yutulur. SDK başlayınca ilk
  // ödüllü reklam önden yüklenir (bkz. core/services/ad_service.dart).
  if (!kIsWeb) {
    unawaited(_initAds());
  }

  runApp(const ProviderScope(child: BiladaApp()));
}

/// AdMob SDK'sını başlatır ve ilk ödüllü reklamı önden yükler. Hata yutulur
/// (reklam yoksa uygulama sorunsuz çalışır). Yalnızca mobilde çağrılır.
Future<void> _initAds() async {
  try {
    await MobileAds.instance.initialize();
    AdService.instance.init();
  } catch (_) {}
}

class BiladaApp extends ConsumerWidget {
  const BiladaApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: 'Bil ya da Düş',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      routerConfig: router,
      // iPad/geniş ekran: içerik ortalanmış ~500pt kuşağa alınır, arkasını
      // tam ekran tema gradyanı doldurur (bkz. AdaptiveStage). Telefonda
      // sarmalayıcı tamamen şeffaftır.
      builder: (context, child) =>
          AdaptiveStage(child: child ?? const SizedBox.shrink()),
    );
  }
}
