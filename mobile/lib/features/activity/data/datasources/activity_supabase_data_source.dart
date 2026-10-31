import 'package:mirsad/core/network/supabase_error_mapping.dart';
import 'package:mirsad/features/activity/data/datasources/activity_data_source.dart';
import 'package:mirsad/features/activity/data/models/activity_event_model.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// The newest rows of the Supabase `events` table, with realtime updates.
class ActivitySupabaseDataSource implements ActivityDataSource {
  ActivitySupabaseDataSource(this._client);

  static const table = 'events';
  static const pageSize = 100;

  final SupabaseClient _client;

  @override
  Stream<List<ActivityEventModel>> watchEvents() {
    return _client
        .from(table)
        .stream(primaryKey: ['id'])
        .order('created_at')
        .limit(pageSize)
        .map((rows) => rows.map(ActivityEventModel.fromJson).toList())
        .handleError((Object error) => throw mapSupabaseError(error));
  }

  /// Realtime keeps [watchEvents] current, so there is nothing to fetch.
  @override
  Future<void> refresh() async {}
}
