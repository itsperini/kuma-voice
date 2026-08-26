import AVFoundation
import Foundation

enum AudioRecorderError: LocalizedError {
    case permissionDenied
    case couldNotStart
    case notRecording

    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "Microphone permission is required."
        case .couldNotStart:
            return "The Watch could not start recording."
        case .notRecording:
            return "No recording is currently active."
        }
    }
}

@MainActor
final class AudioRecorder: NSObject {
    private var recorder: AVAudioRecorder?
    private var recordingURL: URL?

    func start() async throws {
        let permissionGranted = await requestPermission()
        guard permissionGranted else {
            throw AudioRecorderError.permissionDenied
        }

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .voiceChat)
        try session.setActive(true)

        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("kuma-\(UUID().uuidString)")
            .appendingPathExtension("m4a")

        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatMPEG4AAC,
            AVSampleRateKey: 16_000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue,
        ]

        let recorder = try AVAudioRecorder(url: url, settings: settings)
        recorder.prepareToRecord()
        guard recorder.record() else {
            throw AudioRecorderError.couldNotStart
        }

        self.recorder = recorder
        recordingURL = url
    }

    func stop() throws -> URL {
        guard let recorder, let recordingURL else {
            throw AudioRecorderError.notRecording
        }
        recorder.stop()
        self.recorder = nil
        self.recordingURL = nil
        return recordingURL
    }

    private func requestPermission() async -> Bool {
        await withCheckedContinuation { continuation in
            AVAudioApplication.requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }
    }
}

