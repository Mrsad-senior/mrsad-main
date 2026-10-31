// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class AppLocalizationsAr extends AppLocalizations {
  AppLocalizationsAr([String locale = 'ar']) : super(locale);

  @override
  String get appTitle => 'مرصاد';

  @override
  String get navApprovals => 'الموافقات';

  @override
  String get navActivity => 'النشاط';

  @override
  String get navAudit => 'التدقيق';

  @override
  String get approvalsTitle => 'الموافقات المعلّقة';

  @override
  String get activityTitle => 'النشاط';

  @override
  String get auditTitle => 'سجل التدقيق';

  @override
  String get retry => 'إعادة المحاولة';

  @override
  String get cancel => 'إلغاء';

  @override
  String get switchLanguage => 'تغيير اللغة';

  @override
  String get otherLanguageName => 'English';

  @override
  String get signOut => 'تسجيل الخروج';

  @override
  String get configErrorTitle => 'التطبيق غير مُهيّأ';

  @override
  String get errorNetwork =>
      'تعذّر الوصول إلى بوابة مرصاد. تحقّق من اتصالك وحاول مرة أخرى.';

  @override
  String get errorServer => 'واجهت البوابة مشكلة. حاول مرة أخرى بعد قليل.';

  @override
  String get errorUnauthorized => 'انتهت جلستك. سجّل الدخول مرة أخرى.';

  @override
  String get errorNotFound => 'هذا العنصر لم يعد موجودًا.';

  @override
  String get errorConflict => 'تم البتّ في هذا الإجراء مسبقًا أو انتهت مهلته.';

  @override
  String get errorInvalidCredentials =>
      'البريد الإلكتروني أو كلمة المرور غير صحيحة.';

  @override
  String get errorDataFormat => 'أرسلت البوابة بيانات لا يفهمها التطبيق.';

  @override
  String get errorUnexpected => 'حدث خطأ ما. حاول مرة أخرى.';

  @override
  String get riskLow => 'منخفض';

  @override
  String get riskMedium => 'متوسط';

  @override
  String get riskHigh => 'مرتفع';

  @override
  String riskScore(String level, int percent) {
    return 'خطر $level · $percent٪';
  }

  @override
  String get statusHeld => 'مُعلّق';

  @override
  String get statusApproved => 'تمت الموافقة';

  @override
  String get statusRejected => 'مرفوض';

  @override
  String get statusExpired => 'منتهي المهلة';

  @override
  String get decisionAllowed => 'مسموح';

  @override
  String get decisionDenied => 'محظور';

  @override
  String get decisionHeld => 'مُعلّق';

  @override
  String get taintedInput => 'مدخلات غير موثوقة';

  @override
  String get sectorFinance => 'المالية';

  @override
  String get sectorHealthcare => 'الرعاية الصحية';

  @override
  String get sectorGeneral => 'عام';

  @override
  String get layerPolicy => 'السياسات';

  @override
  String get layerTaint => 'تتبّع المدخلات غير الموثوقة';

  @override
  String get layerIntent => 'مطابقة النية';

  @override
  String get layerLlmJudge => 'المُقيّم الذكي';

  @override
  String get layerKeywords => 'فحص الكلمات المفتاحية';

  @override
  String get layerOther => 'فحص آخر';

  @override
  String get toolTransferFunds => 'تحويل أموال';

  @override
  String get toolSendEmail => 'إرسال بريد إلكتروني';

  @override
  String get toolExportCustomerRecords => 'تصدير سجلات العملاء';

  @override
  String get toolUpdateBeneficiary => 'تعديل المستفيد';

  @override
  String get toolGetAccountBalance => 'الاستعلام عن الرصيد';

  @override
  String get pendingEmptyTitle => 'لا توجد إجراءات بانتظار المراجعة';

  @override
  String get pendingEmptyMessage =>
      'تظهر هنا الإجراءات المعلّقة فور إيقاف مرصاد لها.';

  @override
  String expiresIn(String time) {
    return 'رفض تلقائي خلال $time';
  }

  @override
  String recipient(String recipient) {
    return 'إلى $recipient';
  }

  @override
  String get approvalDetailsTitle => 'مراجعة الإجراء';

  @override
  String get userAskedTitle => 'ما طلبه المستخدم';

  @override
  String get agentWantsTitle => 'ما يحاول الوكيل تنفيذه';

  @override
  String get argumentsTitle => 'معطيات الطلب';

  @override
  String get reasonsTitle => 'لماذا أوقف مرصاد هذا الإجراء';

  @override
  String get agentLabel => 'الوكيل';

  @override
  String get sectorLabel => 'القطاع';

  @override
  String get requestedAtLabel => 'وقت الطلب';

  @override
  String get approve => 'موافقة';

  @override
  String get reject => 'رفض';

  @override
  String get confirmApproveTitle => 'الموافقة على هذا الإجراء؟';

  @override
  String confirmApproveBody(String tool) {
    return 'سينفّذ الوكيل «$tool» فورًا.';
  }

  @override
  String get confirmRejectTitle => 'رفض هذا الإجراء؟';

  @override
  String confirmRejectBody(String tool) {
    return 'سيتم إلغاء طلب الوكيل «$tool».';
  }

  @override
  String get noteLabel => 'ملاحظة (اختيارية)';

  @override
  String get noteHint => 'ما سبب قرارك؟';

  @override
  String get approvedMessage => 'تمت الموافقة على الإجراء';

  @override
  String get rejectedMessage => 'تم رفض الإجراء';

  @override
  String get noLongerHeld => 'لم يعد هذا الإجراء بانتظار المراجعة.';

  @override
  String get activityEmptyTitle => 'لا يوجد نشاط بعد';

  @override
  String get activityEmptyMessage => 'يظهر هنا كل إجراء يحاول الوكيل تنفيذه.';

  @override
  String get activityFilteredEmpty => 'لا توجد نتائج لهذه التصفية.';

  @override
  String get filterAll => 'الكل';

  @override
  String get auditValidTitle => 'سلسلة التدقيق سليمة';

  @override
  String get auditValidMessage =>
      'كل قرار مسجّل يطابق بصمته، ولم يُعدَّل أي سجل.';

  @override
  String get auditBrokenTitle => 'سلسلة التدقيق مكسورة';

  @override
  String auditBrokenMessage(int index) {
    return 'السجل رقم $index لا يطابق بصمته. قد تكون السجلات من هذه النقطة فصاعدًا معدّلة.';
  }

  @override
  String get auditBrokenUnknownEntry =>
      'أحد السجلات لا يطابق بصمته. قد تكون السجلات معدّلة.';

  @override
  String get auditVerifyAgain => 'تحقّق مرة أخرى';

  @override
  String get signInTitle => 'تسجيل الدخول';

  @override
  String get signInSubtitle =>
      'راجع الإجراءات التي أوقفها مرصاد بانتظار قرارك.';

  @override
  String get emailLabel => 'البريد الإلكتروني';

  @override
  String get passwordLabel => 'كلمة المرور';

  @override
  String get signInButton => 'دخول';

  @override
  String get emailInvalid => 'أدخل بريدًا إلكترونيًا صالحًا.';

  @override
  String get passwordTooShort => 'استخدم 6 أحرف على الأقل.';

  @override
  String get mockSignInHint =>
      'وضع التجربة: يعمل أي بريد إلكتروني مع كلمة مرور من 6 أحرف أو أكثر.';
}
