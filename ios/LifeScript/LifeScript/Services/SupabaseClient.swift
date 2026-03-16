import Foundation
import Supabase

/// Supabase クライアントのシングルトン
enum SupabaseConfig {
    static let url = URL(string: "https://qppfxzciycoawzreucze.supabase.co")!
    static let anonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFwcGZ4emNpeWNvYXd6cmV1Y3plIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTIwMjYsImV4cCI6MjA4ODcyODAyNn0.cJsm8TEus5-C4QgkSZ8Yrc4k6aUZVlFlbNwKkohKJHk"
}

let supabase = SupabaseClient(
    supabaseURL: SupabaseConfig.url,
    supabaseKey: SupabaseConfig.anonKey
)
