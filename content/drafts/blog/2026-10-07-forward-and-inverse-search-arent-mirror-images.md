# Forward and inverse search aren't mirror images

A synced PDF preview needs two separate pieces of code, not one run backward. Click your LaTeX source and the PDF scrolls to match; click the PDF and the cursor moves to match in the source. Those look like the same feature pointed in opposite directions. Building them turned out to be two different problems, and ModernTex shipped one of them wrong before getting it right.

ModernTex calls this forward and inverse search. Double-click a word in the editor and the PDF scrolls to the matching spot. Command-click a word in the PDF and the cursor lands on it in the source. The mechanism underneath, SyncTeX, is a convention most LaTeX tools share. A compile run writes a map between byte positions in your .tex files and rectangles on PDF pages. Reading that map in each direction is where the symmetry stops.

Forward search, source to PDF, is a scrolling problem and nothing more. SyncTeX hands back a page and a rectangle on it, and the PDF view just has to bring that rectangle into frame. There's no second piece of state, because scrolling is the only thing a read-only preview does.

Inverse search, PDF to source, is a cursor problem, and a cursor has two jobs where a scroll position has one. SyncTeX returns a line in a source file. The editor converts that into a character position, places the insertion point there, and then has to scroll its own view so the spot is actually visible. ModernTex 1.3.3 shipped the first two steps and skipped the third. The cursor moved to the right place every time. If that place was off-screen, which it usually is past page one, nothing appeared to happen. The state was correct. The screen wasn't, and from the chair in front of it, those are the same bug.

The fix, in 1.3.4, was one added call: after moving the cursor, scroll to reveal it. Not a redesign. What's worth sitting with is why it slipped through. Moving a cursor and scrolling a view are different calls on different objects. It's easy to write the one that changes correctness while skipping the one that changes what's on screen. Checking the cursor's reported position, the fast way to test it, would have shown everything working. Only watching the window would have shown the gap. Forward search never had this trap, because a PDF preview has nothing to get right beyond where it scrolled to.

None of this is specific to ModernTex. Any editor that promises two-way sync between a markup source and its compiled output inherits the same asymmetry: one direction is pure positioning, the other is positioning plus visibility. The LaTeX editors available on Mac handle it with varying completeness. That's part of what separates a desktop editor from a browser-based one like Overleaf, where the document is already rendered and sync is a smaller leap. The changelog entry for 1.3.4 is one sentence. Getting there meant noticing that the bug report and the code both looked fine, and only the window didn't.

Further reading: The LaTeX Companion covers the packages and conventions that SyncTeX and most editors build around. Guide to LaTeX is a slower, more complete path through the same material. There are more books on the research desk.

Disclosure: the Amazon links above are affiliate links. As an Amazon Associate I earn from qualifying purchases.

If you write LaTeX on a Mac, ModernTex is a free 7-day trial, then $19.99 once to keep, with all updates included.

## Screenshots to capture

- Double-clicking a word in the ModernTex editor, with the PDF scrolling to show the matching spot.
- Command-clicking a word in the ModernTex PDF preview, with the cursor landing in the source.
- The 1.3.4 changelog entry for the fix.

---

## LinkedIn Post

Clicking a PDF to jump back to your LaTeX source looks like the mirror image of clicking the source to jump to the PDF. It is not, and a bug in ModernTex showed why.

Moving a cursor to the right line is only half the job. If that line is off-screen, which it usually is past page one, nothing visible happens, even though the cursor moved correctly. ModernTex 1.3.3 shipped exactly that gap: the state was right, the screen was not, and from the chair in front of it those are the same bug. The fix was one line. Finding it took noticing that the bug report and the code both looked fine, and only the window did not.

The deeper reason is that a scroll position and a cursor are different kinds of state. Jumping from source to PDF only ever has to scroll. Jumping from PDF to source has to move a cursor and then scroll to prove it. Any editor syncing a markup source to its rendered output runs into the same asymmetry.

More on what that bug looked like and how SyncTeX makes the sync possible at all: https://purplelink.llc/blog/forward-and-inverse-search-arent-mirror-images/
