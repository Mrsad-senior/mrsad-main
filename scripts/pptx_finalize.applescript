-- Usage: osascript scripts/pptx_finalize.applescript /abs/path/in.pptx /abs/path/out.pdf
-- Exports a PowerPoint file to PDF. PowerPoint is sandboxed, so the export runs on a copy inside its container.
on run argv
	set srcPath to item 1 of argv
	set pdfPath to item 2 of argv
	set workDir to (POSIX path of (path to home folder)) & "Library/Containers/com.microsoft.Powerpoint/Data/Documents/mirsad_export/"
	do shell script "mkdir -p " & quoted form of workDir
	set workPptx to workDir & "work.pptx"
	set workPdf to workDir & "work.pdf"
	do shell script "rm -f " & quoted form of workPdf & "; cp -f " & quoted form of srcPath & " " & quoted form of workPptx
	with timeout of 1800 seconds
		tell application "Microsoft PowerPoint"
			open (POSIX file workPptx)
			set waited to 0
			repeat while (count of presentations) is 0 and waited < 60
				delay 1
				set waited to waited + 1
			end repeat
			set thePres to active presentation
			save thePres in ((POSIX file workPdf) as text) as save as PDF
			close thePres saving no
		end tell
	end timeout
	do shell script "mv -f " & quoted form of workPdf & " " & quoted form of pdfPath
	return "exported " & pdfPath
end run
