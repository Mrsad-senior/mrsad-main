-- Usage: osascript scripts/word_finalize.applescript /abs/path/in.docx /abs/path/out.pdf
-- Opens the document in Microsoft Word, updates every table of contents / list of figures / list of
-- tables, saves the .docx and exports a PDF. Word is sandboxed, so the work happens on a copy inside
-- Word's own container (no file-access prompts) and the results are copied back.
-- Each document gets its own working-copy name, and documents Word restored at launch are closed first:
-- otherwise a restored window with the same path would be processed instead of the fresh copy.
on run argv
	set docPath to item 1 of argv
	set pdfPath to item 2 of argv
	set baseName to do shell script "basename " & quoted form of docPath & " .docx"
	set exportDir to (POSIX path of (path to home folder)) & "Library/Containers/com.microsoft.Word/Data/Documents/mirsad_export/"
	do shell script "mkdir -p " & quoted form of exportDir
	set workDoc to exportDir & baseName & "-work.docx"
	set workPdf to exportDir & baseName & "-work.pdf"
	do shell script "rm -f " & quoted form of workPdf & "; cp -f " & quoted form of docPath & " " & quoted form of workDoc
	set docAlias to (POSIX file workDoc) as alias
	with timeout of 3600 seconds
		tell application "Microsoft Word"
			if (count of documents) > 0 then close every document saving no
			open docAlias
			set waited to 0
			repeat while (count of documents) is 0 and waited < 60
				delay 1
				set waited to waited + 1
			end repeat
			set theDoc to document 1
			if (name of theDoc) is not (baseName & "-work.docx") then error "unexpected document open: " & (name of theDoc)
			set tocCount to count of tables of contents of theDoc
			repeat 2 times
				repeat with i from 1 to tocCount
					update table of contents i of theDoc
				end repeat
			end repeat
			save theDoc
			save as theDoc file name workPdf file format format PDF
			close theDoc saving no
		end tell
	end timeout
	do shell script "cp -f " & quoted form of workDoc & " " & quoted form of docPath & "; mv -f " & quoted form of workPdf & " " & quoted form of pdfPath & "; rm -f " & quoted form of workDoc
	return "updated " & tocCount & " tables of contents"
end run
