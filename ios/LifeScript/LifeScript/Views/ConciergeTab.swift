import SwiftUI
import Supabase

struct ConciergeTab: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var messages: [ChatMessage] = []
    @State private var inputText = ""
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // チャット履歴
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            // ウェルカムメッセージ
                            if messages.isEmpty && !isLoading {
                                VStack(spacing: 12) {
                                    ZStack {
                                        RoundedRectangle(cornerRadius: 18)
                                            .fill(Color(hex: "FFD02F"))
                                            .frame(width: 64, height: 64)
                                        Text("\u{1F916}")
                                            .font(.system(size: 32))
                                    }
                                    Text("ダリー")
                                        .font(.system(size: 20, weight: .heavy))
                                        .foregroundColor(Color(hex: "2D2B27"))
                                    Text("なんでも聞いてください")
                                        .font(.system(size: 14))
                                        .foregroundColor(Color(hex: "6B6560"))
                                }
                                .padding(.top, 60)
                            }

                            ForEach(messages) { msg in
                                ChatBubble(message: msg)
                                    .id(msg.id)
                            }

                            if isLoading {
                                HStack {
                                    ProgressView()
                                        .scaleEffect(0.8)
                                    Text("ダリーが考え中...")
                                        .font(.system(size: 13))
                                        .foregroundColor(Color(hex: "A09A93"))
                                    Spacer()
                                }
                                .padding(.horizontal, 16)
                                .id("loading")
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                    }
                    .onChange(of: messages.count) { _ in
                        withAnimation {
                            proxy.scrollTo(messages.last?.id ?? "loading", anchor: .bottom)
                        }
                    }
                }

                Divider()

                // 入力エリア
                HStack(spacing: 8) {
                    TextField("メッセージを入力...", text: $inputText, axis: .vertical)
                        .textFieldStyle(.plain)
                        .font(.system(size: 15))
                        .lineLimit(1...4)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(Color(hex: "F5F3EE"))
                        .cornerRadius(20)

                    Button {
                        sendMessage()
                    } label: {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 32))
                            .foregroundColor(
                                inputText.trimmingCharacters(in: .whitespaces).isEmpty
                                    ? Color(hex: "A09A93")
                                    : Color(hex: "4262FF")
                            )
                    }
                    .disabled(inputText.trimmingCharacters(in: .whitespaces).isEmpty || isLoading)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(Color.white)
            }
            .background(Color(hex: "F2F0EB"))
            .navigationTitle("ダリー")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private func sendMessage() {
        let text = inputText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return }

        let userMsg = ChatMessage(role: .user, content: text)
        messages.append(userMsg)
        inputText = ""
        isLoading = true

        Task {
            await chatWithDarii(text)
        }
    }

    private func chatWithDarii(_ userMessage: String) async {
        // メモリ（文脈）をSupabaseから取得
        var context = ""
        do {
            var query = supabase.from("machine_logs").select()
            if let uid = authManager.userId {
                query = query.eq("user_id", value: uid)
            }
            let memories: [MachineLog] = try await query
                .or("action_type.eq.memory,action_type.eq.memory_auto")
                .order("id", ascending: false)
                .limit(20)
                .execute()
                .value

            if !memories.isEmpty {
                context = "ユーザーについて知っていること:\n" + memories.map { "- \($0.displayContent)" }.joined(separator: "\n")
            }
        } catch {
            print("Context fetch error: \(error)")
        }

        // チャット履歴を構築
        var chatHistory: [[String: String]] = []
        let systemPrompt = """
        あなたは「ダリー」という名前のAIアシスタントです。LifeScriptというアプリのマシン（相棒）として、ユーザーの生活をサポートします。
        性格: 親しみやすく、少しおせっかい。ユーザーの生活文脈を理解して能動的に提案する。
        口調: カジュアルだが丁寧。絵文字は控えめに使う。
        \(context.isEmpty ? "" : "\n\(context)")
        """

        chatHistory.append(["role": "system", "content": systemPrompt])

        for msg in messages {
            chatHistory.append(["role": msg.role == .user ? "user" : "assistant", "content": msg.content])
        }

        // Edge Function or direct LLM呼び出し
        // ここではmachine_logsに会話を記録し、シンプルなレスポンスを返す
        do {
            // Supabase Edge Functionを呼ぶ（存在すれば）
            let response = try await callChat(messages: chatHistory)
            let assistantMsg = ChatMessage(role: .assistant, content: response)
            await MainActor.run {
                messages.append(assistantMsg)
                isLoading = false
            }

            // 会話ログを保存
            var payload: [String: String] = [
                "action_type": "chat",
                "content": "Q: \(userMessage)\nA: \(response)",
            ]
            if let uid = authManager.userId { payload["user_id"] = uid }
            try? await supabase.from("machine_logs").insert(payload).execute()
        } catch {
            let errorMsg = ChatMessage(role: .assistant, content: "ごめんなさい、今は応答できません。もう一度試してください。")
            await MainActor.run {
                messages.append(errorMsg)
                isLoading = false
            }
        }
    }

    private func callChat(messages: [[String: String]]) async throws -> String {
        // PC版のAPIエンドポイントを呼ぶ
        // フォールバック: ローカルで簡易応答
        guard let url = URL(string: "http://localhost:8000/chat") else {
            return fallbackResponse()
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 30
        request.httpBody = try JSONSerialization.data(withJSONObject: ["messages": messages])

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
                return fallbackResponse()
            }
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let reply = json["reply"] as? String {
                return reply
            }
            return fallbackResponse()
        } catch {
            return fallbackResponse()
        }
    }

    private func fallbackResponse() -> String {
        let responses = [
            "今はPCのバックエンドに接続できないみたい。PCでLifeScriptを起動してから、もう一度話しかけてね！",
            "ごめんね、今オフラインみたい。PCのLifeScriptを起動してくれたら、もっとちゃんとお話できるよ。",
            "PCのバックエンドが見つからないよ。LifeScriptのPC版を起動してみて！",
        ]
        return responses.randomElement()!
    }
}

// MARK: - Chat Models

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: ChatRole
    let content: String
}

enum ChatRole {
    case user, assistant
}

// MARK: - Chat Bubble

struct ChatBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 60) }

            if message.role == .assistant {
                ZStack {
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color(hex: "FFD02F"))
                        .frame(width: 32, height: 32)
                    Text("\u{1F916}")
                        .font(.system(size: 16))
                }
            }

            Text(message.content)
                .font(.system(size: 15))
                .foregroundColor(message.role == .user ? .white : Color(hex: "2D2B27"))
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(
                    message.role == .user
                        ? Color(hex: "4262FF")
                        : Color.white
                )
                .cornerRadius(18)
                .overlay(
                    message.role == .assistant
                        ? RoundedRectangle(cornerRadius: 18)
                            .stroke(Color(hex: "E8E4DC"), lineWidth: 1)
                        : nil
                )

            if message.role == .assistant { Spacer(minLength: 60) }
        }
    }
}
