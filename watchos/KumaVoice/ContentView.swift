import SwiftUI

private enum ChatTheme {
    static let background = Color.black
    static let assistantText = Color.white
    static let userText = Color.white.opacity(0.92)
    static let secondary = Color(white: 0.62)
    static let bubble = Color(red: 0.18, green: 0.18, blue: 0.18)
    static let button = Color(white: 0.34)
    static let buttonPressed = Color(white: 0.52)
}

struct ContentView: View {
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
                VStack(alignment: .leading, spacing: 10) {
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
        VStack(spacing: 8) {
            Spacer(minLength: 0)
            Image("KumaLogo")
                .resizable()
                .scaledToFit()
                .frame(width: 52, height: 48)
                .accessibilityLabel("Kuma")

            Text("Tap or Double Tap to chat")
                .font(.caption2)
                .foregroundStyle(ChatTheme.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 12)
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func messageRow(_ message: ChatMessage) -> some View {
        VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 3) {
            Text(message.role == .user ? "You" : "Kuma")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(ChatTheme.secondary)

            Text(displayText(for: message))
                .font(.system(size: 14, weight: .regular))
                .foregroundStyle(
                    message.role == .user ? ChatTheme.userText : ChatTheme.assistantText
                )
                .multilineTextAlignment(message.role == .user ? .trailing : .leading)
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
                .background(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .fill(ChatTheme.bubble)
                )
                .frame(
                    maxWidth: .infinity,
                    alignment: message.role == .user ? .trailing : .leading
                )
        }
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

    private var buttonFill: Color {
        switch viewModel.state {
        case .connecting, .sending:
            return ChatTheme.buttonPressed
        case .ready, .failed, .speaking, .listening:
            return ChatTheme.button
        }
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
            Image(systemName: "arrow.clockwise")
                .font(.system(size: 17, weight: .semibold))
                .frame(width: 22, height: 22)
        }
        .buttonStyle(.borderedProminent)
        .buttonBorderShape(.circle)
        .tint(ChatTheme.button)
        .clipShape(Circle())
        .accessibilityLabel("Delete conversation")
    }

    private var speakButton: some View {
        Button(action: viewModel.buttonTapped) {
            speakGlyph
                .frame(width: 22, height: 22)
        }
        .buttonStyle(.borderedProminent)
        .buttonBorderShape(.circle)
        .tint(buttonFill)
        .clipShape(Circle())
        .id("kuma-speak")
        .modifier(
            PrimaryActionShortcut(
                isEnabled: handGestureEnabled && !confirmResetConversation
            )
        )
        .accessibilityLabel(viewModel.buttonAccessibilityLabel)
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
                .tint(.white)
        case .sending:
            Image(systemName: "ellipsis")
                .font(.system(size: 16, weight: .bold))
        case .listening:
            RoundedRectangle(cornerRadius: 4, style: .continuous)
                .fill(.white)
                .frame(width: 14, height: 14)
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
