import AVFoundation
import Foundation

final class AudioPlaybackController: NSObject, AVAudioPlayerDelegate {
    private var player: AVAudioPlayer?
    var didFinish: (() -> Void)?

    func play(data: Data) throws {
        let player = try AVAudioPlayer(data: data)
        player.delegate = self
        player.prepareToPlay()
        guard player.play() else {
            throw AudioRecorderError.couldNotStart
        }
        self.player = player
    }

    func stop() {
        player?.stop()
        player = nil
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        self.player = nil
        didFinish?()
    }
}

