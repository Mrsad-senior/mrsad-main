import 'package:mirsad/features/audit/data/models/audit_chain_status_model.dart';

/// Reports whether the audit chain is intact. Implemented by the mock and
/// API sources. Throws `AppException`s.
abstract interface class AuditDataSource {
  Future<AuditChainStatusModel> verify();
}
