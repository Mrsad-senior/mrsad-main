import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/supabase_error_mapping.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_data_source.dart';
import 'package:mirsad/features/approvals/data/models/approval_model.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Reads approvals from the Supabase `approvals` table, with realtime
/// updates. Decisions still go through the gateway API.
class ApprovalsSupabaseDataSource implements ApprovalsReadDataSource {
  ApprovalsSupabaseDataSource(this._client);

  static const table = 'approvals';

  final SupabaseClient _client;

  @override
  Stream<List<ApprovalModel>> watchPending() {
    return _client
        .from(table)
        .stream(primaryKey: ['id'])
        .eq('status', 'held')
        .map((rows) => rows.map(ApprovalModel.fromJson).toList())
        .handleError((Object error) => throw mapSupabaseError(error));
  }

  /// Realtime keeps [watchPending] current, so there is nothing to fetch.
  @override
  Future<void> refreshPending() async {}

  @override
  Future<ApprovalModel> getApproval(String id) {
    return callSupabase(() async {
      final row = await _client.from(table).select().eq('id', id).maybeSingle();
      if (row == null) throw NotFoundException('No approval $id');
      return ApprovalModel.fromJson(row);
    });
  }
}
