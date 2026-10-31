import 'package:mirsad/features/audit/data/models/audit_chain_status_model.dart';

/// Verifies the audit chain. Only the gateway can do this, so there is a
/// mock and an API source but no Supabase one. Throws `AppException`s.
abstract interface class AuditDataSource {
  Future<AuditChainStatusModel> verify();
}
