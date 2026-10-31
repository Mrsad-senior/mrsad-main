/// The Mirsad check that flagged an action.
enum ReasonLayer {
  /// Static rules for the sector, e.g. "transfers above a limit need review".
  policy,

  /// Arguments that came from untrusted content such as an email or a PDF.
  taint,

  /// The action does not match what the user asked for.
  intent,

  /// An LLM reviewing the action judged it risky.
  llmJudge,

  /// Known prompt-injection or exfiltration phrases.
  keywords,

  /// A layer this version of the app does not know about yet.
  other,
}
