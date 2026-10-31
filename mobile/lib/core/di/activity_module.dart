import 'package:get_it/get_it.dart';
import 'package:mirsad/core/config/data_sources.dart';
import 'package:mirsad/features/activity/data/datasources/activity_api_data_source.dart';
import 'package:mirsad/features/activity/data/datasources/activity_data_source.dart';
import 'package:mirsad/features/activity/data/datasources/activity_mock_data_source.dart';
import 'package:mirsad/features/activity/data/datasources/activity_supabase_data_source.dart';
import 'package:mirsad/features/activity/data/repositories/activity_repository_impl.dart';
import 'package:mirsad/features/activity/domain/repositories/activity_repository.dart';
import 'package:mirsad/features/activity/domain/usecases/refresh_activity.dart';
import 'package:mirsad/features/activity/domain/usecases/watch_activity.dart';
import 'package:mirsad/features/activity/presentation/cubit/activity_cubit.dart';

void registerActivityModule(GetIt getIt, DataSources sources) {
  getIt
    ..registerLazySingleton<ActivityDataSource>(
      () => switch (sources.reads) {
        DataSourceKind.mock => ActivityMockDataSource(clock: getIt()),
        DataSourceKind.api => ActivityApiDataSource(getIt()),
        DataSourceKind.supabase => ActivitySupabaseDataSource(getIt()),
      },
      dispose: (source) => switch (source) {
        ActivityMockDataSource() => source.dispose(),
        ActivityApiDataSource() => source.dispose(),
        _ => null,
      },
    )
    ..registerLazySingleton<ActivityRepository>(
      () => ActivityRepositoryImpl(getIt()),
    )
    ..registerLazySingleton(() => WatchActivity(getIt()))
    ..registerLazySingleton(() => RefreshActivity(getIt()))
    ..registerFactory(
      () => ActivityCubit(watchActivity: getIt(), refreshActivity: getIt()),
    );
}
