import 'package:get_it/get_it.dart';
import 'package:mirsad/core/config/data_sources.dart';
import 'package:mirsad/features/detector/data/datasources/detector_api_data_source.dart';
import 'package:mirsad/features/detector/data/datasources/detector_data_source.dart';
import 'package:mirsad/features/detector/data/datasources/detector_mock_data_source.dart';
import 'package:mirsad/features/detector/data/repositories/detector_repository_impl.dart';
import 'package:mirsad/features/detector/domain/repositories/detector_repository.dart';
import 'package:mirsad/features/detector/domain/usecases/scan_text.dart';
import 'package:mirsad/features/detector/presentation/cubit/detector_cubit.dart';

void registerDetectorModule(GetIt getIt, DataSources sources) {
  getIt
    ..registerLazySingleton<DetectorDataSource>(
      () => switch (sources.kind) {
        DataSourceKind.mock => DetectorMockDataSource(),
        DataSourceKind.api => DetectorApiDataSource(getIt()),
      },
    )
    ..registerLazySingleton<DetectorRepository>(
      () => DetectorRepositoryImpl(getIt()),
    )
    ..registerLazySingleton(() => ScanText(getIt()))
    ..registerFactory(() => DetectorCubit(scanText: getIt()));
}
