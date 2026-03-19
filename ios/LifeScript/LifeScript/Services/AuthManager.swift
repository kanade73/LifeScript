import Foundation
import Supabase

@MainActor
class AuthManager: ObservableObject {
    @Published var isLoggedIn = false
    @Published var userEmail: String = ""
    @Published var userId: String?
    @Published var errorMessage: String?
    @Published var needsOnboarding = false

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
            userId = session.user.id.uuidString
            await checkOnboarding()
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
            userId = session.user.id.uuidString
            isLoggedIn = true
            await checkOnboarding()
        } catch {
            errorMessage = "ログインに失敗しました"
        }
    }

    func skipAuth() {
        isLoggedIn = true
        userEmail = "dev@local"
        userId = nil
    }

    func signOut() async {
        try? await supabase.auth.signOut()
        isLoggedIn = false
        userEmail = ""
        userId = nil
        needsOnboarding = false
    }

    func checkOnboarding() async {
        guard let uid = userId else {
            needsOnboarding = true
            return
        }
        do {
            let logs: [MachineLog] = try await supabase
                .from("machine_logs")
                .select()
                .eq("user_id", value: uid)
                .eq("action_type", value: "memory")
                .limit(1)
                .execute()
                .value
            needsOnboarding = logs.isEmpty
        } catch {
            needsOnboarding = true
        }
    }

    func completeOnboarding() {
        needsOnboarding = false
    }
}
