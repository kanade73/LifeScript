import SwiftUI

@main
struct LifeScriptApp: App {
    @StateObject private var authManager = AuthManager()

    var body: some Scene {
        WindowGroup {
            Group {
                if authManager.isLoggedIn {
                    if authManager.needsOnboarding {
                        OnboardingView {
                            authManager.completeOnboarding()
                        }
                        .environmentObject(authManager)
                    } else {
                        MainTabView()
                            .environmentObject(authManager)
                    }
                } else {
                    LoginView()
                        .environmentObject(authManager)
                }
            }
            .animation(.easeInOut(duration: 0.3), value: authManager.isLoggedIn)
            .animation(.easeInOut(duration: 0.3), value: authManager.needsOnboarding)
        }
    }
}
