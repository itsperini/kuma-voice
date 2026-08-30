import SwiftUI

@main
struct KumaVoiceApp: App {
    @StateObject private var pairing = DevicePairingViewModel()

    var body: some Scene {
        WindowGroup {
            if pairing.isPaired {
                ContentView()
            } else {
                DevicePairingView(viewModel: pairing)
            }
        }
    }
}
