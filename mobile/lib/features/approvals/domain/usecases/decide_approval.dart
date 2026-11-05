import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/domain/repositories/approvals_repository.dart';

/// Approves or rejects a held action.
class DecideApproval {
  const DecideApproval(this._repository);

  /// The gateway stores at most this many characters of a note.
  static const maxNoteLength = 500;

  final ApprovalsRepository _repository;

  /// A blank [note] is sent as no note; a long one is cut to
  /// [maxNoteLength].
  Future<Either<Failure, Approval>> call({
    required String id,
    required ReviewDecision decision,
    String? note,
  }) {
    final trimmed = note?.trim() ?? '';
    final cleanNote = trimmed.isEmpty
        ? null
        : trimmed.substring(0, trimmed.length.clamp(0, maxNoteLength));
    return _repository.decide(id: id, decision: decision, note: cleanNote);
  }
}
