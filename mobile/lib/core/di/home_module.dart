import 'package:get_it/get_it.dart';
import 'package:mirsad/core/config/data_sources.dart';
import 'package:mirsad/features/home/data/datasources/home_api_data_source.dart';
import 'package:mirsad/features/home/data/datasources/home_data_source.dart';
import 'package:mirsad/features/home/data/datasources/home_mock_data_source.dart';
import 'package:mirsad/features/home/data/repositories/home_repository_impl.dart';
import 'package:mirsad/features/home/domain/repositories/home_repository.dart';
import 'package:mirsad/features/home/domain/usecases/refresh_overview.dart';
import 'package:mirsad/features/home/domain/usecases/watch_overview.dart';
import 'package:mirsad/features/home/presentation/cubit/home_cubit.dart';

void registerHomeModule(GetIt getIt, DataSources sources) {
  getIt
    ..registerLazySingleton<HomeDataSource>(
      () => switch (sources.kind) {
        DataSourceKind.mock => HomeMockDataSource(),
        DataSourceKind.api => HomeApiDataSource(getIt(), getIt()),
      },
      dispose: (source) => switch (source) {
        HomeMockDataSource() => source.dispose(),
        HomeApiDataSource() => source.dispose(),
        _ => null,
      },
    )
    ..registerLazySingleton<HomeRepository>(() => HomeRepositoryImpl(getIt()))
    ..registerLazySingleton(() => WatchOverview(getIt()))
    ..registerLazySingleton(() => RefreshOverview(getIt()))
    ..registerFactory(
      () => HomeCubit(watchOverview: getIt(), refreshOverview: getIt()),
    );
}
