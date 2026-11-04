import 'package:get_it/get_it.dart';
import 'package:mirsad/core/config/data_sources.dart';
import 'package:mirsad/features/account/data/datasources/account_api_data_source.dart';
import 'package:mirsad/features/account/data/datasources/account_data_source.dart';
import 'package:mirsad/features/account/data/datasources/account_mock_data_source.dart';
import 'package:mirsad/features/account/data/models/account_model.dart';
import 'package:mirsad/features/account/data/repositories/account_repository_impl.dart';
import 'package:mirsad/features/account/domain/repositories/account_repository.dart';
import 'package:mirsad/features/account/domain/usecases/get_account.dart';
import 'package:mirsad/features/account/presentation/cubit/account_cubit.dart';
import 'package:mirsad/features/auth/data/datasources/auth_data_source.dart';

void registerAccountModule(GetIt getIt, DataSources sources) {
  getIt
    ..registerLazySingleton<AccountDataSource>(
      () => switch (sources.kind) {
        // The mock account is whoever used mock sign-in.
        DataSourceKind.mock => AccountMockDataSource(() {
          final reviewer = getIt<AuthDataSource>().currentReviewer;
          return reviewer == null
              ? null
              : AccountModel(
                  username: reviewer.username,
                  role: reviewer.role.name,
                );
        }),
        DataSourceKind.api => AccountApiDataSource(getIt()),
      },
    )
    ..registerLazySingleton<AccountRepository>(
      () => AccountRepositoryImpl(getIt()),
    )
    ..registerLazySingleton(() => GetAccount(getIt()))
    ..registerFactory(() => AccountCubit(getAccount: getIt()));
}
