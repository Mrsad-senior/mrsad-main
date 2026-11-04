import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/account/data/datasources/account_data_source.dart';
import 'package:mirsad/features/account/data/models/account_model.dart';

/// Reports whoever signed in with mock sign-in. [_currentAccount] is wired
/// to the mock session in `core/di`, because features do not import each
/// other.
class AccountMockDataSource implements AccountDataSource {
  const AccountMockDataSource(this._currentAccount);

  final AccountModel? Function() _currentAccount;

  @override
  Future<AccountModel> me() async {
    return _currentAccount() ??
        (throw const UnauthorizedException('Not signed in'));
  }
}
