# Mirsad — My Red-Team Report

**Mohammed Yasser Alanssari | 221110935 | 31 October 2026**

My part in Mirsad is red teaming and penetration testing. I prepared 60 attack cases and 60 normal versions of the same tasks. They cover direct overrides, fake authority, hidden text, split instructions, encoding, and Arabic or mixed-language instructions.

I ran the cases with and without Mirsad using the scripted agent. All 60 attacks worked without protection. With the benchmark's full defence, 19 still worked, reducing attack success by 68.3%. All 60 normal tasks completed without being blocked or sent for approval.

I also ran 174 automated gateway security checks, which all passed. The dependency scan found no known vulnerabilities. The audit chains passed verification, but 66 decision replays did not match the original decisions.

I reported the bypasses and replay problem in GitHub issues #4 and #5 and kept the cases for retesting after fixes. Testing with two real language models and measuring detector F1 are still pending. These results come from synthetic, scripted tests.

The scenarios and tooling were prepared with AI assistance.
