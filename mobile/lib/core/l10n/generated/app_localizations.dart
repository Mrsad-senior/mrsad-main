import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('en'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'Mirsad'**
  String get appTitle;

  /// No description provided for @navApprovals.
  ///
  /// In en, this message translates to:
  /// **'Approvals'**
  String get navApprovals;

  /// No description provided for @navActivity.
  ///
  /// In en, this message translates to:
  /// **'Activity'**
  String get navActivity;

  /// No description provided for @navAudit.
  ///
  /// In en, this message translates to:
  /// **'Audit'**
  String get navAudit;

  /// No description provided for @approvalsTitle.
  ///
  /// In en, this message translates to:
  /// **'Pending approvals'**
  String get approvalsTitle;

  /// No description provided for @activityTitle.
  ///
  /// In en, this message translates to:
  /// **'Activity'**
  String get activityTitle;

  /// No description provided for @auditTitle.
  ///
  /// In en, this message translates to:
  /// **'Audit log'**
  String get auditTitle;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get retry;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @switchLanguage.
  ///
  /// In en, this message translates to:
  /// **'Switch language'**
  String get switchLanguage;

  /// No description provided for @otherLanguageName.
  ///
  /// In en, this message translates to:
  /// **'العربية'**
  String get otherLanguageName;

  /// No description provided for @signOut.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get signOut;

  /// No description provided for @configErrorTitle.
  ///
  /// In en, this message translates to:
  /// **'The app is not configured'**
  String get configErrorTitle;

  /// No description provided for @errorNetwork.
  ///
  /// In en, this message translates to:
  /// **'Can\'t reach the Mirsad gateway. Check your connection and try again.'**
  String get errorNetwork;

  /// No description provided for @errorServer.
  ///
  /// In en, this message translates to:
  /// **'The gateway ran into a problem. Try again in a moment.'**
  String get errorServer;

  /// No description provided for @errorUnauthorized.
  ///
  /// In en, this message translates to:
  /// **'Your session has expired. Sign in again.'**
  String get errorUnauthorized;

  /// No description provided for @errorNotFound.
  ///
  /// In en, this message translates to:
  /// **'This item no longer exists.'**
  String get errorNotFound;

  /// No description provided for @errorConflict.
  ///
  /// In en, this message translates to:
  /// **'This action was already decided or has expired.'**
  String get errorConflict;

  /// No description provided for @errorInvalidCredentials.
  ///
  /// In en, this message translates to:
  /// **'Wrong email or password.'**
  String get errorInvalidCredentials;

  /// No description provided for @errorDataFormat.
  ///
  /// In en, this message translates to:
  /// **'The gateway sent data the app doesn\'t understand.'**
  String get errorDataFormat;

  /// No description provided for @errorUnexpected.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong. Try again.'**
  String get errorUnexpected;

  /// No description provided for @riskLow.
  ///
  /// In en, this message translates to:
  /// **'Low'**
  String get riskLow;

  /// No description provided for @riskMedium.
  ///
  /// In en, this message translates to:
  /// **'Medium'**
  String get riskMedium;

  /// No description provided for @riskHigh.
  ///
  /// In en, this message translates to:
  /// **'High'**
  String get riskHigh;

  /// Risk chip text, e.g. 'High risk · 92%'.
  ///
  /// In en, this message translates to:
  /// **'{level} risk · {percent}%'**
  String riskScore(String level, int percent);

  /// No description provided for @statusHeld.
  ///
  /// In en, this message translates to:
  /// **'Held'**
  String get statusHeld;

  /// No description provided for @statusApproved.
  ///
  /// In en, this message translates to:
  /// **'Approved'**
  String get statusApproved;

  /// No description provided for @statusRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get statusRejected;

  /// No description provided for @statusExpired.
  ///
  /// In en, this message translates to:
  /// **'Expired'**
  String get statusExpired;

  /// No description provided for @decisionAllowed.
  ///
  /// In en, this message translates to:
  /// **'Allowed'**
  String get decisionAllowed;

  /// No description provided for @decisionDenied.
  ///
  /// In en, this message translates to:
  /// **'Denied'**
  String get decisionDenied;

  /// No description provided for @decisionHeld.
  ///
  /// In en, this message translates to:
  /// **'Held'**
  String get decisionHeld;

  /// No description provided for @taintedInput.
  ///
  /// In en, this message translates to:
  /// **'Untrusted input'**
  String get taintedInput;

  /// No description provided for @sectorFinance.
  ///
  /// In en, this message translates to:
  /// **'Finance'**
  String get sectorFinance;

  /// No description provided for @sectorHealthcare.
  ///
  /// In en, this message translates to:
  /// **'Healthcare'**
  String get sectorHealthcare;

  /// No description provided for @sectorGeneral.
  ///
  /// In en, this message translates to:
  /// **'General'**
  String get sectorGeneral;

  /// No description provided for @layerPolicy.
  ///
  /// In en, this message translates to:
  /// **'Policy'**
  String get layerPolicy;

  /// No description provided for @layerTaint.
  ///
  /// In en, this message translates to:
  /// **'Taint tracking'**
  String get layerTaint;

  /// No description provided for @layerIntent.
  ///
  /// In en, this message translates to:
  /// **'Intent check'**
  String get layerIntent;

  /// No description provided for @layerLlmJudge.
  ///
  /// In en, this message translates to:
  /// **'LLM judge'**
  String get layerLlmJudge;

  /// No description provided for @layerKeywords.
  ///
  /// In en, this message translates to:
  /// **'Keyword scan'**
  String get layerKeywords;

  /// No description provided for @layerOther.
  ///
  /// In en, this message translates to:
  /// **'Other check'**
  String get layerOther;

  /// No description provided for @toolTransferFunds.
  ///
  /// In en, this message translates to:
  /// **'Transfer funds'**
  String get toolTransferFunds;

  /// No description provided for @toolSendEmail.
  ///
  /// In en, this message translates to:
  /// **'Send email'**
  String get toolSendEmail;

  /// No description provided for @toolExportCustomerRecords.
  ///
  /// In en, this message translates to:
  /// **'Export customer records'**
  String get toolExportCustomerRecords;

  /// No description provided for @toolUpdateBeneficiary.
  ///
  /// In en, this message translates to:
  /// **'Change beneficiary'**
  String get toolUpdateBeneficiary;

  /// No description provided for @toolGetAccountBalance.
  ///
  /// In en, this message translates to:
  /// **'Check balance'**
  String get toolGetAccountBalance;

  /// No description provided for @pendingEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'Nothing waiting for review'**
  String get pendingEmptyTitle;

  /// No description provided for @pendingEmptyMessage.
  ///
  /// In en, this message translates to:
  /// **'Held actions appear here the moment Mirsad stops them.'**
  String get pendingEmptyMessage;

  /// No description provided for @expiresIn.
  ///
  /// In en, this message translates to:
  /// **'Auto-rejects in {time}'**
  String expiresIn(String time);

  /// No description provided for @recipient.
  ///
  /// In en, this message translates to:
  /// **'To {recipient}'**
  String recipient(String recipient);

  /// No description provided for @approvalDetailsTitle.
  ///
  /// In en, this message translates to:
  /// **'Review action'**
  String get approvalDetailsTitle;

  /// No description provided for @userAskedTitle.
  ///
  /// In en, this message translates to:
  /// **'What the user asked'**
  String get userAskedTitle;

  /// No description provided for @agentWantsTitle.
  ///
  /// In en, this message translates to:
  /// **'What the agent is trying to do'**
  String get agentWantsTitle;

  /// No description provided for @argumentsTitle.
  ///
  /// In en, this message translates to:
  /// **'Arguments'**
  String get argumentsTitle;

  /// No description provided for @reasonsTitle.
  ///
  /// In en, this message translates to:
  /// **'Why Mirsad held this'**
  String get reasonsTitle;

  /// No description provided for @agentLabel.
  ///
  /// In en, this message translates to:
  /// **'Agent'**
  String get agentLabel;

  /// No description provided for @sectorLabel.
  ///
  /// In en, this message translates to:
  /// **'Sector'**
  String get sectorLabel;

  /// No description provided for @requestedAtLabel.
  ///
  /// In en, this message translates to:
  /// **'Requested at'**
  String get requestedAtLabel;

  /// No description provided for @approve.
  ///
  /// In en, this message translates to:
  /// **'Approve'**
  String get approve;

  /// No description provided for @reject.
  ///
  /// In en, this message translates to:
  /// **'Reject'**
  String get reject;

  /// No description provided for @confirmApproveTitle.
  ///
  /// In en, this message translates to:
  /// **'Approve this action?'**
  String get confirmApproveTitle;

  /// No description provided for @confirmApproveBody.
  ///
  /// In en, this message translates to:
  /// **'The agent will run {tool} right away.'**
  String confirmApproveBody(String tool);

  /// No description provided for @confirmRejectTitle.
  ///
  /// In en, this message translates to:
  /// **'Reject this action?'**
  String get confirmRejectTitle;

  /// No description provided for @confirmRejectBody.
  ///
  /// In en, this message translates to:
  /// **'The agent\'s {tool} request will be cancelled.'**
  String confirmRejectBody(String tool);

  /// No description provided for @noteLabel.
  ///
  /// In en, this message translates to:
  /// **'Note (optional)'**
  String get noteLabel;

  /// No description provided for @noteHint.
  ///
  /// In en, this message translates to:
  /// **'Why are you making this decision?'**
  String get noteHint;

  /// No description provided for @approvedMessage.
  ///
  /// In en, this message translates to:
  /// **'Action approved'**
  String get approvedMessage;

  /// No description provided for @rejectedMessage.
  ///
  /// In en, this message translates to:
  /// **'Action rejected'**
  String get rejectedMessage;

  /// No description provided for @noLongerHeld.
  ///
  /// In en, this message translates to:
  /// **'This action is no longer waiting for review.'**
  String get noLongerHeld;

  /// No description provided for @activityEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'No activity yet'**
  String get activityEmptyTitle;

  /// No description provided for @activityEmptyMessage.
  ///
  /// In en, this message translates to:
  /// **'Every action an agent tries shows up here.'**
  String get activityEmptyMessage;

  /// No description provided for @activityFilteredEmpty.
  ///
  /// In en, this message translates to:
  /// **'Nothing matches this filter.'**
  String get activityFilteredEmpty;

  /// No description provided for @filterAll.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get filterAll;

  /// No description provided for @auditValidTitle.
  ///
  /// In en, this message translates to:
  /// **'Audit chain intact'**
  String get auditValidTitle;

  /// No description provided for @auditValidMessage.
  ///
  /// In en, this message translates to:
  /// **'Every recorded decision matches its hash. Nothing has been altered.'**
  String get auditValidMessage;

  /// No description provided for @auditBrokenTitle.
  ///
  /// In en, this message translates to:
  /// **'Audit chain broken'**
  String get auditBrokenTitle;

  /// No description provided for @auditBrokenMessage.
  ///
  /// In en, this message translates to:
  /// **'Entry {index} doesn\'t match its hash. Records from that point on may have been altered.'**
  String auditBrokenMessage(int index);

  /// No description provided for @auditBrokenUnknownEntry.
  ///
  /// In en, this message translates to:
  /// **'An entry doesn\'t match its hash. Records may have been altered.'**
  String get auditBrokenUnknownEntry;

  /// No description provided for @auditVerifyAgain.
  ///
  /// In en, this message translates to:
  /// **'Verify again'**
  String get auditVerifyAgain;

  /// No description provided for @signInTitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get signInTitle;

  /// No description provided for @signInSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Review the actions Mirsad has held for you.'**
  String get signInSubtitle;

  /// No description provided for @emailLabel.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get emailLabel;

  /// No description provided for @passwordLabel.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get passwordLabel;

  /// No description provided for @signInButton.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get signInButton;

  /// No description provided for @emailInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid email.'**
  String get emailInvalid;

  /// No description provided for @passwordTooShort.
  ///
  /// In en, this message translates to:
  /// **'Use at least 6 characters.'**
  String get passwordTooShort;

  /// No description provided for @mockSignInHint.
  ///
  /// In en, this message translates to:
  /// **'Mock mode: any email and a password of 6 or more characters works.'**
  String get mockSignInHint;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ar', 'en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return AppLocalizationsAr();
    case 'en':
      return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
