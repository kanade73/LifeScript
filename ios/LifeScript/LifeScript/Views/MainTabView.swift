import SwiftUI

struct MainTabView: View {
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var dataService = DataService()

    var body: some View {
        TabView {
            HomeTab()
                .environmentObject(dataService)
                .tabItem {
                    Image(systemName: "house.fill")
                    Text("ホーム")
                }

            NotificationsTab()
                .environmentObject(dataService)
                .tabItem {
                    Image(systemName: "bell.fill")
                    Text("通知")
                }

            MemoryTab()
                .environmentObject(dataService)
                .tabItem {
                    Image(systemName: "brain.head.profile")
                    Text("メモリ")
                }

            SettingsTab()
                .environmentObject(authManager)
                .tabItem {
                    Image(systemName: "gearshape.fill")
                    Text("設定")
                }
        }
        .tint(Color(hex: "4262FF"))
        .task {
            await dataService.fetchAll()
        }
    }
}
