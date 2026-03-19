import Foundation
import Supabase

/// Supabase からデータを取得するサービス
@MainActor
class DataService: ObservableObject {
    @Published var todayEvents: [CalendarEvent] = []
    @Published var suggestions: [MachineLog] = []
    @Published var notifications: [MachineLog] = []
    @Published var memories: [MachineLog] = []
    @Published var observations: [MachineLog] = []
    @Published var reminders: [MachineLog] = []
    @Published var dynamicWidgets: [MachineLog] = []
    @Published var weekEventCount: Int = 0
    @Published var isLoading = false

    var userId: String?

    func fetchAll() async {
        isLoading = true
        async let events = fetchTodayEvents()
        async let suggs = fetchSuggestions()
        async let notifs = fetchNotifications()
        async let mems = fetchMemories()
        async let obs = fetchObservations()
        async let rems = fetchReminders()
        async let dw = fetchDynamicWidgets()
        async let wec = fetchWeekEventCount()

        todayEvents = await events
        suggestions = await suggs
        notifications = await notifs
        memories = await mems
        observations = await obs
        reminders = await rems
        dynamicWidgets = await dw
        weekEventCount = await wec
        isLoading = false
    }

    // MARK: - Calendar Events (今日〜3日後)

    private func fetchTodayEvents() async -> [CalendarEvent] {
        let cal = Calendar.current
        let now = Date()
        let startOfDay = cal.startOfDay(for: now)
        let endOf3Days = cal.date(byAdding: .day, value: 3, to: startOfDay)!

        let formatter = ISO8601DateFormatter()
        let from = formatter.string(from: startOfDay)
        let to = formatter.string(from: endOf3Days)

        do {
            var query = supabase.from("calendar_events").select()
            if let uid = userId { query = query.eq("user_id", value: uid) }
            let events: [CalendarEvent] = try await query
                .gte("start_at", value: from)
                .lte("start_at", value: to)
                .order("start_at")
                .execute()
                .value
            return events
        } catch {
            print("Events fetch error: \(error)")
            return []
        }
    }

    // MARK: - Suggestions (calendar_suggest + general_suggest)

    private func fetchSuggestions() async -> [MachineLog] {
        do {
            var query = supabase.from("machine_logs").select()
            if let uid = userId { query = query.eq("user_id", value: uid) }
            let logs: [MachineLog] = try await query
                .or("action_type.eq.calendar_suggest,action_type.eq.general_suggest")
                .order("id", ascending: false)
                .limit(10)
                .execute()
                .value
            return logs
        } catch {
            print("Suggestions fetch error: \(error)")
            return []
        }
    }

    // MARK: - Observations (memory_auto)

    private func fetchObservations() async -> [MachineLog] {
        do {
            var query = supabase.from("machine_logs").select()
            if let uid = userId { query = query.eq("user_id", value: uid) }
            let logs: [MachineLog] = try await query
                .eq("action_type", value: "memory_auto")
                .order("id", ascending: false)
                .limit(10)
                .execute()
                .value
            return logs
        } catch {
            print("Observations fetch error: \(error)")
            return []
        }
    }

    // MARK: - Notifications

    private func fetchNotifications() async -> [MachineLog] {
        do {
            var query = supabase.from("machine_logs").select()
            if let uid = userId { query = query.eq("user_id", value: uid) }
            let logs: [MachineLog] = try await query
                .or("action_type.eq.notify,action_type.eq.notify_scheduled")
                .order("id", ascending: false)
                .limit(20)
                .execute()
                .value
            return logs
        } catch {
            print("Notifications fetch error: \(error)")
            return []
        }
    }

    // MARK: - Memories

    private func fetchMemories() async -> [MachineLog] {
        do {
            var query = supabase.from("machine_logs").select()
            if let uid = userId { query = query.eq("user_id", value: uid) }
            let logs: [MachineLog] = try await query
                .or("action_type.eq.memory,action_type.eq.memory_auto")
                .order("id", ascending: false)
                .limit(50)
                .execute()
                .value
            return logs
        } catch {
            print("Memories fetch error: \(error)")
            return []
        }
    }

    // MARK: - Reminders

    private func fetchReminders() async -> [MachineLog] {
        do {
            var query = supabase.from("machine_logs").select()
            if let uid = userId { query = query.eq("user_id", value: uid) }
            let logs: [MachineLog] = try await query
                .eq("action_type", value: "reminder")
                .order("id", ascending: false)
                .limit(10)
                .execute()
                .value
            return logs
        } catch {
            print("Reminders fetch error: \(error)")
            return []
        }
    }

    // MARK: - Dynamic Widgets

    private func fetchDynamicWidgets() async -> [MachineLog] {
        do {
            var query = supabase.from("machine_logs").select()
            if let uid = userId { query = query.eq("user_id", value: uid) }
            let logs: [MachineLog] = try await query
                .like("action_type", pattern: "widget:%")
                .order("id", ascending: false)
                .limit(20)
                .execute()
                .value
            var seen: Set<String> = []
            var unique: [MachineLog] = []
            for log in logs {
                let name = String(log.actionType.dropFirst(7))
                if !seen.contains(name) {
                    seen.insert(name)
                    unique.append(log)
                }
            }
            return unique
        } catch {
            print("Dynamic widgets fetch error: \(error)")
            return []
        }
    }

    // MARK: - Week Event Count

    private func fetchWeekEventCount() async -> Int {
        let cal = Calendar.current
        let now = Date()
        let weekStart = cal.date(from: cal.dateComponents([.yearForWeekOfYear, .weekOfYear], from: now))!
        let weekEnd = cal.date(byAdding: .day, value: 7, to: weekStart)!

        let formatter = ISO8601DateFormatter()
        let from = formatter.string(from: weekStart)
        let to = formatter.string(from: weekEnd)

        do {
            var query = supabase.from("calendar_events").select()
            if let uid = userId { query = query.eq("user_id", value: uid) }
            let events: [CalendarEvent] = try await query
                .gte("start_at", value: from)
                .lte("start_at", value: to)
                .execute()
                .value
            return events.count
        } catch {
            print("Week count fetch error: \(error)")
            return 0
        }
    }

    // MARK: - Actions

    func approveSuggestion(_ log: MachineLog) async {
        let type = log.suggestionType

        if type == "calendar" {
            // カレンダー提案 → イベント作成
            guard let jsonRange = log.content.range(of: #"(?<=<!--meta:).*?(?=-->)"#, options: .regularExpression),
                  let data = String(log.content[jsonRange]).data(using: .utf8),
                  let meta = try? JSONDecoder().decode(SuggestionMeta.self, from: data) else {
                // メタデータ解析失敗 → 提案を削除して終了
                await dismissSuggestion(log)
                return
            }

            let startAt = "\(meta.eventDate)T\(meta.eventTime):00+09:00"

            do {
                var eventPayload: [String: String] = [
                    "title": meta.eventTitle,
                    "start_at": startAt,
                    "source": "machine",
                    "note": "提案から承認",
                ]
                if let uid = userId { eventPayload["user_id"] = uid }

                try await supabase
                    .from("calendar_events")
                    .insert(eventPayload)
                    .execute()

                var logPayload: [String: String] = [
                    "action_type": "calendar_add",
                    "content": "提案を承認: 「\(meta.eventTitle)」",
                ]
                if let uid = userId { logPayload["user_id"] = uid }

                try await supabase
                    .from("machine_logs")
                    .insert(logPayload)
                    .execute()

                await fetchAll()
            } catch {
                print("Approve calendar error: \(error)")
            }
        } else {
            // notify提案 → 承認ログのみ
            do {
                var payload: [String: String] = [
                    "action_type": "notify",
                    "content": "提案を承認: 「\(log.bodyContent)」",
                ]
                if let uid = userId { payload["user_id"] = uid }

                try await supabase
                    .from("machine_logs")
                    .insert(payload)
                    .execute()

                // 元の提案を削除
                try await supabase
                    .from("machine_logs")
                    .delete()
                    .eq("id", value: log.id)
                    .execute()

                await fetchAll()
            } catch {
                print("Approve notify error: \(error)")
            }
        }
    }

    // MARK: - Event CRUD

    func addEvent(title: String, startAt: Date, endAt: Date?, note: String?) async {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        var payload: [String: String] = [
            "title": title,
            "start_at": formatter.string(from: startAt),
            "source": "user",
        ]
        if let uid = userId { payload["user_id"] = uid }
        if let endAt { payload["end_at"] = formatter.string(from: endAt) }
        if let note, !note.isEmpty { payload["note"] = note }

        do {
            try await supabase
                .from("calendar_events")
                .insert(payload)
                .execute()
            await fetchAll()
        } catch {
            print("Add event error: \(error)")
        }
    }

    func updateEvent(_ event: CalendarEvent, title: String, startAt: Date, endAt: Date?, note: String?) async {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        var payload: [String: String] = [
            "title": title,
            "start_at": formatter.string(from: startAt),
        ]
        if let endAt { payload["end_at"] = formatter.string(from: endAt) }
        if let note { payload["note"] = note }

        do {
            try await supabase
                .from("calendar_events")
                .update(payload)
                .eq("id", value: event.id)
                .execute()
            await fetchAll()
        } catch {
            print("Update event error: \(error)")
        }
    }

    func deleteEvent(_ event: CalendarEvent) async {
        do {
            try await supabase
                .from("calendar_events")
                .delete()
                .eq("id", value: event.id)
                .execute()
            todayEvents.removeAll { $0.id == event.id }
        } catch {
            print("Delete event error: \(error)")
        }
    }

    // MARK: - Reminder CRUD

    func addReminder(content: String) async {
        var payload: [String: String] = [
            "action_type": "reminder",
            "content": content,
        ]
        if let uid = userId { payload["user_id"] = uid }

        do {
            try await supabase
                .from("machine_logs")
                .insert(payload)
                .execute()
            await fetchAll()
        } catch {
            print("Add reminder error: \(error)")
        }
    }

    func deleteReminder(_ log: MachineLog) async {
        do {
            try await supabase
                .from("machine_logs")
                .delete()
                .eq("id", value: log.id)
                .execute()
            reminders.removeAll { $0.id == log.id }
        } catch {
            print("Delete reminder error: \(error)")
        }
    }

    // MARK: - Dismiss Suggestion

    func dismissSuggestion(_ log: MachineLog) async {
        do {
            try await supabase
                .from("machine_logs")
                .delete()
                .eq("id", value: log.id)
                .execute()
            suggestions.removeAll { $0.id == log.id }
        } catch {
            print("Dismiss error: \(error)")
        }
    }
}

private struct SuggestionMeta: Codable {
    let eventTitle: String
    let eventDate: String
    let eventTime: String

    enum CodingKeys: String, CodingKey {
        case eventTitle = "event_title"
        case eventDate = "event_date"
        case eventTime = "event_time"
    }
}
