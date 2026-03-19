import Foundation
import UIKit
import HealthKit

@MainActor
class DeviceService: ObservableObject {
    @Published var batteryLevel: Float = -1
    @Published var batteryState: UIDevice.BatteryState = .unknown
    @Published var screenBrightness: CGFloat = 0
    @Published var todaySteps: Int = 0
    @Published var lastSleepHours: Double? = nil
    @Published var healthAvailable = false

    private let healthStore = HKHealthStore()

    init() {
        UIDevice.current.isBatteryMonitoringEnabled = true
        healthAvailable = HKHealthStore.isHealthDataAvailable()
    }

    func fetchAll() async {
        fetchBattery()
        fetchBrightness()
        if healthAvailable {
            await requestHealthPermission()
            await fetchSteps()
            await fetchSleep()
        }
    }

    // MARK: - Battery

    func fetchBattery() {
        batteryLevel = UIDevice.current.batteryLevel
        batteryState = UIDevice.current.batteryState
    }

    var batteryPercent: Int {
        batteryLevel < 0 ? 0 : Int(batteryLevel * 100)
    }

    var batteryIcon: String {
        switch batteryState {
        case .charging, .full:
            return "battery.100.bolt"
        default:
            if batteryPercent > 75 { return "battery.100" }
            if batteryPercent > 50 { return "battery.75" }
            if batteryPercent > 25 { return "battery.50" }
            return "battery.25"
        }
    }

    var batteryColor: String {
        if batteryState == .charging || batteryState == .full { return "00C875" }
        if batteryPercent > 50 { return "00C875" }
        if batteryPercent > 20 { return "FFA500" }
        return "FF7575"
    }

    // MARK: - Screen Brightness

    func fetchBrightness() {
        screenBrightness = UIScreen.main.brightness
    }

    var brightnessPercent: Int {
        Int(screenBrightness * 100)
    }

    // MARK: - HealthKit Permission

    private func requestHealthPermission() async {
        let types: Set<HKObjectType> = [
            HKQuantityType(.stepCount),
            HKCategoryType(.sleepAnalysis),
        ]
        do {
            try await healthStore.requestAuthorization(toShare: [], read: types)
        } catch {
            print("HealthKit auth error: \(error)")
        }
    }

    // MARK: - Steps

    private func fetchSteps() async {
        let stepsType = HKQuantityType(.stepCount)
        let now = Date()
        let startOfDay = Calendar.current.startOfDay(for: now)
        let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: now, options: .strictStartDate)

        do {
            let result = try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Double, Error>) in
                let query = HKStatisticsQuery(
                    quantityType: stepsType,
                    quantitySamplePredicate: predicate,
                    options: .cumulativeSum
                ) { _, statistics, error in
                    if let error {
                        continuation.resume(throwing: error)
                    } else {
                        let steps = statistics?.sumQuantity()?.doubleValue(for: .count()) ?? 0
                        continuation.resume(returning: steps)
                    }
                }
                healthStore.execute(query)
            }
            todaySteps = Int(result)
        } catch {
            print("Steps fetch error: \(error)")
            todaySteps = 0
        }
    }

    // MARK: - Sleep

    private func fetchSleep() async {
        let sleepType = HKCategoryType(.sleepAnalysis)
        let now = Date()
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Calendar.current.startOfDay(for: now))!
        let predicate = HKQuery.predicateForSamples(withStart: yesterday, end: now, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)

        do {
            let result = try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Double?, Error>) in
                let query = HKSampleQuery(
                    sampleType: sleepType,
                    predicate: predicate,
                    limit: HKObjectQueryNoLimit,
                    sortDescriptors: [sortDescriptor]
                ) { _, samples, error in
                    if let error {
                        continuation.resume(throwing: error)
                    } else {
                        guard let samples = samples as? [HKCategorySample] else {
                            continuation.resume(returning: nil)
                            return
                        }
                        // asleepの合計時間を計算
                        let asleepValues: Set<Int> = [
                            HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue,
                            HKCategoryValueSleepAnalysis.asleepCore.rawValue,
                            HKCategoryValueSleepAnalysis.asleepDeep.rawValue,
                            HKCategoryValueSleepAnalysis.asleepREM.rawValue,
                        ]
                        let totalSeconds = samples
                            .filter { asleepValues.contains($0.value) }
                            .reduce(0.0) { $0 + $1.endDate.timeIntervalSince($1.startDate) }
                        continuation.resume(returning: totalSeconds > 0 ? totalSeconds / 3600.0 : nil)
                    }
                }
                healthStore.execute(query)
            }
            lastSleepHours = result
        } catch {
            print("Sleep fetch error: \(error)")
            lastSleepHours = nil
        }
    }
}
