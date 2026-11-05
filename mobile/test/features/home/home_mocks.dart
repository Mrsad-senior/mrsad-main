import 'package:bloc_test/bloc_test.dart';
import 'package:mirsad/features/home/data/datasources/home_data_source.dart';
import 'package:mirsad/features/home/domain/repositories/home_repository.dart';
import 'package:mirsad/features/home/domain/usecases/refresh_overview.dart';
import 'package:mirsad/features/home/domain/usecases/watch_overview.dart';
import 'package:mirsad/features/home/presentation/cubit/home_cubit.dart';
import 'package:mocktail/mocktail.dart';

class MockHomeRepository extends Mock implements HomeRepository {}

class MockHomeDataSource extends Mock implements HomeDataSource {}

class MockWatchOverview extends Mock implements WatchOverview {}

class MockRefreshOverview extends Mock implements RefreshOverview {}

class MockHomeCubit extends MockCubit<HomeState> implements HomeCubit {}
