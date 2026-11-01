import 'package:get_it/get_it.dart';
import 'package:mirsad/core/config/app_config.dart';
import 'package:mirsad/core/config/data_sources.dart';
import 'package:mirsad/core/network/dio_client.dart';
import 'package:mirsad/features/auth/data/datasources/auth_api_data_source.dart';
import 'package:mirsad/features/auth/data/datasources/auth_data_source.dart';
import 'package:mirsad/features/auth/data/datasources/auth_mock_data_source.dart';
import 'package:mirsad/features/auth/data/datasources/auth_supabase_data_source.dart';
import 'package:mirsad/features/auth/data/repositories/auth_repository_impl.dart';
import 'package:mirsad/features/auth/domain/repositories/auth_repository.dart';
import 'package:mirsad/features/auth/domain/usecases/get_current_reviewer.dart';
import 'package:mirsad/features/auth/domain/usecases/sign_in.dart';
import 'package:mirsad/features/auth/domain/usecases/sign_out.dart';
import 'package:mirsad/features/auth/domain/usecases/watch_reviewer.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';
import 'package:mirsad/features/auth/presentation/cubit/sign_in_cubit.dart';

void registerAuthModule(GetIt getIt, DataSources sources) {
  getIt
    ..registerLazySingleton<AuthDataSource>(
      () => switch (sources.auth) {
        DataSourceKind.mock => AuthMockDataSource(),
        DataSourceKind.api => AuthApiDataSource(
          createLoginDio(baseUrl: getIt<AppConfig>().apiBaseUrl),
        ),
        DataSourceKind.supabase => AuthSupabaseDataSource(getIt()),
      },
      dispose: (source) => switch (source) {
        AuthMockDataSource() => source.dispose(),
        AuthApiDataSource() => source.dispose(),
        _ => null,
      },
    )
    ..registerLazySingleton<AuthRepository>(() => AuthRepositoryImpl(getIt()))
    ..registerLazySingleton(() => GetCurrentReviewer(getIt()))
    ..registerLazySingleton(() => WatchReviewer(getIt()))
    ..registerLazySingleton(() => SignIn(getIt()))
    ..registerLazySingleton(() => SignOut(getIt()))
    // One session for the whole app.
    ..registerLazySingleton(
      () => AuthCubit(
        getCurrentReviewer: getIt(),
        watchReviewer: getIt(),
        signOut: getIt(),
      ),
    )
    ..registerFactory(() => SignInCubit(signIn: getIt()));
}
