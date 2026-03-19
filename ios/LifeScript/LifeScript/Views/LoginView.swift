import SwiftUI

struct LoginView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var email = ""
    @State private var password = ""
    @State private var isLoading = false

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            // ロゴ
            VStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 20)
                        .fill(Color(hex: "4262FF"))
                        .frame(width: 72, height: 72)
                    Image(systemName: "sparkles")
                        .font(.system(size: 32, weight: .bold))
                        .foregroundColor(.white)
                }

                Text("LifeScript")
                    .font(.system(size: 28, weight: .heavy))
                    .foregroundColor(Color(hex: "2D2B27"))

                Text("あなたの生活を把握するマシン")
                    .font(.system(size: 14))
                    .foregroundColor(Color(hex: "6B6560"))
            }
            .padding(.bottom, 48)

            // 入力フォーム
            VStack(spacing: 16) {
                TextField("メールアドレス", text: $email)
                    .textFieldStyle(.plain)
                    .padding(16)
                    .background(Color.white)
                    .cornerRadius(12)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color(hex: "E8E4DC"), lineWidth: 1)
                    )
                    .textContentType(.emailAddress)
                    .autocapitalization(.none)

                SecureField("パスワード", text: $password)
                    .textFieldStyle(.plain)
                    .padding(16)
                    .background(Color.white)
                    .cornerRadius(12)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color(hex: "E8E4DC"), lineWidth: 1)
                    )
                    .textContentType(.password)

                if let error = authManager.errorMessage {
                    Text(error)
                        .font(.system(size: 13))
                        .foregroundColor(Color(hex: "FF7575"))
                }

                Button(action: {
                    isLoading = true
                    Task {
                        await authManager.signIn(email: email, password: password)
                        isLoading = false
                    }
                }) {
                    HStack {
                        if isLoading {
                            ProgressView()
                                .tint(.white)
                        }
                        Text("ログイン")
                            .font(.system(size: 16, weight: .semibold))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(16)
                    .background(Color(hex: "4262FF"))
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }
                .disabled(email.isEmpty || password.isEmpty || isLoading)
                .opacity(email.isEmpty || password.isEmpty ? 0.5 : 1)

                // 開発モード: 認証スキップ
                Button(action: {
                    authManager.skipAuth()
                }) {
                    Text("開発モードで続行")
                        .font(.system(size: 13))
                        .foregroundColor(Color(hex: "A09A93"))
                }
                .padding(.top, 8)
            }
            .padding(.horizontal, 32)

            Spacer()
            Spacer()
        }
        .background(Color(hex: "F2F0EB"))
    }
}
