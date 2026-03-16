import SwiftUI

struct MemoryTab: View {
    @EnvironmentObject var dataService: DataService

    private var manualMemories: [MachineLog] {
        dataService.memories.filter { $0.actionType == "memory" }
    }

    private var autoMemories: [MachineLog] {
        dataService.memories.filter { $0.actionType == "memory_auto" }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // 説明
                    Text("マシンが把握しているあなたの情報")
                        .font(.system(size: 13))
                        .foregroundColor(Color(hex: "6B6560"))
                        .padding(.horizontal, 16)

                    // マシンの観察
                    if !autoMemories.isEmpty {
                        memorySection(
                            title: "マシンの観察",
                            icon: "eye.fill",
                            color: Color(hex: "FFA500"),
                            items: autoMemories
                        )
                    }

                    // ユーザーのメモリ
                    if !manualMemories.isEmpty {
                        memorySection(
                            title: "あなたが記録",
                            icon: "person.fill",
                            color: Color(hex: "4262FF"),
                            items: manualMemories
                        )
                    }

                    if manualMemories.isEmpty && autoMemories.isEmpty {
                        ContentUnavailableView(
                            "メモリなし",
                            systemImage: "brain.head.profile",
                            description: Text("PC版でtraitsを書くか、メモリを追加してください")
                        )
                        .padding(.top, 40)
                    }
                }
                .padding(.top, 8)
            }
            .background(Color(hex: "FAFAF8"))
            .navigationTitle("メモリ")
            .navigationBarTitleDisplayMode(.inline)
            .refreshable {
                await dataService.fetchAll()
            }
        }
    }

    private func memorySection(title: String, icon: String, color: Color, items: [MachineLog]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(title, systemImage: icon)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(color)
                .padding(.horizontal, 16)

            ForEach(items) { item in
                HStack(spacing: 10) {
                    Image(systemName: icon)
                        .font(.system(size: 12))
                        .foregroundColor(color)
                    Text(item.displayContent)
                        .font(.system(size: 14))
                        .foregroundColor(Color(hex: "2D2B27"))
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.white)
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color(hex: "E8E4DC"), lineWidth: 1)
                )
                .padding(.horizontal, 16)
            }
        }
    }
}
