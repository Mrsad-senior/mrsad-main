-- Usage: osascript scripts/keynote_export.applescript /abs/path/in.pptx /abs/path/out.pdf
-- Opens a PowerPoint file in Keynote and exports it to PDF (used for previews when PowerPoint automation hangs).
on run argv
	set srcPath to item 1 of argv
	set pdfPath to item 2 of argv
	with timeout of 1200 seconds
		tell application "Keynote"
			set theDoc to open (POSIX file srcPath)
			delay 2
			export theDoc to (POSIX file pdfPath) as PDF with properties {PDF image quality:Best}
			close theDoc saving no
		end tell
	end timeout
	return "exported " & pdfPath
end run
