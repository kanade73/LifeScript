import SwiftUI

struct NotificationsTab: View {
    @EnvironmentObject var dataService: DataService

    var body: some View {
        NavigationStack {
            List {
                if dataService.notifications.isEmpty {
                    ContentUnavailableView(
                        "通知なし",
                        systemImage: "bell.slash",
                        description: Text("マシンからの通知はまだありません")
                    )
                } else {
                    ForEach(dataService.notifications) { log in
                        NotificationRow(log: log)
                    }
                }
            }
            .listStyle(.plain)
            .background(Color(hex: "F2F0EB"))
            .navigationTitle("通知")
            .navigationBarTitleDisplayMode(.inline)
            .refreshable {
                await dataService.fetchAll()
            }
        }
    }
}

struct NotificationRow: View {
    let log: MachineLog

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(iconColor.opacity(0.15))
                    .frame(width: 36, height: 36)
                Image(systemName: iconName)
                    .font(.system(size: 15))
                    .foregroundColor(iconColor)
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(log.displayContent)
                    .font(.system(size: 14))
                    .foregroundColor(Color(hex: "2D2B27"))
                    .lineLimit(3)
                Text(log.timeString)
                    .font(.system(size: 11))
                    .foregroundColor(Color(hex: "A09A93"))
            }
        }
        .padding(.vertical, 4)
    }

    private var iconName: String {
        log.actionType == "notify" ? "bell.badge.fill" : "clock.fill"
    }

    private var iconColor: Color {
        log.actionType == "notify" ? Color(hex: "00C875") : Color(hex: "4262FF")
    }
}
