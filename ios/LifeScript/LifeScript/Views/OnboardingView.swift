import SwiftUI
import Supabase

struct OnboardingView: View {
    @EnvironmentObject var authManager: AuthManager
    var onComplete: () -> Void

    @State private var currentIndex = 0
    @State private var selectedIndex: Int? = nil
    @State private var answers: [String] = []

    private let questions: [(String, [String], String)] = [
        ("朝と夜、どちらが得意ですか？",
         ["朝型", "夜型", "どちらでもない"],
         "{answer}"),
        ("通知はいつ届くと嬉しいですか？",
         ["朝（7-9時）", "昼（12-14時）", "夕方（17-19時）", "夜（20-22時）", "いつでもOK"],
         "通知は{answer}に届けてほしい"),
        ("予定が詰まると…",
         ["ストレスを感じる（余白が欲しい）", "充実感がある（忙しいのが好き）", "特に気にしない"],
         "予定が詰まると{answer}"),
        ("疲れたときのリフレッシュ方法は？",
         ["美味しいものを食べる", "散歩・外出する", "家でゆっくり過ごす", "運動する", "寝る"],
         "疲れたときは{answer}ことが多い"),
        ("ダリーにどこまで任せたいですか？",
         ["積極的に提案してほしい", "控えめに提案してほしい", "聞いたときだけ答えてほしい"],
         "ダリーには{answer}"),
    ]

    var body: some View {
        VStack(spacing: 0) {
            Spacer().frame(height: 60)

            // ヘッダー
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 14)
                        .fill(Color(hex: "FFD02F"))
                        .frame(width: 48, height: 48)
                    Text("🤖")
                        .font(.system(size: 24))
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("はじめまして")
                        .font(.system(size: 24, weight: .heavy))
                        .foregroundColor(Color(hex: "2D2B27"))
                    Text("あなたのことを少し教えてください")
                        .font(.system(size: 13))
                        .foregroundColor(Color(hex: "6B6560"))
                }
                Spacer()
            }
            .padding(.horizontal, 32)

            // プログレスバー
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color(hex: "4262FF").opacity(0.15))
                        .frame(height: 4)
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color(hex: "4262FF"))
                        .frame(width: geo.size.width * CGFloat(currentIndex + 1) / CGFloat(questions.count), height: 4)
                }
            }
            .frame(height: 4)
            .padding(.horizontal, 32)
            .padding(.top, 16)

            Spacer().frame(height: 24)

            // 質問カード
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Text(questions[currentIndex].0)
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(Color(hex: "2D2B27"))
                    Spacer()
                    Text("\(currentIndex + 1) / \(questions.count)")
                        .font(.system(size: 13))
                        .foregroundColor(Color(hex: "6B6560"))
                }

                ForEach(Array(questions[currentIndex].1.enumerated()), id: \.offset) { idx, choice in
                    Button {
                        withAnimation(.easeInOut(duration: 0.15)) {
                            selectedIndex = idx
                        }
                    } label: {
                        HStack(spacing: 12) {
                            Circle()
                                .fill(selectedIndex == idx ? Color(hex: "4262FF") : Color.clear)
                                .frame(width: 20, height: 20)
                                .overlay(
                                    Circle().stroke(Color(hex: "4262FF"), lineWidth: 2)
                                )
                            Text(choice)
                                .font(.system(size: 15))
                                .foregroundColor(Color(hex: "2D2B27"))
                            Spacer()
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 14)
                        .background(selectedIndex == idx ? Color(hex: "4262FF").opacity(0.05) : Color.white)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(selectedIndex == idx ? Color(hex: "4262FF") : Color(hex: "E8E4DC"),
                                        lineWidth: selectedIndex == idx ? 2 : 1)
                        )
                    }
                }

                HStack {
                    Spacer()
                    Button {
                        onNext()
                    } label: {
                        HStack(spacing: 4) {
                            Text(currentIndex == questions.count - 1 ? "完了" : "次へ")
                                .font(.system(size: 14, weight: .semibold))
                            Image(systemName: currentIndex == questions.count - 1 ? "checkmark" : "arrow.right")
                                .font(.system(size: 14))
                        }
                        .foregroundColor(.white)
                        .padding(.horizontal, 24)
                        .padding(.vertical, 12)
                        .background(selectedIndex != nil ? Color(hex: "4262FF") : Color(hex: "4262FF").opacity(0.4))
                        .cornerRadius(12)
                    }
                    .disabled(selectedIndex == nil)
                }
            }
            .padding(24)
            .background(Color.white)
            .cornerRadius(16)
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(Color(hex: "E8E4DC"), lineWidth: 1)
            )
            .padding(.horizontal, 24)

            Spacer()
        }
        .background(Color(hex: "F2F0EB"))
    }

    private func onNext() {
        guard let idx = selectedIndex else { return }
        let (_, choices, template) = questions[currentIndex]
        let answer = choices[idx]
        answers.append(template.replacingOccurrences(of: "{answer}", with: answer))

        if currentIndex + 1 < questions.count {
            currentIndex += 1
            selectedIndex = nil
        } else {
            saveAndFinish()
        }
    }

    private func saveAndFinish() {
        Task {
            for memory in answers {
                do {
                    var payload: [String: String] = [
                        "action_type": "memory",
                        "content": memory,
                    ]
                    if let userId = authManager.userId {
                        payload["user_id"] = userId
                    }
                    try await supabase
                        .from("machine_logs")
                        .insert(payload)
                        .execute()
                } catch {
                    print("Onboarding save error: \(error)")
                }
            }
            // 初回提案を生成（オンボーディング回答に基づく）
            await generateWelcomeSuggestions()
            onComplete()
        }
    }

    private func generateWelcomeSuggestions() async {
        // 回答から文脈を読んで初回提案を生成
        let morningType = answers.first ?? ""
        let isMorningPerson = morningType.contains("朝型")

        var suggestions: [[String: String]] = []

        // 提案1: 朝型/夜型に応じた提案
        if isMorningPerson {
            suggestions.append([
                "action_type": "general_suggest",
                "content": "朝の時間を活用して、今週のタスクを整理してみない？\n理由: 朝型のあなたなら、朝の集中力が高い時間帯を活かせるはず\n<!--meta:{\"type\":\"notify\"}-->",
            ])
        } else {
            suggestions.append([
                "action_type": "general_suggest",
                "content": "夜のリラックスタイムに、明日の予定を確認してみない？\n理由: 夜型のあなたに合わせて、夜の時間を有効活用する提案です\n<!--meta:{\"type\":\"notify\"}-->",
            ])
        }

        // 提案2: LifeScript紹介
        suggestions.append([
            "action_type": "general_suggest",
            "content": "PC版のIDEで LifeScript を書いてみよう。例えば「毎朝天気を通知」のようなルールが作れるよ\n理由: LifeScriptを書くほど、ダリーがあなたの生活をもっと理解できるようになります\n<!--meta:{\"type\":\"notify\"}-->",
        ])

        for var suggestion in suggestions {
            if let userId = authManager.userId {
                suggestion["user_id"] = userId
            }
            try? await supabase
                .from("machine_logs")
                .insert(suggestion)
                .execute()
        }
    }
}
