import 'package:bloc_test/bloc_test.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_data_source.dart';
import 'package:mirsad/features/approvals/domain/repositories/approvals_repository.dart';
import 'package:mirsad/features/approvals/domain/usecases/decide_approval.dart';
import 'package:mirsad/features/approvals/domain/usecases/get_approval.dart';
import 'package:mirsad/features/approvals/domain/usecases/refresh_pending_approvals.dart';
import 'package:mirsad/features/approvals/domain/usecases/watch_pending_approvals.dart';
import 'package:mirsad/features/approvals/presentation/cubit/approval_details_cubit.dart';
import 'package:mocktail/mocktail.dart';

class MockApprovalsRepository extends Mock implements ApprovalsRepository {}

class MockApprovalsReadDataSource extends Mock
    implements ApprovalsReadDataSource {}

class MockApprovalDecisionDataSource extends Mock
    implements ApprovalDecisionDataSource {}

class MockWatchPendingApprovals extends Mock implements WatchPendingApprovals {}

class MockRefreshPendingApprovals extends Mock
    implements RefreshPendingApprovals {}

class MockGetApproval extends Mock implements GetApproval {}

class MockDecideApproval extends Mock implements DecideApproval {}

class MockApprovalDetailsCubit extends MockCubit<ApprovalDetailsState>
    implements ApprovalDetailsCubit {}
