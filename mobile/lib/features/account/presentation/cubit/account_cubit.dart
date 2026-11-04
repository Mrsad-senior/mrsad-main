import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/account/domain/entities/account.dart';
import 'package:mirsad/features/account/domain/usecases/get_account.dart';

part 'account_state.dart';

class AccountCubit extends Cubit<AccountState> {
  AccountCubit({required this._getAccount}) : super(const AccountState());

  final GetAccount _getAccount;

  /// Reads the account from the gateway. Calling it again reloads it.
  Future<void> load() async {
    emit(const AccountState());
    final result = await _getAccount();
    emit(
      result.match(
        (failure) =>
            AccountState(status: AccountStatus.failure, failure: failure),
        (account) =>
            AccountState(status: AccountStatus.ready, account: account),
      ),
    );
  }
}
