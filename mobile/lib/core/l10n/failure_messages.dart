import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/core/l10n/generated/app_localizations.dart';

extension FailureMessage on Failure {
  /// The message shown to the reviewer for this failure.
  String localizedMessage(AppLocalizations l10n) {
    return switch (this) {
      NetworkFailure() => l10n.errorNetwork,
      ServerFailure() => l10n.errorServer,
      UnauthorizedFailure() => l10n.errorUnauthorized,
      NotFoundFailure() => l10n.errorNotFound,
      ConflictFailure() => l10n.errorConflict,
      InvalidCredentialsFailure() => l10n.errorInvalidCredentials,
      DataFormatFailure() => l10n.errorDataFormat,
      UnexpectedFailure() => l10n.errorUnexpected,
    };
  }
}
