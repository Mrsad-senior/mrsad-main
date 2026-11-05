import 'package:mirsad/features/activity/data/datasources/activity_data_source.dart';
import 'package:mirsad/features/activity/domain/repositories/activity_repository.dart';
import 'package:mirsad/features/activity/domain/usecases/refresh_activity.dart';
import 'package:mirsad/features/activity/domain/usecases/watch_activity.dart';
import 'package:mocktail/mocktail.dart';

class MockActivityRepository extends Mock implements ActivityRepository {}

class MockActivityDataSource extends Mock implements ActivityDataSource {}

class MockWatchActivity extends Mock implements WatchActivity {}

class MockRefreshActivity extends Mock implements RefreshActivity {}
