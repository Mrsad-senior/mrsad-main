import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';
import 'package:mirsad/core/config/app_config.dart';
import 'package:mirsad/core/config/data_sources.dart';
import 'package:mirsad/core/di/activity_module.dart';
import 'package:mirsad/core/di/approvals_module.dart';
import 'package:mirsad/core/di/audit_module.dart';
import 'package:mirsad/core/di/auth_module.dart';
import 'package:mirsad/core/di/home_module.dart';
import 'package:mirsad/core/l10n/locale_cubit.dart';
import 'package:mirsad/core/network/dio_client.dart';
import 'package:mirsad/core/network/live/live_status_cubit.dart';
import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/core/network/live/sse_live_updates.dart';
import 'package:mirsad/core/utils/clock.dart';
import 'package:mirsad/features/auth/data/datasources/auth_data_source.dart';

final GetIt getIt = GetIt.instance;

/// Registers everything the app needs, using the data sources [config] picks.
Future<void> configureDependencies(AppConfig config) async {
  final sources = DataSources.from(config);
  getIt
    ..registerSingleton<AppConfig>(config)
    ..registerSingleton<DataSources>(sources)
    ..registerSingleton<Clock>(const SystemClock())
    ..registerLazySingleton<LocaleCubit>(LocaleCubit.new);

  if (sources.usesApi) {
    getIt
      ..registerLazySingleton<Dio>(
        () => createGatewayDio(
          baseUrl: config.apiBaseUrl,
          readToken: () => getIt<AuthDataSource>().accessToken(),
        ),
      )
      ..registerLazySingleton<LiveUpdates>(
        () => SseLiveUpdates(getIt()),
        dispose: (live) => (live as SseLiveUpdates).dispose(),
      );
  } else {
    getIt.registerLazySingleton<LiveUpdates>(MockLiveUpdates.new);
  }
  getIt.registerFactory(() => LiveStatusCubit(getIt()));

  registerAuthModule(getIt, sources);
  registerApprovalsModule(getIt, sources);
  registerActivityModule(getIt, sources);
  registerAuditModule(getIt, sources);
  registerHomeModule(getIt, sources);
}
