import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';
import 'package:mirsad/features/audit/domain/usecases/verify_audit_chain.dart';

part 'audit_state.dart';

class AuditCubit extends Cubit<AuditState> {
  AuditCubit({required this._verifyAuditChain}) : super(const AuditState());

  final VerifyAuditChain _verifyAuditChain;

  /// Verifies the chain. A previous result stays visible while it runs.
  Future<void> verify() async {
    if (state.verifying) return;
    final previous = state.result;
    emit(
      previous == null
          ? const AuditState()
          : AuditState(
              status: AuditStatus.ready,
              result: previous,
              verifying: true,
            ),
    );

    final outcome = await _verifyAuditChain();
    emit(
      outcome.match(
        (failure) => AuditState(
          status: previous == null ? AuditStatus.failure : AuditStatus.ready,
          result: previous,
          failure: failure,
        ),
        (result) => AuditState(status: AuditStatus.ready, result: result),
      ),
    );
  }
}
