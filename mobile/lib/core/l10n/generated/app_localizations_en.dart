// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'Mirsad';

  @override
  String get navApprovals => 'Approvals';

  @override
  String get navActivity => 'Activity';

  @override
  String get navAudit => 'Audit';

  @override
  String get approvalsTitle => 'Pending approvals';

  @override
  String get activityTitle => 'Activity';

  @override
  String get auditTitle => 'Audit log';

  @override
  String get retry => 'Try again';

  @override
  String get cancel => 'Cancel';

  @override
  String get switchLanguage => 'Switch language';

  @override
  String get otherLanguageName => 'العربية';

  @override
  String get signOut => 'Sign out';

  @override
  String get configErrorTitle => 'The app is not configured';

  @override
  String get errorNetwork =>
      'Can\'t reach the Mirsad gateway. Check your connection and try again.';

  @override
  String get errorServer =>
      'The gateway ran into a problem. Try again in a moment.';

  @override
  String get errorUnauthorized => 'Your session has expired. Sign in again.';

  @override
  String get errorNotFound => 'This item no longer exists.';

  @override
  String get errorConflict => 'This action was already decided or has expired.';

  @override
  String get errorInvalidCredentials => 'Wrong email or password.';

  @override
  String get errorDataFormat =>
      'The gateway sent data the app doesn\'t understand.';

  @override
  String get errorUnexpected => 'Something went wrong. Try again.';

  @override
  String get riskLow => 'Low';

  @override
  String get riskMedium => 'Medium';

  @override
  String get riskHigh => 'High';

  @override
  String riskScore(String level, int percent) {
    return '$level risk · $percent%';
  }

  @override
  String get statusHeld => 'Held';

  @override
  String get statusApproved => 'Approved';

  @override
  String get statusRejected => 'Rejected';

  @override
  String get statusExpired => 'Expired';

  @override
  String get decisionAllowed => 'Allowed';

  @override
  String get decisionDenied => 'Denied';

  @override
  String get decisionHeld => 'Held';

  @override
  String get taintedInput => 'Untrusted input';

  @override
  String get sectorFinance => 'Finance';

  @override
  String get sectorHealthcare => 'Healthcare';

  @override
  String get sectorGeneral => 'General';

  @override
  String get layerPolicy => 'Policy';

  @override
  String get layerTaint => 'Taint tracking';

  @override
  String get layerIntent => 'Intent check';

  @override
  String get layerLlmJudge => 'LLM judge';

  @override
  String get layerKeywords => 'Keyword scan';

  @override
  String get layerOther => 'Other check';

  @override
  String get toolTransferFunds => 'Transfer funds';

  @override
  String get toolSendEmail => 'Send email';

  @override
  String get toolExportCustomerRecords => 'Export customer records';

  @override
  String get toolUpdateBeneficiary => 'Change beneficiary';

  @override
  String get toolGetAccountBalance => 'Check balance';

  @override
  String get pendingEmptyTitle => 'Nothing waiting for review';

  @override
  String get pendingEmptyMessage =>
      'Held actions appear here the moment Mirsad stops them.';

  @override
  String expiresIn(String time) {
    return 'Auto-rejects in $time';
  }

  @override
  String recipient(String recipient) {
    return 'To $recipient';
  }

  @override
  String get approvalDetailsTitle => 'Review action';

  @override
  String get userAskedTitle => 'What the user asked';

  @override
  String get agentWantsTitle => 'What the agent is trying to do';

  @override
  String get argumentsTitle => 'Arguments';

  @override
  String get reasonsTitle => 'Why Mirsad held this';

  @override
  String get agentLabel => 'Agent';

  @override
  String get sectorLabel => 'Sector';

  @override
  String get requestedAtLabel => 'Requested at';

  @override
  String get approve => 'Approve';

  @override
  String get reject => 'Reject';

  @override
  String get confirmApproveTitle => 'Approve this action?';

  @override
  String confirmApproveBody(String tool) {
    return 'The agent will run $tool right away.';
  }

  @override
  String get confirmRejectTitle => 'Reject this action?';

  @override
  String confirmRejectBody(String tool) {
    return 'The agent\'s $tool request will be cancelled.';
  }

  @override
  String get noteLabel => 'Note (optional)';

  @override
  String get noteHint => 'Why are you making this decision?';

  @override
  String get approvedMessage => 'Action approved';

  @override
  String get rejectedMessage => 'Action rejected';

  @override
  String get noLongerHeld => 'This action is no longer waiting for review.';

  @override
  String get activityEmptyTitle => 'No activity yet';

  @override
  String get activityEmptyMessage =>
      'Every action an agent tries shows up here.';

  @override
  String get activityFilteredEmpty => 'Nothing matches this filter.';

  @override
  String get filterAll => 'All';

  @override
  String get auditValidTitle => 'Audit chain intact';

  @override
  String get auditValidMessage =>
      'Every recorded decision matches its hash. Nothing has been altered.';

  @override
  String get auditBrokenTitle => 'Audit chain broken';

  @override
  String auditBrokenMessage(int index) {
    return 'Entry $index doesn\'t match its hash. Records from that point on may have been altered.';
  }

  @override
  String get auditBrokenUnknownEntry =>
      'An entry doesn\'t match its hash. Records may have been altered.';

  @override
  String get auditVerifyAgain => 'Verify again';

  @override
  String get signInTitle => 'Sign in';

  @override
  String get signInSubtitle => 'Review the actions Mirsad has held for you.';

  @override
  String get emailLabel => 'Email';

  @override
  String get passwordLabel => 'Password';

  @override
  String get signInButton => 'Sign in';

  @override
  String get emailInvalid => 'Enter a valid email.';

  @override
  String get passwordTooShort => 'Use at least 6 characters.';

  @override
  String get mockSignInHint =>
      'Mock mode: any email and a password of 6 or more characters works.';
}
