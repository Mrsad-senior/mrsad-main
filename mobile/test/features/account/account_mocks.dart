import 'package:bloc_test/bloc_test.dart';
import 'package:mirsad/features/account/data/datasources/account_data_source.dart';
import 'package:mirsad/features/account/domain/entities/account.dart';
import 'package:mirsad/features/account/domain/repositories/account_repository.dart';
import 'package:mirsad/features/account/domain/usecases/get_account.dart';
import 'package:mirsad/features/account/presentation/cubit/account_cubit.dart';
import 'package:mocktail/mocktail.dart';

class MockAccountRepository extends Mock implements AccountRepository {}

class MockAccountDataSource extends Mock implements AccountDataSource {}

class MockGetAccount extends Mock implements GetAccount {}

class MockAccountCubit extends MockCubit<AccountState>
    implements AccountCubit {}

const noura = Account(
  username: 'noura@bank.example',
  role: 'approver',
  displayName: 'Noura',
  language: 'ar',
);
