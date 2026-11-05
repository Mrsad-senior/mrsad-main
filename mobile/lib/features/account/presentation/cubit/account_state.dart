part of 'account_cubit.dart';

enum AccountStatus { loading, ready, failure }

class AccountState extends Equatable {
  const AccountState({
    this.status = AccountStatus.loading,
    this.account,
    this.failure,
  });

  final AccountStatus status;
  final Account? account;
  final Failure? failure;

  @override
  List<Object?> get props => [status, account, failure];
}
