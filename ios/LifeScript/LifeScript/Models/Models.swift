import Foundation

struct CalendarEvent: Codable, Identifiable {
    let id: Int
    let title: String
    let startAt: String
    let endAt: String?
    let note: String?
    let source: String

    enum CodingKeys: String, CodingKey {
        case id, title, note, source
        case startAt = "start_at"
        case endAt = "end_at"
    }

    var startDate: Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: startAt)
            ?? ISO8601DateFormatter().date(from: startAt)
    }

    var timeString: String {
        guard let date = startDate else {
            return String(startAt.prefix(16)).replacingOccurrences(of: "T", with: " ")
        }
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return f.string(from: date)
    }

    var dateString: String {
        guard let date = startDate else { return "" }
        let f = DateFormatter()
        f.dateFormat = "M/d"
        return f.string(from: date)
    }
}

struct MachineLog: Codable, Identifiable {
    let id: Int
    let actionType: String
    let content: String
    let triggeredAt: String

    enum CodingKeys: String, CodingKey {
        case id, content
        case actionType = "action_type"
        case triggeredAt = "triggered_at"
    }

    /// メタデータタグを除去した表示用テキスト
    var displayContent: String {
        content.replacingOccurrences(
            of: #"\n<!--meta:.*?-->"#,
            with: "",
            options: .regularExpression
        ).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var timeString: String {
        String(triggeredAt.prefix(16)).replacingOccurrences(of: "T", with: " ")
    }
}
