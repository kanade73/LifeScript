import SwiftUI

struct SettingsTab: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        NavigationStack {
            List {
                Section("アカウント") {
                    HStack {
                        ZStack {
                            Circle()
                                .fill(Color(hex: "4262FF").opacity(0.15))
                                .frame(width: 40, height: 40)
                            Image(systemName: "person.fill")
                                .foregroundColor(Color(hex: "4262FF"))
                        }
                        VStack(alignment: .leading, spacing: 2) {
                            Text(authManager.userEmail.isEmpty ? "ローカル" : authManager.userEmail)
                                .font(.system(size: 15, weight: .medium))
                            Text("ログイン中")
                                .font(.system(size: 12))
                                .foregroundColor(Color(hex: "A09A93"))
                        }
                    }
                    .padding(.vertical, 4)
                }

                Section("情報") {
                    HStack {
                        Text("バージョン")
                        Spacer()
                        Text("0.2")
                            .foregroundColor(Color(hex: "A09A93"))
                    }
                    HStack {
                        Text("データ")
                        Spacer()
                        Text("Supabase")
                            .foregroundColor(Color(hex: "A09A93"))
                    }
                }

                Section {
                    Button(action: {
                        Task { await authManager.signOut() }
                    }) {
                        HStack {
                            Spacer()
                            Text("ログアウト")
                                .foregroundColor(Color(hex: "FF7575"))
                            Spacer()
                        }
                    }
                }
            }
            .navigationTitle("設定")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
