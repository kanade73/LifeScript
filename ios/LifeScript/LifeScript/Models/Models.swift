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
        bodyContent
    }

    /// 本文（理由・メタタグを除去）
    var bodyContent: String {
        var text = content
        // メタタグ除去
        text = text.replacingOccurrences(of: #"\n<!--meta:.*?-->"#, with: "", options: .regularExpression)
        // 理由行を除去
        if let range = text.range(of: #"\n理由: .*"#, options: .regularExpression) {
            text = String(text[text.startIndex..<range.lowerBound])
        }
        return text.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// 提案の理由（あれば）
    var reason: String? {
        guard let range = content.range(of: #"(?<=\n理由: ).*"#, options: .regularExpression) else {
            return nil
        }
        let r = String(content[range]).trimmingCharacters(in: .whitespacesAndNewlines)
        return r.isEmpty ? nil : r
    }

    /// メタデータからtype（calendar/notify）を取得
    var suggestionType: String {
        guard let range = content.range(of: #"(?<=<!--meta:).*?(?=-->)"#, options: .regularExpression),
              let data = String(content[range]).data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else {
            return "calendar"
        }
        return type
    }

    var timeString: String {
        String(triggeredAt.prefix(16)).replacingOccurrences(of: "T", with: " ")
    }
}
