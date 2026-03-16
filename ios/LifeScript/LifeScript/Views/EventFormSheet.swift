import SwiftUI

struct EventFormSheet: View {
    @EnvironmentObject var dataService: DataService
    @Environment(\.dismiss) private var dismiss

    /// nil なら新規追加、あれば編集
    let editingEvent: CalendarEvent?

    @State private var title: String = ""
    @State private var startDate: Date = Date()
    @State private var hasEndDate: Bool = false
    @State private var endDate: Date = Date().addingTimeInterval(3600)
    @State private var note: String = ""
    @State private var isSaving = false

    var isEditing: Bool { editingEvent != nil }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("タイトル", text: $title)

                    DatePicker("開始", selection: $startDate)

                    Toggle("終了時刻を設定", isOn: $hasEndDate)
                    if hasEndDate {
                        DatePicker("終了", selection: $endDate)
                    }

                    TextField("メモ（任意）", text: $note, axis: .vertical)
                        .lineLimit(3...6)
                }

                if isEditing {
                    Section {
                        Button(role: .destructive) {
                            Task {
                                if let event = editingEvent {
                                    await dataService.deleteEvent(event)
                                }
                                dismiss()
                            }
                        } label: {
                            HStack {
                                Image(systemName: "trash")
                                Text("この予定を削除")
                            }
                        }
                    }
                }
            }
            .navigationTitle(isEditing ? "予定を編集" : "予定を追加")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("キャンセル") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isEditing ? "保存" : "追加") {
                        isSaving = true
                        Task {
                            if let event = editingEvent {
                                await dataService.updateEvent(
                                    event,
                                    title: title,
                                    startAt: startDate,
                                    endAt: hasEndDate ? endDate : nil,
                                    note: note.isEmpty ? nil : note
                                )
                            } else {
                                await dataService.addEvent(
                                    title: title,
                                    startAt: startDate,
                                    endAt: hasEndDate ? endDate : nil,
                                    note: note.isEmpty ? nil : note
                                )
                            }
                            isSaving = false
                            dismiss()
                        }
                    }
                    .disabled(title.trimmingCharacters(in: .whitespaces).isEmpty || isSaving)
                    .bold()
                }
            }
            .onAppear {
                if let event = editingEvent {
                    title = event.title
                    if let d = event.startDate { startDate = d }
                    note = event.note ?? ""
                    if let endStr = event.endAt {
                        let f = ISO8601DateFormatter()
                        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                        if let d = f.date(from: endStr) ?? ISO8601DateFormatter().date(from: endStr) {
                            hasEndDate = true
                            endDate = d
                        }
                    }
                }
            }
        }
    }
}
