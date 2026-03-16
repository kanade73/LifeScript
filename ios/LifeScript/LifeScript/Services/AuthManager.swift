import Foundation
import Supabase

@MainActor
class AuthManager: ObservableObject {
    @Published var isLoggedIn = false
    @Published var userEmail: String = ""
    @Published var errorMessage: String?

    init() {
        Task {
            await checkSession()
        }
    }

    func checkSession() async {
        do {
            let session = try await supabase.auth.session
            isLoggedIn = true
            userEmail = session.user.email ?? ""
        } catch {
            isLoggedIn = false
        }
    }

    func signIn(email: String, password: String) async {
        errorMessage = nil
        do {
            let session = try await supabase.auth.signIn(
                email: email,
                password: password
            )
            userEmail = session.user.email ?? ""
            isLoggedIn = true
        } catch {
            errorMessage = "ログインに失敗しました"
        }
    }

    func skipAuth() {
        isLoggedIn = true
        userEmail = "dev@local"
    }

    func signOut() async {
        try? await supabase.auth.signOut()
        isLoggedIn = false
        userEmail = ""
    }
}
