import SwiftUI

struct HomeTab: View {
    @EnvironmentObject var dataService: DataService
    @State private var showEventForm = false
    @State private var editingEvent: CalendarEvent?
    @State private var showReminderAlert = false
    @State private var reminderText = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // ── 挨拶ヘッダー ──
                    greetingSection

                    // ── マシンの提案 ──
                    suggestionsSection

                    // ── 通知 ──
                    notificationsSection

                    // ── スケジュール（予定 + リマインダー） ──
                    scheduleSection

                    // ── メモリサマリー ──
                    memorySection

                    // ── 動的ウィジェット ──
                    ForEach(dataService.dynamicWidgets) { widget in
                        dynamicWidgetCard(widget)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)
                .padding(.bottom, 20)
            }
            .background(Color(hex: "FAFAF8"))
            .navigationTitle("LifeScript")
            .navigationBarTitleDisplayMode(.inline)
            .refreshable {
                await dataService.fetchAll()
            }
        }
    }

    // MARK: - Greeting

    private var greetingSection: some View {
        let hour = Calendar.current.component(.hour, from: Date())
        let (greeting, icon, color): (String, String, String) = {
            switch hour {
            case 0..<6: return ("おやすみなさい", "moon.fill", "9B59B6")
            case 6..<12: return ("おはようございます", "sun.max.fill", "FFA500")
            case 12..<18: return ("こんにちは", "sun.min.fill", "FFD02F")
            default: return ("こんばんは", "moon.stars.fill", "4262FF")
            }
        }()

        return HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(Color(hex: color))
                    .frame(width: 48, height: 48)
                Image(systemName: icon)
                    .font(.system(size: 22))
                    .foregroundColor(.white)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(greeting)
                    .font(.system(size: 22, weight: .heavy))
                    .foregroundColor(Color(hex: "2D2B27"))
                HStack(spacing: 6) {
                    Circle()
                        .fill(Color(hex: "00C875"))
                        .frame(width: 8, height: 8)
                    Text("今週\(dataService.weekEventCount)件の予定")
                        .font(.system(size: 13))
                        .foregroundColor(Color(hex: "6B6560"))
                }
            }

            Spacer()

            Text(Date(), format: .dateTime.month().day())
                .font(.system(size: 18, weight: .bold))
                .foregroundColor(Color(hex: "A09A93"))
        }
        .padding(.vertical, 4)
    }

    // MARK: - Suggestions

    private var suggestionsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Image(systemName: "sparkles")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color(hex: "FFA500"))
                Text("Machine")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color(hex: "2D2B27"))
                Spacer()

                // 凡例
                HStack(spacing: 3) {
                    Image(systemName: "calendar")
                        .font(.system(size: 10))
                        .foregroundColor(Color(hex: "4262FF"))
                    Text("今週\(dataService.weekEventCount)件")
                        .font(.system(size: 10))
                        .foregroundColor(Color(hex: "6B6560"))
                }
            }

            if dataService.suggestions.isEmpty {
                Text("マシンからの提案はまだありません")
                    .font(.system(size: 13))
                    .foregroundColor(Color(hex: "A09A93"))
                    .italic()
                    .padding(.vertical, 4)
            } else {
                ForEach(dataService.suggestions) { log in
                    SuggestionCard(log: log)
                        .environmentObject(dataService)
                }
            }
        }
        .padding(16)
        .background(Color.white)
        .cornerRadius(16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color(hex: "E8E4DC"), lineWidth: 1)
        )
    }

    // MARK: - Notifications

    private var notificationsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Image(systemName: "bell")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color(hex: "00C875"))
                Text("通知")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color(hex: "2D2B27"))
            }

            Divider()

            if dataService.notifications.isEmpty {
                Text("通知なし")
                    .font(.system(size: 13))
                    .foregroundColor(Color(hex: "A09A93"))
                    .italic()
                    .padding(.vertical, 4)
            } else {
                ForEach(dataService.notifications.prefix(5)) { log in
                    HomeNotificationRow(log: log)
                }
            }
        }
        .padding(16)
        .background(Color.white)
        .cornerRadius(16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color(hex: "E8E4DC"), lineWidth: 1)
        )
    }

    // MARK: - Schedule (Events + Reminders)

    private var scheduleSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Image(systemName: "calendar")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color(hex: "4262FF"))
                Text("スケジュール")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color(hex: "2D2B27"))

                Spacer()

                Button {
                    showReminderAlert = true
                } label: {
                    Image(systemName: "pin.fill")
                        .font(.system(size: 14))
                        .foregroundColor(Color(hex: "9B59B6"))
                }

                Button {
                    editingEvent = nil
                    showEventForm = true
                } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(Color(hex: "4262FF"))
                }
            }

            // 凡例
            HStack(spacing: 3) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color(hex: "4262FF"))
                    .frame(width: 8, height: 8)
                Text("予定")
                    .font(.system(size: 10))
                    .foregroundColor(Color(hex: "6B6560"))
                Spacer().frame(width: 4)
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color(hex: "9B59B6"))
                    .frame(width: 8, height: 8)
                Text("マシン")
                    .font(.system(size: 10))
                    .foregroundColor(Color(hex: "6B6560"))
                Spacer().frame(width: 4)
                Image(systemName: "pin.fill")
                    .font(.system(size: 10))
                    .foregroundColor(Color(hex: "9B59B6"))
                Text("リマインダー")
                    .font(.system(size: 10))
                    .foregroundColor(Color(hex: "6B6560"))
            }

            Divider()

            if dataService.todayEvents.isEmpty && dataService.reminders.isEmpty {
                Text("予定・リマインダーなし")
                    .font(.system(size: 14))
                    .foregroundColor(Color(hex: "A09A93"))
                    .italic()
                    .padding(.vertical, 8)
            } else {
                // イベント（タップで編集、スワイプで削除）
                ForEach(dataService.todayEvents) { event in
                    EventRow(event: event)
                        .contentShape(Rectangle())
                        .onTapGesture {
                            editingEvent = event
                            showEventForm = true
                        }
                        .contextMenu {
                            Button {
                                editingEvent = event
                                showEventForm = true
                            } label: {
                                Label("編集", systemImage: "pencil")
                            }
                            Button(role: .destructive) {
                                Task { await dataService.deleteEvent(event) }
                            } label: {
                                Label("削除", systemImage: "trash")
                            }
                        }
                }

                // リマインダー
                ForEach(dataService.reminders) { reminder in
                    ReminderRow(log: reminder)
                        .contextMenu {
                            Button(role: .destructive) {
                                Task { await dataService.deleteReminder(reminder) }
                            } label: {
                                Label("削除", systemImage: "trash")
                            }
                        }
                }
            }
        }
        .padding(16)
        .background(Color.white)
        .cornerRadius(16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color(hex: "E8E4DC"), lineWidth: 1)
        )
        .sheet(isPresented: $showEventForm) {
            EventFormSheet(editingEvent: editingEvent)
                .environmentObject(dataService)
        }
        .alert("リマインダーを追加", isPresented: $showReminderAlert) {
            TextField("内容", text: $reminderText)
            Button("追加") {
                let text = reminderText.trimmingCharacters(in: .whitespaces)
                if !text.isEmpty {
                    Task { await dataService.addReminder(content: text) }
                }
                reminderText = ""
            }
            Button("キャンセル", role: .cancel) { reminderText = "" }
        }
    }

    // MARK: - Memory Summary

    private var memorySection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color(hex: "4262FF"))
                Text("メモリ")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color(hex: "2D2B27"))
                Spacer()
                Text("\(dataService.memories.count)件")
                    .font(.system(size: 12))
                    .foregroundColor(Color(hex: "A09A93"))
            }

            Divider()

            if dataService.memories.isEmpty {
                Text("メモリなし — PC版でオンボーディングを完了すると表示されます")
                    .font(.system(size: 13))
                    .foregroundColor(Color(hex: "A09A93"))
                    .italic()
                    .padding(.vertical, 4)
            } else {
                ForEach(dataService.memories.prefix(3)) { mem in
                    HStack(spacing: 8) {
                        Image(systemName: mem.actionType == "memory_auto" ? "eye" : "person.fill")
                            .font(.system(size: 13))
                            .foregroundColor(
                                mem.actionType == "memory_auto"
                                    ? Color(hex: "FFA500")
                                    : Color(hex: "4262FF")
                            )
                        Text(mem.displayContent)
                            .font(.system(size: 13))
                            .foregroundColor(Color(hex: "2D2B27"))
                            .lineLimit(2)
                    }
                }

                if dataService.memories.count > 3 {
                    Text("他\(dataService.memories.count - 3)件...")
                        .font(.system(size: 12))
                        .foregroundColor(Color(hex: "A09A93"))
                        .italic()
                }
            }
        }
        .padding(16)
        .background(Color.white)
        .cornerRadius(16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color(hex: "E8E4DC"), lineWidth: 1)
        )
    }

    // MARK: - Dynamic Widget Card

    private func dynamicWidgetCard(_ widget: MachineLog) -> some View {
        let widgetName = String(widget.actionType.dropFirst(7)) // "widget:" を除去
        let content = widget.displayContent

        return VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Image(systemName: "doc.text")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color(hex: "4262FF"))
                Text(widgetName)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color(hex: "2D2B27"))
                Spacer()
                Text(String(widget.triggeredAt.prefix(16)).replacingOccurrences(of: "T", with: " ").dropFirst(5))
                    .font(.system(size: 10))
                    .foregroundColor(Color(hex: "A09A93"))
            }

            Divider()

            Text(content)
                .font(.system(size: 13))
                .foregroundColor(Color(hex: "2D2B27"))
        }
        .padding(16)
        .background(Color.white)
        .cornerRadius(16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color(hex: "E8E4DC"), lineWidth: 1)
        )
    }
}

// MARK: - Suggestion Card

struct SuggestionCard: View {
    let log: MachineLog
    @EnvironmentObject var dataService: DataService

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(log.displayContent)
                .font(.system(size: 14))
                .foregroundColor(Color(hex: "2D2B27"))

            HStack(spacing: 12) {
                Spacer()

                Button(action: {
                    Task { await dataService.approveSuggestion(log) }
                }) {
                    Label("承認", systemImage: "checkmark")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(Color(hex: "00C875"))
                }

                Button(action: {
                    Task { await dataService.dismissSuggestion(log) }
                }) {
                    Label("却下", systemImage: "xmark")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundColor(Color(hex: "A09A93"))
                }
            }
        }
        .padding(12)
        .background(Color(hex: "FFFBF0"))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color(hex: "F0E8D8"), lineWidth: 1)
        )
    }
}

// MARK: - Event Row

struct EventRow: View {
    let event: CalendarEvent

    var body: some View {
        HStack(spacing: 10) {
            RoundedRectangle(cornerRadius: 2)
                .fill(event.source == "machine" ? Color(hex: "9B59B6") : Color(hex: "4262FF"))
                .frame(width: 4, height: 40)

            VStack(alignment: .leading, spacing: 2) {
                Text(event.title)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(Color(hex: "2D2B27"))
                Text("\(event.dateString) \(event.timeString)")
                    .font(.system(size: 12))
                    .foregroundColor(Color(hex: "A09A93"))
            }

            Spacer()

            if event.source == "machine" {
                Text("マシン")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(Color(hex: "9B59B6"))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Color(hex: "9B59B6").opacity(0.1))
                    .cornerRadius(6)
            }
        }
    }
}

// MARK: - Notification Row

struct HomeNotificationRow: View {
    let log: MachineLog

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: log.actionType == "notify_scheduled" ? "clock.fill" : "bell.fill")
                .font(.system(size: 14))
                .foregroundColor(
                    log.actionType == "notify_scheduled"
                        ? Color(hex: "4262FF")
                        : Color(hex: "00C875")
                )

            VStack(alignment: .leading, spacing: 2) {
                Text(log.displayContent)
                    .font(.system(size: 14))
                    .foregroundColor(Color(hex: "2D2B27"))
                    .lineLimit(2)
                Text(log.timeString)
                    .font(.system(size: 11))
                    .foregroundColor(Color(hex: "A09A93"))
            }

            Spacer()
        }
        .padding(.vertical, 2)
    }
}

// MARK: - Reminder Row

struct ReminderRow: View {
    let log: MachineLog

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "pin.fill")
                .font(.system(size: 14))
                .foregroundColor(Color(hex: "9B59B6"))

            Text(log.displayContent)
                .font(.system(size: 13))
                .foregroundColor(Color(hex: "2D2B27"))
                .lineLimit(2)

            Spacer()

            Text(String(log.triggeredAt.prefix(16))
                .replacingOccurrences(of: "T", with: " ")
                .dropFirst(5))
                .font(.system(size: 11))
                .foregroundColor(Color(hex: "A09A93"))
        }
        .padding(.vertical, 2)
    }
}
