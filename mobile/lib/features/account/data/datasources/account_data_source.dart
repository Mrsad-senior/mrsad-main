import 'package:mirsad/features/account/data/models/account_model.dart';

/// The signed-in account. Implemented by the mock and API sources. Throws
/// `AppException`s.
abstract interface class AccountDataSource {
  Future<AccountModel> me();
}
