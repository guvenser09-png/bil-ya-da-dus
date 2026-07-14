import UIKit
import Flutter
import UserNotifications

@main
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    GeneratedPluginRegistrant.register(with: self)

    // Push bildirimleri (FCM/APNs).
    //
    // ÖNEMLİ: Burada `FirebaseApp.configure()` ÇAĞRILMAZ. Firebase, Dart
    // tarafında `Firebase.initializeApp()` ile başlatılır (push_service.dart);
    // GoogleService-Info.plist YOKSA oradaki istisna yutulur ve uygulama normal
    // açılır. Native tarafta configure çağırsaydık, plist yokken uygulama
    // AÇILIŞTA ÇÖKERDİ.
    //
    // Bildirim merkezinin delegesini üstleniyoruz: bildirim ön plandayken de
    // gösterilebilsin ve dokunma olayı Flutter'a ulaşsın. (firebase_messaging,
    // method swizzling ile APNs token'ını buradan alır — ek kod gerekmez.)
    if #available(iOS 10.0, *) {
      UNUserNotificationCenter.current().delegate = self as UNUserNotificationCenterDelegate
    }

    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
}
