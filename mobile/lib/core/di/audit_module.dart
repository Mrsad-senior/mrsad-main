import 'package:get_it/get_it.dart';
import 'package:mirsad/core/config/data_sources.dart';
import 'package:mirsad/features/audit/data/datasources/audit_api_data_source.dart';
import 'package:mirsad/features/audit/data/datasources/audit_data_source.dart';
import 'package:mirsad/features/audit/data/datasources/audit_mock_data_source.dart';
import 'package:mirsad/features/audit/data/repositories/audit_repository_impl.dart';
import 'package:mirsad/features/audit/domain/repositories/audit_repository.dart';
import 'package:mirsad/features/audit/domain/usecases/verify_audit_chain.dart';
import 'package:mirsad/features/audit/presentation/cubit/audit_cubit.dart';

void registerAuditModule(GetIt getIt, DataSources sources) {
  getIt
    ..registerLazySingleton<AuditDataSource>(
      () => switch (sources.gateway) {
        DataSourceKind.mock => const AuditMockDataSource(),
        DataSourceKind.api => AuditApiDataSource(getIt()),
        DataSourceKind.supabase => throw StateError(
          'Only the gateway can verify the audit chain.',
        ),
      },
    )
    ..registerLazySingleton<AuditRepository>(() => AuditRepositoryImpl(getIt()))
    ..registerLazySingleton(() => VerifyAuditChain(getIt()))
    ..registerFactory(() => AuditCubit(verifyAuditChain: getIt()));
}
