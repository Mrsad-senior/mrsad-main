import 'package:mirsad/features/audit/data/models/audit_chain_status_model.dart';

/// Reports whether the audit chain is intact. Only the gateway can verify
/// it, so there is a mock and an API source but no Supabase one. Throws
/// `AppException`s.
abstract interface class AuditDataSource {
  Future<AuditChainStatusModel> verify();
}
