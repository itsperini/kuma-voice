import SwiftUI

enum DevicePairingState: Equatable {
    case loading
    case waiting(code: String, destination: String)
    case failed(String)
}

@MainActor
final class DevicePairingViewModel: ObservableObject {
    @Published private(set) var isPaired = AppConfiguration.hasAuthorization
    @Published private(set) var state: DevicePairingState = .loading

    private let client = DevicePairingClient()
    private var pairingTask: Task<Void, Never>?

    func start() {
        guard !isPaired, pairingTask == nil else { return }
        state = .loading
        pairingTask = Task { [weak self] in
            guard let self else { return }
            do {
                let authorization = try await client.createAuthorization()
                state = .waiting(
                    code: authorization.userCode,
                    destination: Self.displayDestination(authorization.verificationURI)
                )
                let accessToken = try await client.waitForApproval(authorization)
                try DeviceCredentialStore.save(accessToken)
                isPaired = true
            } catch is CancellationError {
                return
            } catch {
                state = .failed(error.localizedDescription)
            }
            pairingTask = nil
        }
    }

    func retry() {
        pairingTask?.cancel()
        pairingTask = nil
        start()
    }

    private static func displayDestination(_ value: String) -> String {
        guard let url = URL(string: value), let host = url.host else {
            return value
        }
        let port = url.port.map { ":\($0)" } ?? ""
        let path = url.path == "/" ? "" : url.path
        return "\(host)\(port)\(path)"
    }
}

struct DevicePairingView: View {
    @ObservedObject var viewModel: DevicePairingViewModel

    var body: some View {
        VStack(spacing: 8) {
            Image("KumaLogo")
                .resizable()
                .scaledToFit()
                .colorMultiply(ChatTheme.warmWhite)
                .frame(width: 45, height: 38)
                .accessibilityLabel("Kuma")

            switch viewModel.state {
            case .loading:
                Text("Creating your code")
                    .font(.system(size: 12, weight: .semibold, design: .rounded))
                    .foregroundStyle(ChatTheme.warmWhite)
                ProgressView()
                    .tint(ChatTheme.ember)
            case let .waiting(code, destination):
                Text("Pair with Studio")
                    .font(.system(size: 12, weight: .semibold, design: .rounded))
                    .foregroundStyle(ChatTheme.warmWhite)

                Text(code)
                    .font(.system(size: 23, weight: .bold, design: .rounded))
                    .tracking(2)
                    .foregroundStyle(ChatTheme.ember)
                    .accessibilityLabel("Pairing code \(code)")

                Text("Enter at")
                    .font(.system(size: 9, weight: .medium, design: .rounded))
                    .foregroundStyle(ChatTheme.secondary)

                Text(destination)
                    .font(.system(size: 9, weight: .semibold, design: .rounded))
                    .foregroundStyle(ChatTheme.warmWhite)
                    .lineLimit(2)
                    .minimumScaleFactor(0.72)
                    .multilineTextAlignment(.center)

                HStack(spacing: 5) {
                    ProgressView()
                        .controlSize(.mini)
                        .tint(ChatTheme.ember)
                    Text("Waiting for approval")
                        .font(.system(size: 9, design: .rounded))
                        .foregroundStyle(ChatTheme.secondary)
                }
                .padding(.top, 2)
            case let .failed(message):
                Text("Pairing paused")
                    .font(.system(size: 12, weight: .semibold, design: .rounded))
                    .foregroundStyle(ChatTheme.warmWhite)
                Text(message)
                    .font(.system(size: 9, design: .rounded))
                    .foregroundStyle(ChatTheme.secondary)
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
                Button("Try again") {
                    viewModel.retry()
                }
                .buttonStyle(.borderedProminent)
                .tint(ChatTheme.clay)
            }
        }
        .padding(.horizontal, 13)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(ChatTheme.background.ignoresSafeArea())
        .preferredColorScheme(.dark)
        .task {
            viewModel.start()
        }
    }
}

private enum ChatTheme {
    static let background = Color.black
    static let night = Color(red: 36.0 / 255.0, green: 24.0 / 255.0, blue: 20.0 / 255.0)
    static let cocoa = Color(red: 56.0 / 255.0, green: 32.0 / 255.0, blue: 23.0 / 255.0)
    static let clay = Color(red: 138.0 / 255.0, green: 75.0 / 255.0, blue: 50.0 / 255.0)
    static let ember = Color(red: 241.0 / 255.0, green: 120.0 / 255.0, blue: 63.0 / 255.0)
    static let emberDeep = Color(red: 217.0 / 255.0, green: 91.0 / 255.0, blue: 37.0 / 255.0)
    static let warmWhite = Color(red: 1.0, green: 246.0 / 255.0, blue: 240.0 / 255.0)
    static let secondary = Color(red: 169.0 / 255.0, green: 150.0 / 255.0, blue: 140.0 / 255.0)
    static let assistantText = warmWhite
    static let userText = warmWhite.opacity(0.96)

    static let userBubble = LinearGradient(
        colors: [cocoa, clay.opacity(0.78)],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
}

struct ContentView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @StateObject private var viewModel = VoiceConversationViewModel()
    @State private var confirmResetConversation = false

    var body: some View {
        Group {
            if viewModel.messages.isEmpty {
                emptyState
            } else {
                conversationHistory
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(ChatTheme.background.ignoresSafeArea())
        .safeAreaInset(edge: .bottom, spacing: 0) {
            bottomBar
        }
        .preferredColorScheme(.dark)
        .confirmationDialog(
            "Are you sure you want to delete the conversation?",
            isPresented: $confirmResetConversation,
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) {
                viewModel.resetConversation()
            }
            Button("Cancel", role: .cancel) {}
        }
    }

    private var conversationHistory: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(viewModel.messages) { message in
                        messageRow(message)
                            .id(message.id)
                    }
                }
                .padding(.horizontal, 10)
                .padding(.top, 4)
                .padding(.bottom, 8)

                Color.clear
                    .frame(height: 1)
                    .id(ChatScrollAnchor.bottom)
            }
            .modifier(PinChatToBottom())
            .onChange(of: viewModel.latestScrollToken) { _, _ in
                DispatchQueue.main.async {
                    proxy.scrollTo(ChatScrollAnchor.bottom, anchor: .bottom)
                }
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 9) {
            Spacer(minLength: 0)
            Image("KumaLogo")
                .resizable()
                .scaledToFit()
                .colorMultiply(ChatTheme.warmWhite)
                .frame(width: 56, height: 50)
                .shadow(color: ChatTheme.clay.opacity(0.32), radius: 10, y: 4)
                .accessibilityLabel("Kuma")

            Text("Tap or Double Tap to talk")
                .font(.system(size: 11, weight: .medium, design: .rounded))
                .foregroundStyle(ChatTheme.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 12)
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    @ViewBuilder
    private func messageRow(_ message: ChatMessage) -> some View {
        if message.role == .user {
            VStack(alignment: .trailing, spacing: 3) {
                messageLabel("You", color: ChatTheme.secondary)

                Text(displayText(for: message))
                    .font(.system(size: 14, weight: .regular))
                    .foregroundStyle(ChatTheme.userText)
                    .multilineTextAlignment(.trailing)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .fill(ChatTheme.userBubble)
                            .overlay(
                                RoundedRectangle(cornerRadius: 14, style: .continuous)
                                    .stroke(ChatTheme.clay.opacity(0.42), lineWidth: 0.5)
                            )
                    )
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
        } else {
            VStack(alignment: .leading, spacing: 4) {
                messageLabel("Kuma", color: ChatTheme.ember)

                Text(displayText(for: message))
                    .font(.system(size: 14, weight: .regular))
                    .foregroundStyle(ChatTheme.assistantText)
                    .multilineTextAlignment(.leading)
                    .padding(.horizontal, 2)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private func messageLabel(_ title: String, color: Color) -> some View {
        Text(title)
            .font(.system(size: 11, weight: .semibold, design: .rounded))
            .foregroundStyle(color)
    }

    private func displayText(for message: ChatMessage) -> String {
        let trimmed = message.text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            return viewModel.state == .speaking ? "…" : " "
        }
        return trimmed
    }

    private var handGestureEnabled: Bool {
        switch viewModel.state {
        case .ready, .listening, .failed, .sending, .speaking:
            return true
        case .connecting:
            return false
        }
    }

    private var primaryButtonFill: LinearGradient {
        switch viewModel.state {
        case .listening:
            return LinearGradient(
                colors: [ChatTheme.ember, ChatTheme.emberDeep],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        case .speaking:
            return LinearGradient(
                colors: [ChatTheme.clay, ChatTheme.emberDeep],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        case .connecting, .sending:
            return LinearGradient(
                colors: [ChatTheme.cocoa, ChatTheme.clay],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        case .ready, .failed:
            return LinearGradient(
                colors: [ChatTheme.night, ChatTheme.clay.opacity(0.82)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        }
    }

    private var showsVoiceHalo: Bool {
        viewModel.state == .listening || viewModel.state == .speaking
    }

    private var bottomBar: some View {
        HStack(spacing: 10) {
            if !viewModel.messages.isEmpty {
                resetButton
            }
            speakButton
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 4)
        .padding(.bottom, 2)
    }

    private var resetButton: some View {
        Button {
            confirmResetConversation = true
        } label: {
            ZStack {
                Circle()
                    .fill(ChatTheme.night)
                    .overlay(
                        Circle()
                            .stroke(ChatTheme.clay.opacity(0.38), lineWidth: 0.75)
                    )
                    .frame(width: 42, height: 42)

                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(ChatTheme.secondary)
            }
            .frame(width: 52, height: 52)
            .contentShape(Circle())
        }
        .buttonStyle(KumaPlainCircleButtonStyle(pressedScale: 0.97))
        .contentShape(Circle())
        .accessibilityLabel("Delete conversation")
    }

    private var speakButton: some View {
        ZStack {
            if showsVoiceHalo {
                VoiceActivityHalo(
                    level: viewModel.inputLevel,
                    isSpeaking: viewModel.state == .speaking
                )
                .transition(.opacity)
            }

            Button(action: viewModel.buttonTapped) {
                speakGlyph
                    .foregroundStyle(ChatTheme.warmWhite)
                    .frame(width: 50, height: 50)
                    .background(
                        Circle()
                            .fill(primaryButtonFill)
                            .overlay(
                                Circle()
                                    .stroke(ChatTheme.warmWhite.opacity(0.18), lineWidth: 0.75)
                            )
                            .shadow(
                                color: ChatTheme.emberDeep.opacity(
                                    showsVoiceHalo ? 0.34 : 0.14
                                ),
                                radius: showsVoiceHalo ? 9 : 4,
                                y: 3
                            )
                    )
            }
            .buttonStyle(KumaPlainCircleButtonStyle())
            .contentShape(Circle())
            .id("kuma-speak")
            .modifier(
                PrimaryActionShortcut(
                    isEnabled: handGestureEnabled && !confirmResetConversation
                )
            )
            .accessibilityLabel(viewModel.buttonAccessibilityLabel)
        }
        .frame(width: 58, height: 58)
        .animation(
            reduceMotion ? nil : .easeInOut(duration: 0.22),
            value: showsVoiceHalo
        )
    }

    @ViewBuilder
    private var speakGlyph: some View {
        switch viewModel.state {
        case .ready, .failed, .speaking:
            Image(systemName: "mic.fill")
                .font(.system(size: 17, weight: .semibold))
        case .connecting:
            ProgressView()
                .progressViewStyle(.circular)
                .tint(ChatTheme.warmWhite)
        case .sending:
            Image(systemName: "ellipsis")
                .font(.system(size: 16, weight: .bold))
        case .listening:
            RoundedRectangle(cornerRadius: 4, style: .continuous)
                .fill(ChatTheme.warmWhite)
                .frame(width: 14, height: 14)
        }
    }
}

private struct KumaPlainCircleButtonStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var pressedScale: CGFloat = 0.92

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(
                configuration.isPressed && !reduceMotion ? pressedScale : 1
            )
            .brightness(configuration.isPressed ? 0.08 : 0)
            .animation(
                reduceMotion ? nil : .easeOut(duration: 0.12),
                value: configuration.isPressed
            )
    }
}

private struct VoiceActivityHalo: View {
    let level: Float
    let isSpeaking: Bool

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var breathing = false

    private var energy: CGFloat {
        if isSpeaking {
            return reduceMotion ? 0.45 : (breathing ? 1 : 0.32)
        }
        return max(0.18, min(1, CGFloat(level)))
    }

    var body: some View {
        ZStack {
            Circle()
                .fill(ChatTheme.ember.opacity(0.10))
                .frame(width: 56, height: 56)
                .scaleEffect(1 + (energy * 0.18))

            Circle()
                .stroke(ChatTheme.ember.opacity(0.34), lineWidth: 1.5)
                .frame(width: 54, height: 54)
                .scaleEffect(1 + (energy * 0.12))
        }
        .animation(.linear(duration: 0.08), value: level)
        .animation(
            reduceMotion
                ? .default
                : .easeInOut(duration: 0.9).repeatForever(autoreverses: true),
            value: breathing
        )
        .onAppear {
            breathing = isSpeaking && !reduceMotion
        }
        .onChange(of: isSpeaking) { _, speaking in
            breathing = speaking && !reduceMotion
        }
    }
}

/// Native Watch buttons keep a real interaction view for Double Tap.
private struct PrimaryActionShortcut: ViewModifier {
    var isEnabled: Bool

    func body(content: Content) -> some View {
        if #available(watchOS 11.0, *) {
            content.handGestureShortcut(.primaryAction, isEnabled: isEnabled)
        } else {
            content
        }
    }
}

private enum ChatScrollAnchor {
    static let bottom = "chat-bottom"
}

private struct PinChatToBottom: ViewModifier {
    func body(content: Content) -> some View {
        if #available(watchOS 11.0, *) {
            content.defaultScrollAnchor(.bottom)
        } else {
            content
        }
    }
}
