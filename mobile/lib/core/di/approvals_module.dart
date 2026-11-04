import 'package:get_it/get_it.dart';
import 'package:mirsad/core/config/data_sources.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_api_data_source.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_data_source.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_mock_data_source.dart';
import 'package:mirsad/features/approvals/data/repositories/approvals_repository_impl.dart';
import 'package:mirsad/features/approvals/domain/repositories/approvals_repository.dart';
import 'package:mirsad/features/approvals/domain/usecases/decide_approval.dart';
import 'package:mirsad/features/approvals/domain/usecases/get_approval.dart';
import 'package:mirsad/features/approvals/domain/usecases/refresh_pending_approvals.dart';
import 'package:mirsad/features/approvals/domain/usecases/watch_pending_approvals.dart';
import 'package:mirsad/features/approvals/presentation/cubit/approval_details_cubit.dart';
import 'package:mirsad/features/approvals/presentation/cubit/pending_approvals_cubit.dart';

void registerApprovalsModule(GetIt getIt, DataSources sources) {
  // Lazy, so only the sources [sources] picks are ever built. The mock and
  // API sources implement both interfaces and are shared between them.
  getIt
    ..registerLazySingleton<ApprovalsMockDataSource>(
      () => ApprovalsMockDataSource(clock: getIt()),
      dispose: (source) => source.dispose(),
    )
    ..registerLazySingleton<ApprovalsApiDataSource>(
      () => ApprovalsApiDataSource(getIt()),
      dispose: (source) => source.dispose(),
    )
    ..registerLazySingleton<ApprovalsReadDataSource>(
      () => switch (sources.kind) {
        DataSourceKind.mock => getIt<ApprovalsMockDataSource>(),
        DataSourceKind.api => getIt<ApprovalsApiDataSource>(),
      },
    )
    ..registerLazySingleton<ApprovalDecisionDataSource>(
      () => switch (sources.kind) {
        DataSourceKind.mock => getIt<ApprovalsMockDataSource>(),
        DataSourceKind.api => getIt<ApprovalsApiDataSource>(),
      },
    )
    ..registerLazySingleton<ApprovalsRepository>(
      () => ApprovalsRepositoryImpl(reads: getIt(), decisions: getIt()),
    )
    ..registerLazySingleton(() => WatchPendingApprovals(getIt()))
    ..registerLazySingleton(() => RefreshPendingApprovals(getIt()))
    ..registerLazySingleton(() => GetApproval(getIt()))
    ..registerLazySingleton(() => DecideApproval(getIt()))
    ..registerFactory(
      () =>
          PendingApprovalsCubit(watchPending: getIt(), refreshPending: getIt()),
    )
    ..registerFactory(
      () => ApprovalDetailsCubit(getApproval: getIt(), decide: getIt()),
    );
}
