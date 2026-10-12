// Offscreen render of Panely's real Settings view (SwiftUI) into PNG files. Never shows a window, never reads the real
// preferences: it refuses to run unless HOME points into a temp directory. Compiled together with copies of the app's
// own source files by render.sh (the app's Sources/ folder is not touched).
import AppKit
import SwiftUI

let env = ProcessInfo.processInfo.environment
guard let home = env["CFFIXED_USER_HOME"], home.contains("panely-fakehome") else { print("refusing: CFFIXED_USER_HOME must be a panely-fakehome temp dir"); exit(2) }
guard let outDir = env["PANELY_OUT"] else { print("PANELY_OUT missing"); exit(2) }

NSApplication.shared.setActivationPolicy(.prohibited)

// Invented sample data: three custom areas, one changed shortcut, a few ignored apps (bundle ids of well known apps).
var s = PanelySettings()
s.gap = 8; s.outer = 8
s.customAreas = [
    CustomArea(name: "Reading column", rect: NormalizedRect(x: 0.2, y: 0, width: 0.6, height: 1), shortcut: HotKeySpec(keyCode: 18, modifiers: HotKeySpec.control | HotKeySpec.option | HotKeySpec.shift)),
    CustomArea(name: "Notes strip", rect: NormalizedRect(x: 0.7, y: 0.1, width: 0.3, height: 0.8), shortcut: nil),
    CustomArea(name: "Video call", rect: NormalizedRect(x: 0.55, y: 0.55, width: 0.45, height: 0.45), shortcut: nil),
]
s.ignoredApps = ["com.apple.FaceTime", "us.zoom.xos"]
UserDefaults.standard.set(try! JSONEncoder().encode(s), forKey: "panely.settings.v1")

func render(_ name: String, size: NSSize, appearance: NSAppearance.Name) {
    let store = SettingsStore()
    let view = SettingsView(store: store, license: { "Trial: 5 days left" }, enterLicense: {}, openDesktopAndDock: {}, nativeTilingOn: false)
        .frame(width: size.width, height: size.height)
        .environment(\.controlActiveState, .key)
    let host = NSHostingView(rootView: view)
    host.frame = NSRect(origin: .zero, size: size)
    let win = NSWindow(contentRect: host.frame, styleMask: [.titled], backing: .buffered, defer: false)
    win.appearance = NSAppearance(named: appearance)
    win.contentView = host
    win.setFrame(NSRect(x: -20000, y: -20000, width: size.width, height: size.height + 28), display: false)   // never ordered in, parked far off any screen
    for _ in 0..<6 { host.layoutSubtreeIfNeeded(); RunLoop.current.run(until: Date().addingTimeInterval(0.25)) }
    guard let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { print("no rep"); return }
    host.cacheDisplay(in: host.bounds, to: rep)
    let scale = 2
    // upscale to 2x by re-rendering with a 2x bitmap
    let pw = Int(size.width) * scale, ph = Int(size.height) * scale
    let rep2 = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pw, pixelsHigh: ph, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    rep2.size = size
    host.cacheDisplay(in: host.bounds, to: rep2)
    try! rep2.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "\(outDir)/\(name).png"))
    print("wrote \(name).png \(pw)x\(ph)")
}

let mode = env["PANELY_MODE"] ?? "full"
let ap: NSAppearance.Name = (env["PANELY_APPEARANCE"] ?? "light") == "dark" ? .darkAqua : .aqua
render(mode, size: NSSize(width: 540, height: Double(env["PANELY_H"] ?? "3000")!), appearance: ap)
