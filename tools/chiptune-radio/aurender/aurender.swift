// aurender: plays one sampled instrument (.exs) dry and writes raw float32 stereo (planar: all left, then all right).
// Usage: aurender job.json out.f32
// job.json: {"sr": 44100, "frames": N, "exs": "/abs/path.exs", "events": [[frame, status, data1, data2], ...]} sorted by frame.
// Events are raw MIDI (0x90 note-on, 0x80 note-off) scheduled at their exact sample inside each render block.
// Exits non-zero on any failure; never writes a short file.
import AVFoundation
import Foundation

struct Job: Decodable { let sr: Double; let frames: Int; let exs: String; let events: [[Int]] }
func fail(_ m: String) -> Never { FileHandle.standardError.write((m + "\n").data(using: .utf8)!); exit(1) }

let a = CommandLine.arguments
guard a.count == 3 else { fail("usage: aurender job.json out.f32") }
guard let data = FileManager.default.contents(atPath: a[1]), let job = try? JSONDecoder().decode(Job.self, from: data) else { fail("bad job file") }
guard FileManager.default.fileExists(atPath: job.exs) else { fail("missing instrument \(job.exs)") }

let engine = AVAudioEngine()
let sampler = AVAudioUnitSampler()
engine.attach(sampler)
let fmt = AVAudioFormat(standardFormatWithSampleRate: job.sr, channels: 2)!
engine.connect(sampler, to: engine.mainMixerNode, format: fmt)
let block: AVAudioFrameCount = 512
do { try engine.enableManualRenderingMode(.offline, format: fmt, maximumFrameCount: block) } catch { fail("manual mode: \(error)") }
// Load every sample into memory. By default the sampler streams long samples from disk on a background thread, and an offline
// render runs faster than that thread can keep up: notes then come out partly silent, differently on every run.
var noStream: UInt32 = 0
let ps = AudioUnitSetProperty(sampler.audioUnit, kMusicDeviceProperty_StreamFromDisk, kAudioUnitScope_Global, 0, &noStream, UInt32(MemoryLayout<UInt32>.size))
if ps != noErr { fail("stream-from-disk off: OSStatus \(ps)") }
do { try sampler.loadInstrument(at: URL(fileURLWithPath: job.exs)) } catch { fail("load \(job.exs): \(error)") }
do { try engine.start() } catch { fail("start: \(error)") }
guard let midi = sampler.auAudioUnit.scheduleMIDIEventBlock else { fail("no MIDI block") }

let buf = AVAudioPCMBuffer(pcmFormat: engine.manualRenderingFormat, frameCapacity: block)!
var left = [Float](repeating: 0, count: job.frames), right = [Float](repeating: 0, count: job.frames)
var pos = 0, ei = 0
while pos < job.frames {
  let n = min(Int(block), job.frames - pos)
  while ei < job.events.count && job.events[ei][0] < pos + n {
    let e = job.events[ei]; let off = max(0, e[0] - pos)
    var bytes: [UInt8] = [UInt8(e[1] & 0xFF), UInt8(e[2] & 0x7F), UInt8(e[3] & 0x7F)]
    midi(AUEventSampleTimeImmediate + AUEventSampleTime(off), 0, 3, &bytes)
    ei += 1
  }
  let st: AVAudioEngineManualRenderingStatus
  do { st = try engine.renderOffline(AVAudioFrameCount(n), to: buf) } catch { fail("render: \(error)") }
  guard st == .success, Int(buf.frameLength) == n else { fail("render status \(st.rawValue) at frame \(pos)") }
  let l = buf.floatChannelData![0], r = buf.floatChannelData![1]
  for i in 0..<n { left[pos + i] = l[i]; right[pos + i] = r[i] }
  pos += n
}
let out = FileManager.default.createFile(atPath: a[2], contents: nil)
guard out, let fh = FileHandle(forWritingAtPath: a[2]) else { fail("cannot write \(a[2])") }
left.withUnsafeBufferPointer { fh.write(Data(buffer: $0)) }
right.withUnsafeBufferPointer { fh.write(Data(buffer: $0)) }
fh.closeFile()
